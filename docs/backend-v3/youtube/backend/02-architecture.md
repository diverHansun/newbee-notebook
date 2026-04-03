# YouTube 扩展模块：架构变更与数据流

## 1. 总体架构

本次扩展不新增新的业务服务入口，Studio 与 `/video` skill 继续共用 `VideoService`。

```text
Studio Video / Runtime /video
            |
            v
        VideoService
            |
     +------+------+
     |             |
 BilibiliClient  YouTubeClient
     |             |
  subtitle/asr   tier1/tier2/asr
            \     /
             \   /
            LLM + Storage + video_summaries
```

## 2. 关键模块变化

### 2.1 新增 `infrastructure/youtube/`

新增 YouTube 平台基础设施层，负责：

- URL / ID 识别
- 元信息提取
- transcript 三层链路
- 音频下载
- YouTube 特有异常

### 2.2 扩展 `VideoService`

`VideoService` 增加：

- `_detect_platform(url_or_id)`
- YouTube summarize 分支
- `lang` 支持
- 对 YouTube 的 `fetch_video_info`

### 2.3 扩展 ASR 依赖注入

现有 `AsrPipeline` 继续复用，但 `audio_fetcher` 不能再只依赖 `bili_client`。依赖注入需升级为“按 source 中的平台字段分发抓音频”。

## 3. 总结数据流

```text
input(url_or_id, notebook_id, lang)
        |
        v
_detect_platform()
        |
        +--> bilibili --> 现有 Bilibili 逻辑
        |
        +--> youtube
              |
              v
      YouTubeClient.extract_video_id()
              |
              v
      repo.get_by_platform_and_video_id("youtube", video_id)
              |
              v
      YouTubeClient.get_video_info()
              |
              v
      YouTubeClient.get_transcript()
        |          |            |
        |          |            +--> (None, "asr") --> AsrPipeline
        |          +--> tier2 captionTracks / youtubei
        +--> tier1 yt-dlp
              |
              v
      storage.save_file(transcript)
              |
              v
      llm_client.chat(messages(lang))
              |
              v
      repo.update(status="completed")
```

## 4. SSE 事件设计

YouTube 路径继续使用现有事件模型，只做增量扩展：

- `start`
- `info`
- `subtitle`
- `asr`
- `summarize`
- `done`
- `error`

其中：

- `start` 保持现有“进入处理流程”的语义
- `info` 用于传元信息，前端可用来展示 metadata preview
- `subtitle` 增加 `source`

## 5. 为什么不新增抽象基类

本次实现阶段不强行抽 `PlatformClient` 抽象基类，原因是：

- 当前只扩到两个平台
- Bilibili 的 discovery 能力和 YouTube 的 summarize 能力并不对称
- 先让 service 层平台分支清晰落地，比过早抽象更稳

后续如果再接入第三个平台，再考虑统一 adapter 接口。
