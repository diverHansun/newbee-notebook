# VideoService、依赖注入与 Agent 变更

## 1. VideoService 改动

### 1.1 summarize 签名

`summarize()` 从单平台参数升级为多平台兼容参数：

```python
async def summarize(
    self,
    url_or_id: str,
    *,
    notebook_id: str | None = None,
    lang: Literal["zh", "en"] = "zh",
    progress_callback: ProgressCallback | None = None,
) -> VideoSummary:
```

## 2. 平台检测

`VideoService` 增加 `_detect_platform(url_or_id)`：

- YouTube URL / 11 位 ID -> `youtube`
- 其余仍按 Bilibili 处理

## 3. summarize 路由

### 3.1 Bilibili

保持现有逻辑。

### 3.2 YouTube

YouTube 分支负责：

- `extract_video_id`
- `(platform="youtube", video_id)` 去重
- `get_video_info`
- `get_transcript(lang_hint=lang)`
- 必要时 `_transcribe_with_asr()`
- 构建 `lang` 对应的 LLM prompt

## 4. `_transcribe_with_asr()` 改造

现有 `_transcribe_with_asr()` 只传 `video_id/source_url/title`，默认 audio_fetcher 里按 Bilibili 方式下载音频。现在需要把 `platform` 一并传入：

```python
{
    "platform": "youtube",
    "video_id": video_id,
    "source_url": ...,
    "title": ...,
}
```

依赖注入中的 `audio_fetcher` 根据 `platform` 分发到 Bilibili 或 YouTube 的音频下载实现。

## 5. `fetch_video_info()` 扩展

`fetch_video_info()` 需要支持 YouTube，以满足 `/video` runtime skill 的 `info` 能力。

## 6. 动态语言 prompt

`_build_summary_messages()` 改为接收 `lang`：

- `zh` 输出中文结构化摘要
- `en` 输出英文结构化摘要

默认仍为中文，保证旧调用方不传 `lang` 也能工作。

## 7. 依赖注入变更

`api/dependencies.py` 需要：

- 新增 `get_youtube_client_dep()`
- `get_asr_pipeline_dep()` 接收 `bili_client + youtube_client`
- `get_video_service()` 注入 `youtube_client`

## 8. Runtime Skill 变更

`skills/video/provider.py` 与 `skills/video/tools.py` 需要明确：

- YouTube 只支持 `get_video_info`
- YouTube 只支持 `summarize_video`
- discovery / ai_conclusion 继续是 Bilibili 能力

本次不删现有 Bilibili discovery，只补 YouTube 能力边界说明与多平台输入支持。
