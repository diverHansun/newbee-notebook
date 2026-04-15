# Video 模块 YouTube 扩展 -- 后端设计文档

## 模块定位

本目录描述 `newbee-notebook` 在 backend-v3 阶段为 Video 模块新增 YouTube 总结能力的后端设计。目标不是重做一套独立视频系统，而是在现有 Bilibili 视频总结链路上做平台扩展，并保持 Studio 与 `/video` runtime skill 共用同一条应用服务链路。

## 当前结论

1. YouTube 主链路使用 `yt-dlp` 获取元信息、字幕和音频。
2. 当 `yt-dlp` 未拿到可用字幕时，第二层借鉴仓内 `summarize/` 的思路，用 Python 解析页面里的 `captionTracks` / `youtubei player` 数据。
3. 最后一层复用现有 `AsrPipeline` 做兜底，确保“有字幕”和“无字幕”都能工作。
4. API 协议对外统一为 `url_or_id`，同时兼容历史字段 `url_or_bvid`。
5. Agent 范围仅扩到 `YouTube info + summarize`，不新增 YouTube 热门/搜索/推荐发现能力。

## 和现有代码的真实边界

- 数据库表 `video_summaries` 已有 `platform` 字段，YouTube 不需要额外迁移。
- `VideoService` 目前是 Bilibili 主导实现，YouTube 扩展的核心改动会落在 `application/services/video_service.py`。
- 现有 ASR pipeline 本身可复用，但依赖注入里的音频抓取目前是 Bilibili 专属，需要改成多平台音频获取。
- `/video` skill 目前文案和工具集明显偏 Bilibili，本次只补 YouTube 的 `get_video_info` 与 `summarize_video` 能力，不做 discovery。

## 设计原则

- 以现有稳定链路为基线，增量改造，不推翻 batch-6 Video 的既有实现。
- 先保证 summarize/info 跑通，再扩展更多 YouTube 细节能力。
- 兼容现有 API 与前端调用方式，避免一次性破坏性切换。
- 把平台差异收敛在基础设施层与服务层，不污染数据库和通用持久化逻辑。

## 文档清单

| 序号 | 文档 | 说明 |
|------|------|------|
| 01 | [01-goals-duty.md](01-goals-duty.md) | 设计目标、职责边界、非目标 |
| 02 | [02-architecture.md](02-architecture.md) | 架构收敛、数据流、模块边界 |
| 03 | [03-youtube-infrastructure.md](03-youtube-infrastructure.md) | YouTubeClient 与 transcript 链路 |
| 04 | [04-service-layer-changes.md](04-service-layer-changes.md) | VideoService、DI、Agent 侧改动 |
| 05 | [05-api-layer-changes.md](05-api-layer-changes.md) | 请求模型、SSE 事件、兼容策略 |
| 06 | [06-test.md](06-test.md) | 测试与验证策略 |

## 新增依赖

| 依赖 | 用途 |
|------|------|
| `yt-dlp` | YouTube 元信息提取、字幕链路、音频下载 |
| `httpx` | 第二层 HTML / `youtubei player` transcript 解析 |

## 关联文档

- 前端设计文档：[`../frontend/README.md`](../frontend/README.md)
- 实施计划：[`../implement/README.md`](../implement/README.md)
