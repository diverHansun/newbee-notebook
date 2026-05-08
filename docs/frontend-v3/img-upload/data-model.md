# img_upload 前端模块 data-model.md

本文档描述 `frontend-v3/img-upload` 前端模块在 TypeScript 层的核心概念与数据归属。

---

## 一、Core Concepts（核心概念）

### 1. Attachment

附件栏中的一项。表示"用户已选择、当前消息绑定、生命周期与本条消息编辑过程一致"的图片附件。

它有四态（`idle | uploading | ready | failed`）；同时持有本地 `File` 对象与（uploading 之后）由后端返回的 `image_id`。

### 2. Attachment Set

当前消息绑定的所有 Attachment 的集合。

集合是 `useChatImageUpload` hook 的内部 state，发送 / 切 session / 主动 reset 都会清空它。

### 3. Image Identifier

后端持久化身份，类型为 string（UUID）。

只有 `status === "ready"` 的 Attachment 才有 image_id。它是发送时拼入 `ChatRequest.image_ids` 的真值。

### 4. Local Preview Source

在前端用 `URL.createObjectURL(file)` 生成的本地 blob URL。

附件栏的缩略图始终从它取；卡片 unmount 或 attachment 移除时必须 `URL.revokeObjectURL` 释放。

### 5. Remote Preview Source

后端 `GET /api/v1/chat/images/{id}/thumbnail` 路径。

仅在历史回看场景使用——历史消息中的图没有原始 File 对象，必须从后端拉。

### 6. Send Gate Predicate

每次渲染时由 Attachment Set 派生的布尔：
```
sendDisabled = !text.trim()
            || (attachments.length > 0 && attachments.some(a => a.status !== "ready"))
```

它是"门禁"的运行期实现，不持久化。

### 7. ChatRequest with image_ids

前端 ChatRequest payload 的扩展形态。

`image_ids: string[]` 是新增字段，仅在 mode ∈ {agent, ask} 且 attachments 非空时携带。

### 8. History Image Reference

聊天历史中某条消息的 `image_ids` 字段，由后端返回。

与 backend data-model "Image Reference" 概念对应；前端只读，渲染为缩略图卡片网格。

---

## 二、Entity / Value Object 区分

### Entity

| 概念 | 身份 | 生命周期 |
|------|------|----------|
| Attachment | 客户端临时 id（如 `crypto.randomUUID`）+ 上传成功后绑定 image_id | 选图加入 → 上传 → 发送或主动移除 → 销毁 |

### Value Object

| 概念 | 说明 |
|------|------|
| Attachment Set | useReducer state，每次操作产出新引用 |
| Image Identifier | 后端给的字符串，前端只读 |
| Local Preview Source | ObjectURL 字符串 + 释放契约 |
| Remote Preview Source | URL 字符串，由 image_id 拼出 |
| Send Gate Predicate | 渲染期派生 |
| ChatRequest with image_ids | 网络层即时构造 |
| History Image Reference | history 数据的一个字段 |

---

## 三、Key Data Fields（关键数据字段）

### Attachment

- `id`：客户端 ID。用于 React key、retry 时定位、reducer action 目标。
- `file`：原始 `File` 对象。
- `localUrl`：`URL.createObjectURL(file)`，用作缩略图 src。
- `status`：`"idle" | "uploading" | "ready" | "failed"`。
- `progress`：可选，上传进度（0–100）。
- `imageId`：仅 `status === "ready"` 时存在。
- `width` / `height`：可选，由上传响应填充，用于卡片纵横比。
- `mimeType`：客户端预校验时填充。
- `sizeBytes`：客户端预校验时填充。
- `errorCode` / `errorMessage`：仅 `status === "failed"` 时存在；展示于卡片错误层。

### Attachment Set Operations

- `add(files: File[])`：批量加入；每个 file 经客户端校验后产出 `idle` 项；自动触发 upload。
- `retry(id)`：把 `failed` 项重置为 `uploading` 并再次发起 POST。
- `remove(id)`：移出集合；revoke 本地 ObjectURL。
- `reset()`：发送成功后清空整个集合，逐项 revoke。

### ChatRequest 扩展

```ts
interface ChatRequest {
  message: string;
  mode: "agent" | "ask" | "explain" | "conclude";
  session_id?: string;
  context?: ChatContext;
  source_document_ids?: string[];
  lang?: "en" | "zh";
  image_ids?: string[];   // 新增；仅 mode ∈ {agent, ask} 且 ready 集合非空时携带
}
```

### History Image Reference 渲染输入

- `image_ids: string[]`：来自后端历史响应。
- 用于渲染：每个 id → `<img src=/api/v1/chat/images/{id}/thumbnail>`。
- 点击放大：`<img src=/api/v1/chat/images/{id}/data>` 在 `<dialog>` 内显示。

### Local Preview Source 释放契约

- 创建时：`add` action 内部 `URL.createObjectURL(file)`。
- 释放时机：
  - `remove(id)` 立即释放
  - `reset()` 对集合中所有 attachment 释放
  - hook unmount 时对集合中所有 attachment 释放
- 不释放将导致内存泄漏；测试需要锁定上述三条路径。

---

## 四、Lifecycle & Ownership（生命周期与归属）

### Attachment 生命周期

1. 用户通过 4 类入口产出 `File[]`。
2. `useChatImageUpload.add(files)` 客户端校验并构造 idle Attachment + ObjectURL。
3. hook 立即对每张图调度 `uploadChatImages` POST。
4. POST 成功 → `status="ready"` + `imageId` 落入 reducer state。
5. POST 失败 → `status="failed"` + `errorCode/Message` 落入 reducer state。
6. 用户可重试 / 移除。
7. 发送 chat 时，attachments 的 ready 项 image_id 拼入 ChatRequest；hook reset 清空集合。

归属：`useChatImageUpload`。

### Attachment Set 归属

- 创建：chat-input mount 或新会话切换时 hook 初始化空集合。
- 销毁：chat-input unmount 或主动 reset。
- 与 Zustand chat-store 的关系：**独立**，不进 store；store 不知道附件存在。

### History Image Reference 归属

- 创建：后端历史 API 返回。
- 不可变：前端不修改、不重传。
- 点击查看大图时新建 `<dialog>` 视图，本地 state，关闭即销毁。

### ChatRequest with image_ids 归属

- 由 chat-input 提交 handler 即时构造，调用 useChatStream 现有 mutation。
- 不持久化。

---

## 五、数据边界

### 本前端模块拥有

- Attachment / Attachment Set 的形态与状态机。
- Send Gate Predicate 派生规则。
- Local Preview Source 的释放契约。
- ChatRequest.image_ids 字段在前端 payload 的位置语义。

### 本前端模块不拥有

- 后端 `chat_images` 表的字段、生命周期、跨会话边界（属于 backend img_upload）。
- StorageBackend 的对象 key 命名与缩放策略。
- ChatService 的 vision_fallback 决策。
- 现有 `image-card-list` 用于渲染 generated images 的逻辑。
- `useChatStream` 的 SSE 解析机制（仅扩展其请求 payload）。

---

## 六、数据安全约束

1. 任何前端日志（console / Sentry / 自带埋点）都不允许打印 Attachment.file 的 base64 或 ObjectURL。
2. ChatRequest 提交时只携带 image_ids，绝不携带 base64。
3. 发送失败或用户删除附件时必须释放 ObjectURL，否则在长会话中会持续泄漏内存。
4. 历史回看的 `<img src=/api/v1/chat/images/...>` 必须使用同源带 cookie（或 token）路径，依赖现有 `apiFetch` 的鉴权约定，不允许把 image_id 拼成无鉴权的公网 URL。
