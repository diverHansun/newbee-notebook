# YouTube 扩展实施计划

## 目标

按“先文档对齐、再实现主链路、最后补回归验证”的顺序推进 YouTube summarize。

## 实施顺序

### Phase 1：协议与服务收敛

- `SummarizeRequest` 支持 `url_or_id + lang`
- 保留 `url_or_bvid` 兼容
- `VideoService` 支持平台识别与 YouTube summarize 分支
- `fetch_video_info()` 支持 YouTube

### Phase 2：YouTube 基础设施

- 新增 `infrastructure/youtube/`
- `yt-dlp` 元信息、字幕、音频下载
- `captionTracks / youtubei player` fallback
- 与 ASR pipeline 联动

### Phase 3：前端 Studio

- 单输入框自动识别平台
- 动态平台状态条
- 支持 `info` 事件
- 双维筛选与平台 badge
- 文案升级为多平台

### Phase 4：Runtime Skill

- `/video` prompt 与工具说明补充 YouTube 能力边界
- `get_video_info` 与 `summarize_video` 支持 YouTube 输入

### Phase 5：验证

- 后端单测
- 前端单测
- Bilibili 回归
- YouTube 手动验证

## 交付物

- backend 设计文档
- frontend 设计文档
- 实现代码
- 更新后的测试
