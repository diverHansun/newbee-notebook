# ASR Transcription Pipeline Design

## Overview

When a video has no CC subtitles, the summarization pipeline falls back to speech-to-text
transcription. This document defines the ASR pipeline architecture supporting two cloud providers
(Zhipu GLM-ASR, Qwen ASR-Flash) via the user's existing API keys.

---

## Provider Specifications

### Zhipu GLM-ASR-2512

| Item | Value |
|------|-------|
| Model | `glm-asr-2512` |
| Endpoint | `https://open.bigmodel.cn/api/paas/v4/audio/transcriptions` |
| Upload method | multipart/form-data: `file` (binary) or `file_base64` (string) |
| Audio format | `.wav`, `.mp3` |
| Max file size | 25 MB |
| Max duration | 30 seconds per request |
| Auth | Bearer token (ZHIPU_API_KEY) |
| Response | `{"text": "transcribed content"}` |
| Optional params | `prompt` (context hint), `hotwords` (list, max 100) |

### Qwen qwen3-asr-flash

| Item | Value |
|------|-------|
| Model | `qwen3-asr-flash` |
| Endpoint | `https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation` |
| Upload method | Messages body: `{"audio": "data:audio/wav;base64,..."}` |
| Audio format | `.wav`, `.mp3`, and others |
| Max file size | 10 MB |
| Max duration | 5 minutes per request |
| Auth | Bearer token (DASHSCOPE_API_KEY) |
| Response | MultiModalConversation format, extract text from `output.choices[0].message.content[0].text` |
| Optional params | `asr_options.language` (e.g. "zh"), `asr_options.enable_itn` (inverse text normalization) |

### Key Difference: Segment Granularity

| Metric | Zhipu | Qwen |
|--------|-------|------|
| Max per segment | 30s | 5min |
| 10-min video segments | ~20 | ~2 |
| 30-min video segments | ~60 | ~6 |
| Concurrency needed | Higher (limit 5) | Lower (limit 3) |

Qwen produces far fewer segments per video, reducing total latency and API call count.

---

## Pipeline Architecture

```
VideoService.summarize()
  |  subtitle not available
  v
VideoService._transcribe_with_asr(bvid, info)
  |
  v
AsrPipeline.transcribe(source)
  |
  +-- audio_fetcher(source) -> audio_file_path
  |     BilibiliClient.get_audio_url(bvid) -> url
  |     BilibiliClient.download_audio(url, temp_path) -> bytes
  |
  +-- segmenter(audio_file_path) -> list[segment_path]
  |     AudioProcessor.convert_and_split(input, max_seconds) -> [seg_001.wav, ...]
  |     m4s/AAC -> 16kHz mono WAV -> time-based split
  |
  +-- transcriber(segments) -> transcript_text
        Provider-specific adapter:
        ZhipuTranscriber or QwenTranscriber
        Concurrent execution with rate limiting
        Merge results in segment order
```

---

## Component Details

### 1. AudioProcessor (new module)

File: `infrastructure/bilibili/audio_processor.py`

Responsibilities:
- Accept audio file in any format (m4s, AAC, MP3)
- Convert to 16kHz mono PCM WAV
- Split into fixed-duration segments
- Return list of segment file paths
- Clean up temp files via context manager or explicit cleanup

```python
class AudioProcessor:
    @staticmethod
    def convert_and_split(
        input_path: str,
        output_dir: str,
        max_segment_seconds: int = 25,
    ) -> list[str]:
        """Convert audio to WAV and split into segments.

        Returns list of segment file paths, each a 16kHz mono WAV.
        """
```

Implementation uses PyAV (`av` package):

1. Open input container (`av.open(input_path)`)
2. Iterate decoded audio frames
3. Track cumulative sample count per segment
4. When segment threshold reached, write accumulated frames:
   - Resample to 16kHz mono via `av.AudioResampler(format="s16", layout="mono", rate=16000)`
   - Encode as PCM s16le WAV
5. Handle final partial segment

Reference: `bilibili-cli/bili_cli/client.py` `split_audio()` (lines 698-773).

**Segment duration per provider:**

| Provider | max_segment_seconds | Rationale |
|----------|-------------------|-----------|
| Zhipu | 25 | 30s API limit, 5s safety margin |
| Qwen | 270 | 5min API limit, 30s safety margin |

The segment duration is determined by the active ASR provider config at runtime.

### 2. Audio Fetcher

Implemented as a closure wired in dependency injection. Not a separate class.

```python
async def audio_fetcher(source: dict) -> str:
    bvid = source["video_id"]
    audio_url = await bili_client.get_audio_url(bvid)
    temp_path = os.path.join(temp_dir, f"{bvid}_audio.m4s")
    await bili_client.download_audio(audio_url, temp_path)
    return temp_path
```

Progress callback emitted at download start: `("asr", {"step": "download", "video_id": bvid})`.

### 3. Segmenter

Closure wrapping `AudioProcessor.convert_and_split`:

```python
def segmenter(audio_path: str) -> list[str]:
    return AudioProcessor.convert_and_split(
        input_path=audio_path,
        output_dir=os.path.join(temp_dir, "segments"),
        max_segment_seconds=segment_seconds,  # from ASR config
    )
```

Progress callback emitted: `("asr", {"step": "segment", "segment_count": len(segments)})`.

### 4. Transcribers

Provider-specific implementations under `infrastructure/asr/`.

#### ZhipuTranscriber

File: `infrastructure/asr/zhipu_transcriber.py`

```python
class ZhipuTranscriber:
    def __init__(self, api_key: str, max_concurrency: int = 5):
        self._api_key = api_key
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def transcribe_segments(self, segment_paths: list[str]) -> str:
        tasks = [
            self._transcribe_one(path, index)
            for index, path in enumerate(segment_paths)
        ]
        results = await asyncio.gather(*tasks)
        return " ".join(r for r in results if r.strip())

    async def _transcribe_one(self, path: str, index: int) -> str:
        async with self._semaphore:
            return await self._call_api(path)
```

API call:
- Read file, base64 encode
- POST to `https://open.bigmodel.cn/api/paas/v4/audio/transcriptions`
- Headers: `Authorization: Bearer {api_key}`, `Content-Type: multipart/form-data`
- Body: `model=glm-asr-2512`, `file_base64=<encoded>`, `stream=false`
- Extract: `response.json()["text"]`

Retry: 3 attempts, exponential backoff (1s, 2s, 4s).

#### QwenTranscriber

File: `infrastructure/asr/qwen_transcriber.py`

```python
class QwenTranscriber:
    def __init__(self, api_key: str, base_url: str | None = None, max_concurrency: int = 3):
        self._api_key = api_key
        self._base_url = base_url or "https://dashscope.aliyuncs.com/api/v1"
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def transcribe_segments(self, segment_paths: list[str]) -> str:
        tasks = [
            self._transcribe_one(path, index)
            for index, path in enumerate(segment_paths)
        ]
        results = await asyncio.gather(*tasks)
        return " ".join(r for r in results if r.strip())

    async def _transcribe_one(self, path: str, index: int) -> str:
        async with self._semaphore:
            return await self._call_api(path)
```

API call:
- Read file, base64 encode to data URL: `data:audio/wav;base64,{encoded}`
- POST to `{base_url}/services/aigc/multimodal-generation/generation`
- Headers: `Authorization: Bearer {api_key}`, `Content-Type: application/json`
- Body:

```json
{
    "model": "qwen3-asr-flash",
    "input": {
        "messages": [
            {"role": "system", "content": [{"text": ""}]},
            {"role": "user", "content": [{"audio": "data:audio/wav;base64,..."}]}
        ]
    },
    "parameters": {
        "asr_options": {"enable_itn": false}
    }
}
```

- Extract: `response.json()["output"]["choices"][0]["message"]["content"][0]["text"]`

Retry: 3 attempts, exponential backoff (1s, 2s, 4s).

---

## Integration with Existing Code

### AsrPipeline Refactoring

Current scaffold at `infrastructure/bilibili/asr.py` processes segments sequentially.
Refactor to delegate to the provider transcriber's `transcribe_segments()` for concurrent execution:

```python
class AsrPipeline:
    def __init__(
        self,
        *,
        audio_fetcher: Callable,
        segmenter: Callable,
        transcriber: ZhipuTranscriber | QwenTranscriber,
    ):
        ...

    async def transcribe(self, source: dict) -> str:
        audio_path = await self._resolve(self._audio_fetcher(source))
        segments = self._segmenter(audio_path)
        transcript = await self._transcriber.transcribe_segments(segments)
        self._cleanup(audio_path, segments)
        return transcript
```

Key changes:
- `transcriber` is now a class instance, not a bare callable
- Concurrent execution handled inside the transcriber, not the pipeline
- Explicit cleanup of temp files after transcription

### VideoService Integration

No changes to `VideoService._transcribe_with_asr()`. It already calls `self._asr_pipeline.transcribe(source_dict)`.
The source dict `{"video_id": bvid, "source_url": ..., "title": ...}` is consumed by the audio_fetcher closure.

### Dependency Injection

File: `api/dependencies.py`

```python
async def get_asr_pipeline_dep(
    bili_client: BilibiliClient = Depends(get_bilibili_client_dep),
) -> AsrPipeline | None:
    asr_config = await get_asr_config()  # from app_settings
    if asr_config is None:
        return None

    provider = asr_config["provider"]
    api_key = resolve_asr_api_key(provider)  # reuse LLM provider key
    if not api_key:
        return None

    if provider == "zhipu":
        transcriber = ZhipuTranscriber(api_key=api_key)
        segment_seconds = 25
    elif provider == "qwen":
        transcriber = QwenTranscriber(api_key=api_key, base_url=asr_config.get("base_url"))
        segment_seconds = 270
    else:
        return None

    return AsrPipeline(
        audio_fetcher=_build_audio_fetcher(bili_client),
        segmenter=_build_segmenter(segment_seconds),
        transcriber=transcriber,
    )
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No ASR config or API key | `get_asr_pipeline_dep` returns None -> VideoService raises `VideoTranscriptUnavailableError` |
| Audio download fails | `NetworkError` propagated, VideoService catches -> status=failed |
| Audio has no audio stream | `BiliError` from get_audio_url -> status=failed |
| PyAV decode fails | `BiliError` from AudioProcessor -> status=failed |
| Single segment ASR fails after 3 retries | `AsrTranscriptionError` (new exception) -> status=failed |
| All segments succeed but empty text | `VideoTranscriptUnavailableError` -> status=failed |

All failures are caught by `VideoService.summarize()` existing error handler,
setting `summary.status = "failed"` and `summary.error_message`.

New exception:

```python
class AsrTranscriptionError(BiliError):
    """Raised when ASR API call fails after retries."""
```

---

## Temp File Management

ASR produces temporary files (downloaded audio, WAV segments). Cleanup strategy:

```python
async def transcribe(self, source: dict) -> str:
    temp_dir = tempfile.mkdtemp(prefix="asr_")
    try:
        audio_path = await self._audio_fetcher(source, temp_dir)
        segments = self._segmenter(audio_path, temp_dir)
        transcript = await self._transcriber.transcribe_segments(segments)
        return transcript
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
```

`tempfile.mkdtemp` ensures no collision across concurrent requests.
`finally` block ensures cleanup even on failure.

---

## Progress Events

During ASR, the pipeline emits progress events via VideoService's callback:

| Event | Stage | Data |
|-------|-------|------|
| `asr` | download | `{"step": "download", "video_id": bvid}` |
| `asr` | segment | `{"step": "segment", "segment_count": N}` |
| `asr` | transcribe | `{"step": "transcribe", "progress": "3/6"}` |
| `asr` | done | `{"step": "done"}` |

These are forwarded to the Studio panel SSE stream so the user sees transcription progress.

---

## File Layout

```
infrastructure/
  asr/                          [new directory]
    __init__.py                 [new] exports
    zhipu_transcriber.py        [new] Zhipu GLM-ASR adapter
    qwen_transcriber.py         [new] Qwen ASR-Flash adapter
    exceptions.py               [new] AsrTranscriptionError
  bilibili/
    audio_processor.py          [new] PyAV convert + split
    client.py                   [modify] add get_audio_url, download_audio
    asr.py                      [modify] refactor pipeline to use typed transcriber
```

---

## Dependency

Add to `pyproject.toml`:

```toml
"av>=14.0.0",
```

PyAV bundles FFmpeg as compiled extensions. No system FFmpeg installation required.
Supports m4s, AAC, MP3, WAV decoding and WAV encoding with resampling.
