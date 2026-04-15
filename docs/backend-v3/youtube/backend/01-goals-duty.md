# YouTube 扩展模块：设计目标与职责边界

## 1. 设计目标

### 1.1 在现有视频总结能力上平滑扩展 YouTube

YouTube 扩展必须复用现有 Video 模块的数据库、摘要持久化、SSE 推送、LLM 总结与 Notebook 关联能力，避免形成第二套“平台专用视频系统”。

### 1.2 三层 transcript 获取策略必须稳定降级

后端必须保证以下优先级：

1. `yt-dlp` 主链路
2. 借鉴 `summarize/` 的页面 / `captionTracks` / `youtubei player` transcript 解析链路
3. ASR 兜底

任何一层失败都不应直接终止总结流程，只在最终三层全部失败时才返回错误。

### 1.3 保持协议和前端的迁移平滑

新增 YouTube 后，对外字段统一语义为 `url_or_id`，但必须兼容历史的 `url_or_bvid`，避免老前端或现有测试用例一次性全部失效。

### 1.4 Agent 能力明确收敛

`/video` skill 的 YouTube 扩展只包含：

- 获取视频信息
- 生成/复用视频总结

不包含：

- 搜索
- 热门
- 排行
- 相关推荐

## 2. 职责

### 2.1 YouTubeClient

负责：

- 从 URL / ID 提取 YouTube 视频 ID
- 通过 `yt-dlp` 获取视频元信息
- 组织三层 transcript 获取链路
- 下载音频供 ASR 使用
- 对 YouTube 侧异常做模块内统一封装

### 2.2 VideoService

负责：

- 平台识别与平台路由
- `(platform, video_id)` 维度去重
- 复用摘要写库、对象存储、LLM 总结链路
- 接收 `lang` 并动态构建中英文总结 prompt
- 向 Studio / runtime 统一发出 SSE 进度事件

### 2.3 API 层

负责：

- 接收兼容字段 `url_or_id` / `url_or_bvid`
- 透传 `lang`
- 维持现有 SSE 输出协议，仅做增量扩展

### 2.4 Runtime Skill

负责：

- 在 `/video` prompt 中明确 YouTube 支持范围
- 对 YouTube URL / ID 使用 `get_video_info` 和 `summarize_video`

## 3. 非职责

- 不接入 YouTube Data API v3
- 不实现 YouTube 账号登录
- 不实现播放列表 / channel / 批量总结
- 不实现 YouTube discovery（search/hot/rank/related）
- 不新增数据库表
- 不重写已有 Bilibili summarize 链路

## 4. 约束与假设

- 部署环境需要具备访问 YouTube 的网络条件。
- `yt-dlp` 作为运行时依赖必须可用。
- ASR 兜底依赖现有音频切分和转写能力，不单独再做 YouTube 专属 ASR。
