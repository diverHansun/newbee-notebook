# YouTube 基础设施层详细设计

## 1. 目录结构

```text
newbee_notebook/infrastructure/youtube/
├── __init__.py
├── client.py
├── exceptions.py
└── parsers.py
```

本次先保持精简目录，把核心逻辑放在 `client.py`，解析辅助方法放在 `parsers.py`。

## 2. YouTubeClient 对外接口

建议接口如下：

```python
class YouTubeClient:
    def is_youtube_input(self, value: str) -> bool: ...
    def extract_video_id(self, value: str) -> str: ...
    async def get_video_info(self, video_id: str) -> dict[str, Any]: ...
    async def get_transcript(self, video_id: str, *, lang_hint: str | None = None) -> tuple[str | None, str]: ...
    async def download_audio(self, video_id: str) -> str: ...
```

## 3. Tier 1：`yt-dlp` 主链路

### 3.1 用途

- 获取视频标题、时长、封面、频道名
- 获取可用字幕轨道
- 下载音频供 ASR 使用

### 3.2 transcript 策略

第一层不必强依赖 CLI 文件输出，也可以直接使用 `yt-dlp` 返回的 subtitle metadata：

- 手动字幕优先于自动字幕
- 优先尝试与 `lang_hint` 接近的语言
- 再回落到中英文常用语言顺序

若拿到字幕 URL，则下载并解析对应内容。

## 4. Tier 2：借鉴 `summarize/` 的 transcript 解析链路

### 4.1 借鉴范围

借鉴仓内 `summarize/packages/core/src/content/transcript/providers/youtube/` 的思路，而不是直接依赖其 Node 运行时：

- 页面 HTML 中提取 `ytInitialPlayerResponse`
- 读取 `playerCaptionsTracklistRenderer.captionTracks`
- 必要时请求 `youtubei/v1/player`
- 优先下载 `json3`，失败再回退 XML

### 4.2 Python 实现要求

- 只复用思路，不引入 summarize npm 依赖
- 解析器保持纯函数，便于单测
- 失败时静默回退到 ASR

## 5. Tier 3：ASR 音频兜底

当 transcript 两层都失败时，YouTubeClient 只负责下载音频，不负责直接转写。转写仍走现有 `AsrPipeline`。

## 6. 解析器能力

`parsers.py` 需要覆盖：

- `extract_initial_player_response(html)`
- `extract_caption_tracks(payload)`
- `pick_best_track(tracks, lang_hint)`
- `parse_json3_transcript(raw)`
- `parse_xml_transcript(raw)`
- `parse_vtt_transcript(raw)`
- `parse_srt_transcript(raw)`

## 7. 异常层级

```text
YouTubeError
├── InvalidYouTubeInputError
├── InvalidYouTubeVideoIdError
├── YouTubeVideoUnavailableError
└── YouTubeNetworkError
```

说明：

- transcript 两层失败不应抛出 `YouTubeError` 终止流程，应返回 `(None, "asr")`
- 只有输入非法、视频不可用、完全无法下载音频等场景才真正中断 summarize
