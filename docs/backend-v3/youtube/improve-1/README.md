# YouTube Improve-1

## 目标

本轮只处理 YouTube 视频总结链路，目标如下：

1. `yt-dlp` 改为软依赖，缺失或失败时继续走 HTTP + ASR fallback。
2. YouTube 处理中 summary 不出现在列表里，前端只依赖输入区 spinner 展示进度。
3. metadata 获取失败不阻断 summarize。
4. 若最终 ASR + summarize 成功，但 metadata 仍不完整：
   - 标题使用 `video_id`
   - 隐藏时长与作者 chip
   - 保留正常卡片布局与已完成状态
5. 本轮不改 Bilibili 行为。

## 问题分析

### 1. `yt-dlp` 仍是音频下载硬依赖

当前 YouTube 的 transcript 已具备部分降级能力，但 ASR 音频下载仍直接依赖 `yt-dlp`。结果是：

- `get_video_info()` 可降级
- `get_transcript()` 可降级
- `download_audio()` 仍会因 `yt-dlp` 缺失直接失败

这会导致 summarize 虽然能越过 metadata 阶段，但仍在 ASR 阶段中断。

### 2. processing summary 过早暴露给列表

后端在进入 summarize 后会先创建 `processing` 记录，并用默认值填充：

- `title = video_id`
- `duration_seconds = 0`
- `uploader_name = ""`

前端又会在早期 SSE 事件触发列表刷新，导致 processing 卡片以占位信息出现在 UI 中。

### 3. 缺少 metadata readiness 契约

当前 API 只返回 metadata 字段本身，没有表达：

- 这些字段是否可靠
- 是否只是 fallback 占位值

因此前端无法区分“真实 metadata”与“为了不中断流程写入的最小 metadata”。

## 本轮决策

### 1. `yt-dlp` 作为可选加速层

YouTubeClient 的三条能力统一采用 best-effort 多层链路：

- metadata: `yt-dlp` -> watch page
- transcript: `yt-dlp` -> watch page caption tracks -> ASR
- audio: `yt-dlp` -> watch page streaming data -> `youtubei/player`

只有所有链路都失败时，才真正中断 summarize。

### 2. processing YouTube summary 从列表中隐藏

YouTube summary 在 `status=processing` 时，不返回给列表接口。

这样可以避免 processing 阶段出现占位卡片。进度反馈完全交给 SSE spinner。

### 3. 新增 `metadata_ready` 响应语义

不改数据库结构，本轮通过已有字段派生出 `metadata_ready`：

- `true`: metadata 可视为真实可展示
- `false`: metadata 为占位或明显不完整

该字段进入 list/detail response，供前端决定是否显示作者和时长 chip。

### 4. minimal metadata 不发 `info` 事件

当 summarize 只能拿到最小 metadata 时：

- 后端仍继续执行 transcript / ASR / summarize
- 但不发送 `info` SSE 事件
- 前端输入区不展示占位 metadata 预览

## 实施方案

### 后端

1. `YouTubeClient`
   - `download_audio()` 改为多层 fallback
   - 新增 watch page `streamingData` 音频 URL 解析
   - 新增 `youtubei/player` 音频 URL fallback
   - `yt-dlp` 失败只记录日志，不直接向上暴露依赖错误

2. `VideoService`
   - 保留 metadata 失败后继续 summarize 的能力
   - 增加 metadata readiness 判断
   - minimal metadata 时不发 `info` 事件
   - `list_all()` / `list_by_notebook()` 隐藏 processing 的 YouTube summary

3. Video API
   - list/detail response 增加 `metadata_ready`
   - 由后端基于 summary 字段动态计算

### 前端

1. `VideoInputArea`
   - YouTube summarize 期间不依赖列表卡片反馈
   - spinner 继续按 SSE 事件即时更新
   - `done` / `error` 再刷新列表

2. `VideoListItem` / `VideoDetail`
   - `metadata_ready=false` 且平台为 YouTube 时：
     - 显示标题
     - 隐藏作者 chip
     - 隐藏时长 chip
     - 其它布局保持不变

## 非目标

1. 本轮不修改 Bilibili summarize 展示策略。
2. 本轮不为 processing YouTube summary 增加“隐藏但可恢复”的持久任务栏。
3. 本轮不重做 `/videos/info` 单独接口的展示体验。

## 测试范围

测试放在 `newbee_notebook/tests/` 下，重点覆盖：

1. YouTube summarize 在 metadata 失败后仍可走 ASR 完成。
2. YouTube processing summary 不出现在列表结果中。
3. YouTubeClient 在 `yt-dlp` 失败后继续走 HTTP 音频下载 fallback。
4. API / service 层返回 `metadata_ready` 语义正确。
