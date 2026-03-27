# Video 前端模块：数据流与接口设计

## 1. 上下文与范围

本文档描述 Video 前端模块与外部的交互方式，包括：API client 如何调用后端 REST API、如何消费 SSE 进度流、组件之间如何通过 props 和回调传递数据。

前端模块位于 Studio 面板内部，其外部依赖包括：

- 后端 Video REST API 和 SSE 端点
- 后端 B站认证相关 API
- Studio 面板的全局状态（studio-store）
- chat-store（当 /video 斜杠命令被激活时）

## 2. 数据流描述

### 2.1 视频总结触发与进度推送

```
用户输入 URL
    │
    v
VideoInputArea 组件
    │  state: inputValue
    v
用户点击「总结」按钮
    │
    v
API: POST /api/v1/videos/summarize
body: { url: string, notebook_id?: string }
    │
    +----> SSE 连接建立（fetch + ReadableStream）
    |         │
    |         v
    |     解析 SSE 事件
    |         │
    |         +-- event: processing --> 更新 step indicator（currentStep）
    |         +-- event: error --> 显示错误 + 重试按钮
    |         +-- event: completed --> 刷新列表 cache
    |         +-- event: done --> 复原输入区域状态
    |
    +----> HTTP 响应（summary_id）
              │
              v
          queryClient.invalidateQueries(["video-summaries", "all"])
```

注意：POST /api/v1/videos/summarize 返回 HTTP 202 Accepted，body 包含 `{ summary_id, task_id }`。实际进度通过 SSE 推送，最终完成时 SSE 发送 `completed` 或 `error` 事件。

### 2.2 Agent 工具调用后的数据刷新

```
用户输入 /video xxx
    │
    v
SlashCommandHint 选中 /video
    │
    v
ChatInput 切换到 AGENT 模式
    │
    v
AgentLoop 执行 VideoSkillProvider 工具
    │
    v
工具内部调用 VideoService.summarize()
    │
    v
VideoService 创建 VideoSummary 实体
    │
    v
AgentLoop 返回工具结果（tool_result 事件）
    │
    v
chat-store 收到 tool_result
    │
    v
queryClient.invalidateQueries(["video-summaries", "all"])
    │
    v
VideoListView 自动重新拉取（如果当前可见）
```

这个流程中，前端不需要感知 agent 工具调用的细节，只需要通过缓存失效机制确保数据同步。

### 2.3 B站登录流程

```
用户点击「B站登录」按钮
    │
    v
显示登录弹窗（QR 码）
    │
    v
前端建立 SSE 连接（轮询 QR 状态）
GET /api/v1/bilibili-auth/qr/status
    │
    +---> 扫码中：显示 "等待扫码"
    +---> 已扫描：显示 "已扫码，等待确认"
    +---> 已确认：关闭弹窗，刷新 auth 状态
    +---> 已过期：显示 "二维码已过期"，提供刷新按钮
```

登录状态通过 `useBilibiliAuth()` hook 管理，返回 `BilibiliAuthState` 类型。VideoInputArea 接收该状态并渲染对应的 UI。

### 2.4 Notebook 关联操作

```
用户点击详情页「关联到笔记本」按钮
    │
    v
useAssociateVideoSummary mutation
    │
    v
PATCH /api/v1/videos/summaries/:id/associate
body: { notebook_id: string }
    │
    v
成功 --> queryClient.invalidateQueries(["video-summaries", 当前 notebookId])
    │
    v
前端派生字段 is_associated 更新
```

## 3. 接口定义

### 3.1 API Client 函数（lib/api/videos.ts）

#### 3.1.1 listAllVideoSummaries

获取用户全部视频摘要列表。

```
输入：无参数，或 { sort_by?, order? }
输出：Promise<VideoListResponse>
方法：GET /api/v1/videos/summaries
```

#### 3.1.2 listVideoSummaries

获取当前 notebook 关联的视频摘要。

```
输入：{ notebook_id: string, sort_by?: VideoSortField, order?: VideoSortOrder }
输出：Promise<VideoListResponse>
方法：GET /api/v1/videos/summaries?notebook_id=xxx
```

#### 3.1.3 getVideoSummary

获取单条摘要详情。

```
输入：summary_id
输出：Promise<VideoSummary>
方法：GET /api/v1/videos/summaries/:summary_id
```

#### 3.1.4 deleteVideoSummary

删除视频摘要。

```
输入：summary_id
输出：Promise<void>
方法：DELETE /api/v1/videos/summaries/:summary_id
```

#### 3.1.5 summarizeVideo

触发视频总结（不等待完成，返回 task_id）。

```
输入：{ url: string, notebook_id?: string }
输出：Promise<{ summary_id: string; task_id: string }>
方法：POST /api/v1/videos/summarize
```

#### 3.1.6 associateVideoSummary

关联摘要到 notebook。

```
输入：{ summary_id: string, notebook_id: string }
输出：Promise<VideoSummary>
方法：PATCH /api/v1/videos/summaries/:summary_id/associate
```

#### 3.1.7 disassociateVideoSummary

取消摘要与 notebook 的关联。

```
输入：summary_id
输出：Promise<VideoSummary>
方法：PATCH /api/v1/videos/summaries/:summary_id/disassociate
```

#### 3.1.8 getVideoInfo

获取视频元信息（不触发总结）。

```
输入：{ url: string }
输出：Promise<{ bvid: string; title: string; cover_url: string; ... }>
方法：GET /api/v1/videos/info
```

### 3.2 API Client 函数（lib/api/bilibili-auth.ts）

#### 3.2.1 getBilibiliAuthState

查询当前 B站登录状态。

```
输入：无
输出：Promise<BilibiliAuthState>
方法：GET /api/v1/bilibili-auth/state
```

#### 3.2.2 createBilibiliQrLogin

发起 QR 码登录，获取二维码。

```
输入：无
输出：Promise<{ qr_id: string; qr_url: string; image_base64: string }>
方法：POST /api/v1/bilibili-auth/qr/create
```

#### 3.2.3 pollBilibiliQrStatus

轮询扫码状态。

```
输入：qr_id
输出：Promise<{ status: "waiting" | "scanned" | "confirmed" | "expired", username?: string }>
方法：GET /api/v1/bilibili-auth/qr/status?qr_id=xxx
```

#### 3.2.4 logoutBilibili

登出 B站账号。

```
输入：无
输出：Promise<void>
方法：POST /api/v1/bilibili-auth/logout
```

### 3.3 SSE 连接接口

#### 3.3.1 summarizeVideoSSE

建立 SSE 连接接收总结进度。

```
URL: POST /api/v1/videos/summarize/stream
Header: Content-Type: application/json
Body: { url: string, notebook_id?: string }
响应：text/event-stream
```

发送的事件序列：

```
1. event: processing, step: "获取视频信息"
2. event: processing, step: "获取字幕"
3. event: processing, step: "AI 生成总结"
4. event: completed, summary_id: "xxx", status: "success"
   或
4. event: error, message: "获取字幕失败"
5. event: done, total: 1, success: 1, ...
```

## 4. 数据归属与责任

### 4.1 前端责任

- 管理用户输入的 URL 和 UI 状态
- 调用总结 API 并建立 SSE 连接
- 解析 SSE 事件并更新 UI
- 调用 CRUD API 并处理响应
- 通过 TanStack Query 缓存失效确保数据一致性

### 4.2 后端责任

- 验证 URL 格式和 BV 号合法性
- 调用 Bilibili API 获取视频信息和字幕
- 执行 ASR 转录（当无字幕时）
- 调用 LLM 生成总结
- 持久化 VideoSummary 实体
- 管理 B站登录凭证
- 发送 SSE 进度事件

### 4.3 TanStack Query 缓存责任

- 列表数据由 query 自行管理，前端通过 `invalidateQueries` 主动失效
- SSE 完成后，前端显式调用 `invalidateQueries` 确保列表最新
- agent 工具调用完成后，由前端显式 `invalidateQueries`（通过 chat-store 的 SSE 消费逻辑）

## 5. 错误处理接口

### 5.1 API 错误响应格式

后端 API 错误响应的格式为：

```typescript
type ApiErrorResponse = {
  error_code: string;
  message: string;
  detail?: unknown;
};
```

前端通过 `apiFetch` 底层统一处理非 2xx 响应，抛出统一异常。组件通过 `onError` 回调处理。

### 5.2 SSE 错误事件

SSE 连接中的错误通过 `SseEventError` 事件传递。前端在消费 SSE 时：

```typescript
if (event.event === "error") {
  setError(event.message);
  setPhase("error");
}
```

前端不主动关闭 SSE 连接（由后端控制连接生命周期）。前端在组件卸载时中止 `ReadableStream`。

### 5.3 网络错误处理

- SSE 连接建立失败：显示 "连接失败，请重试"
- SSE 传输中断（网络波动）：不自动重连，用户手动重试
- API 请求失败：通过 TanStack Query 的 `onError` 处理，显示 toast 或内联错误

## 6. 组件间通信

### 6.1 Props 传递

父组件向子组件通过 props 传递数据，子组件通过回调向上传递事件：

```
StudioPanel
    │
    ├── navigateTo / openVideoDetail 等方法
    │
    └── VideoListView (notebookId)
            │
            ├── VideoInputArea (notebookId, authState, onLoginClick)
            │       │
            │       └── 内部管理 SSE 状态和进度
            │
            └── VideoListItem[] (summary, isAssociated, onClick)
                    │
                    └── onClick --> openVideoDetail(summary.summary_id)
```

### 6.2 回调签名

```typescript
type onLoginClick = () => void;
type onVideoClick = (summaryId: string) => void;
type onDeleteConfirm = (summaryId: string) => void;
type onAssociate = (summaryId: string) => void;
type onDisassociate = (summaryId: string) => void;
```
