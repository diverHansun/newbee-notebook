# Video 前端模块：验证策略

## 1. 测试范围

### 1.1 覆盖范围

- Video 组件（video-list.tsx、video-detail.tsx、video-input-area.tsx 等）的渲染
- API client 函数（lib/api/videos.ts、lib/api/bilibili-auth.ts）
- TanStack Query hooks（lib/hooks/use-videos.ts、lib/hooks/use-bilibili-auth.ts）
- studio-store 的 Video 导航状态扩展
- SlashCommandHint 中的 /video 命令条目
- i18n 键（video 命名空间及补充条目）

### 1.2 不在测试范围内

- 后端 API 的正确性（由后端模块负责）
- Bilibili 平台的行为（第三方依赖）
- Markdown 渲染组件的正确性（复用已有组件）
- TanStack Query 本身的缓存机制
- 现有 Studio 面板组件（Notes、Diagrams）的已有行为

## 2. 关键场景

### 2.1 视频总结触发流程

**场景**：用户在 Video 输入框输入有效 URL，点击「总结」按钮。

**预期行为**：

1. 输入框立即禁用，按钮文字变为"总结中..."
2. step indicator 显示第一个步骤
3. 收到 `processing` 事件后，step indicator 高亮对应步骤
4. 收到 `completed` 事件后，输入框恢复可用，列表顶部出现新条目
5. 收到 `error` 事件后，显示错误文字和重试按钮

**验证方式**：使用 MSW（Mock Service Worker）拦截 API 请求和 SSE 事件，按序返回模拟事件序列。验证 UI 状态变化符合预期。

### 2.2 无效 URL 提交

**场景**：用户在 Video 输入框输入无效字符串（如 "hello world"），点击「总结」。

**预期行为**：前端校验不通过，输入框下方显示错误提示"请输入有效的 Bilibili URL 或 BV 号"，不调用 API。

**验证方式**：单元测试，直接调用校验函数或渲染组件后模拟输入和点击。

### 2.3 列表加载与空状态

**场景**：Video 视图挂载时，用户没有任何摘要。

**预期行为**：显示空状态插画和提示文字，不显示 skeleton 以外的列表内容。

**验证方式**：MSW 拦截返回空列表，验证空状态渲染。

### 2.4 列表筛选切换

**场景**：用户在 Video 列表视图点击筛选器，从「全部」切换为「当前笔记本」。

**预期行为**：列表数据从 `useAllVideoSummaries` 切换到 `useVideoSummaries(notebookId)`，列表内容更新。

**验证方式**：MSW 返回不同数据，验证渲染内容符合预期。

### 2.5 摘要详情加载

**场景**：用户点击列表条目，导航到详情页。

**预期行为**：详情页正确显示视频信息头、Markdown 摘要内容、关联按钮状态。

**验证方式**：MSW 返回完整摘要数据，验证详情页渲染。

### 2.6 删除确认流程

**场景**：用户在详情页点击「删除」，在 ConfirmDialog 中确认。

**预期行为**：删除成功后，自动导航回列表，列表中不再包含该条目。

**验证方式**：MSW 拦截 DELETE 请求返回成功，验证路由状态和列表 cache 均已更新。

### 2.7 Notebook 关联操作

**场景**：用户在详情页点击「关联到笔记本」。

**预期行为**：关联成功后，按钮文字变为「取消关联」，列表条目右上角显示已关联图标。

**验证方式**：MSW 拦截 PATCH 请求返回更新后的摘要数据，验证本地派生字段 `is_associated` 正确。

### 2.8 B站登录流程

**场景**：用户点击「B站登录」，扫码并确认。

**预期行为**：弹窗正确展示 QR 码，轮询状态更新 UI，最终登录成功后弹窗关闭，登录按钮变为用户名显示。

**验证方式**：MSW 拦截 QR 创建和轮询请求，按序返回不同状态，验证 UI 状态变化。

### 2.9 SSE 错误处理

**场景**：总结过程中 SSE 收到 `error` 事件。

**预期行为**：step indicator 下方显示红色错误文字 + 重试按钮，输入框恢复可用。

**验证方式**：MSW 返回 error 事件，验证错误展示和 UI 状态。

### 2.10 /video 斜杠命令

**场景**：用户在聊天输入框输入 `/video`。

**预期行为**：SlashCommandHint 面板正确显示 `/video` 命令条目，描述文字正确。

**验证方式**：单元测试，传入 `/video` 输入，验证过滤结果包含 `/video` 条目。

## 3. 集成点测试

### 3.1 studio-store 集成

验证 studio-store 的 Video 导航方法正确更新状态：

- `openVideoDetail(videoId)` 将 `studioView` 设为 `"video-detail"`，`activeVideoId` 设为对应值
- `backToVideoList()` 将 `studioView` 设为 `"videos"`，`activeVideoId` 设为 null

### 3.2 TanStack Query 缓存失效

验证各 mutation 正确失效对应的 query key：

- `useDeleteVideoSummary` 成功后应失效 `ALL_VIDEO_SUMMARIES_QUERY_KEY` 和 `VIDEO_SUMMARY_QUERY_KEY(deletedId)`
- `useAssociateVideoSummary` 成功后应失效 `VIDEO_SUMMARIES_QUERY_KEY(notebookId)`

### 3.3 SSE 与 API 的协调

验证 SSE `completed` 事件触发时，列表 cache 被正确刷新，使得新创建的摘要立即出现在列表中。

## 4. 验证策略

### 4.1 测试工具

- **Vitest**：单元测试和组件测试
- **React Testing Library**：组件渲染测试和用户交互模拟
- **MSW（Mock Service Worker）**：拦截 HTTP 请求和 SSE 事件，返回可控的模拟数据

### 4.2 测试分层

**单元测试**：API client 函数的输入输出映射，如 URL 校验逻辑、请求参数构造。

**组件测试**：Video 组件的渲染和交互。使用 MSW 拦截真实网络请求，验证组件在给定数据下的渲染结果和用户交互后的行为。

**集成测试**：多个组件串联的场景，如从列表导航到详情、从详情删除返回列表。使用真实 store（zustand）和 MSW。

### 4.3 Mock 策略

- HTTP API：使用 MSW 拦截，`lib/api/videos.ts` 和 `lib/api/bilibili-auth.ts` 中的请求
- SSE 事件：通过 MSW 的 `sseCallback` 或类似机制按序发送模拟事件
- 后端依赖：不 mock Bilibili 平台，也不 mock 后端 VideoService
- TanStack Query：使用 `QueryClientProvider` 的测试实例

### 4.4 关键验证指标

- 组件在给定 props 下正确渲染对应内容
- 用户交互（点击、输入）触发正确的 API 调用
- API 响应正确更新 UI 状态
- 错误状态（网络错误、API 错误）正确展示错误信息
- 导航状态正确流转（videos <-> video-detail）

### 4.5 不追求的指标

- 不追求测试覆盖率数字
- 不追求边界情况的穷举覆盖（由 E2E 测试和用户反馈补充）
- 不测试第三方库本身的行为（如 TanStack Query 的缓存淘汰策略）
