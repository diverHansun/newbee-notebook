# img_upload 前端模块 dfd-interface.md

本文档描述 `frontend-v3/img-upload` 前端模块与外部模块的数据流与接口边界。本文档基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md) 与 [data-model.md](data-model.md)。

---

## 一、Context & Scope（上下文与范围）

`frontend-v3/img-upload` 模块连接以下外部模块：

- 浏览器 Web API：`<input type="file">`、DragEvent、ClipboardEvent、`navigator.mediaDevices.getDisplayMedia`、`URL.createObjectURL` / `revokeObjectURL`、`<dialog>`。
- backend img_upload：`POST /api/v1/chat/sessions/{sid}/images`、`GET /api/v1/chat/images/{id}/thumbnail`、`GET /api/v1/chat/images/{id}/data`。
- frontend chat-input.tsx：宿主组件，托管附件栏与发送门禁。
- frontend useChatStream / chat 流：扩展 ChatRequest 携带 `image_ids`。
- frontend message-item.tsx + chat-panel.tsx：历史消息中的图渲染。
- frontend lib/api/types.ts：扩展 ChatRequest 与 ChatMessage 类型。

本文档只描述图片附件流；不描述 LLM 调用、SSE 解析、source-selector、generated_images。

---

## 二、Data Flow Description（数据流描述）

### 1. 选图流（File Picker）

1. 用户点击 paperclip 按钮 → 触发隐藏 `<input type="file" multiple accept="image/*">.click()`。
2. `change` 事件回调拿到 `event.target.files`。
3. 收集为 `File[]` 后调用 `useChatImageUpload.add(files)`。
4. 进入"客户端校验流"。

### 2. 拖拽流（Dropzone）

1. 用户在 chat-input 区域拖入文件 → `dragover` 阻止默认行为，附件栏显示 dropzone 高亮。
2. `drop` 事件捕获 `event.dataTransfer.files`。
3. 同样进入"客户端校验流"。

### 3. 剪贴板流（Paste）

1. textarea 聚焦时监听 `paste` 事件。
2. 检查 `event.clipboardData.files`；若存在图片，`event.preventDefault()`（防止把 base64 字符塞进 textarea）。
3. 进入"客户端校验流"。

### 4. 截屏流（Screenshot）

1. 用户点击截屏按钮（仅在浏览器支持 `getDisplayMedia` 时显示）。
2. hook 调 `navigator.mediaDevices.getDisplayMedia({ video: true })` 拿到 MediaStream。
3. 将 MediaStream 帧绘到 OffscreenCanvas / canvas 元素，导出为 PNG `Blob`，封装为 `File`。
4. stream 立即停止；进入"客户端校验流"。

### 5. 客户端校验流

1. `useChatImageUpload.add(files)` 接收 `File[]`。
2. 对每张文件做以下校验：
   - MIME 在 `image/png | image/jpeg | image/webp`。
   - size ≤ 10 MB。
   - 加入后集合总数 ≤ 10。
3. 通过校验的项构造 idle Attachment 与 ObjectURL，进入集合。
4. 不通过的项：以 toast 提示原因码（mime / oversize / count），不进入集合。
5. hook 自动对所有 idle 项调度上传。

输出目标：附件 reducer state、附件栏 UI、toast。

### 6. 上传流

1. hook 标记 attachment 为 `uploading`。
2. `lib/api/chat-images.uploadChatImages(sessionId, file)` 发 multipart POST。
3. 成功响应：
   - 取响应中 images[0]（单文件 POST，预期一项）。
   - 标记 attachment `ready`，写入 `imageId`、`width`、`height`、`mimeType`。
4. 失败响应（4xx/5xx/网络）：
   - 标记 `failed`，写入 `errorCode` / `errorMessage`。
   - 卡片显示 retry / remove 按钮。
5. 全局并发限制：hook 内队列保持最多 4 个 in-flight upload，剩余排队。

输出目标：reducer state、错误展示。

关键约束：

- 单图请求体即原文件 multipart，不在前端做 base64 转码。
- 上传请求都打到当前 chat session 的 `session_id`；session_id 切换会触发 hook reset。

### 7. 发送流

1. 用户点击发送按钮（前提：text 非空且所有附件 ready）。
2. chat-input 收集 ready attachments 的 imageId 列表。
3. 调用 `onSend(text, mode)` 时携带 `imageIds`（chat-input 要把 onSend 签名扩展为支持 image_ids，或新增 `attachments` 参数；选其一在实现时锁定）。
4. 上层 useChatStream 调 `chatStream(notebookId, ChatRequest)`，ChatRequest 增 `image_ids`。
5. SSE 流正常返回；mode 不在 {agent, ask} 时该字段不被拼入。
6. 发送成功 → `useChatImageUpload.reset()` 清空附件、释放所有 ObjectURL。
7. 发送失败（chat 流自身的错误）→ 附件保持原状，让用户可以再次按发送。

输出目标：后端 chat stream、附件集合归零。

关键约束：

- 发送时不重新上传图（上传已经在选图时完成）。
- 失败回退仅作用于 chat 流，不会让附件 reset。

### 8. 历史回看流

1. chat-panel 加载历史消息列表，每条 ChatMessage 可能含 `image_ids`。
2. message-item 在文本旁渲染缩略图卡片网格：每个 id → `<img src=/api/v1/chat/images/{id}/thumbnail loading="lazy">`。
3. 用户点击缩略图：打开 `<dialog>`，内部 `<img src=/api/v1/chat/images/{id}/data>`。
4. ESC / 点击遮罩 → 关闭 dialog。
5. 关闭 chat-panel / 切 session → 历史消息 unmount，浏览器自然回收图片资源。

输出目标：历史 chat 视图。

关键约束：

- 历史回看不触发任何上传或 LLM 调用。
- 缩略图加载错误（image 已被软删等）显示一个 placeholder 占位，不让卡片整个崩塌。

### 9. 浏览器能力降级流

1. 模块挂载时各 hook 探测对应 API。
2. 不支持 → 对应入口在 JSX 层不渲染对应按钮 / 不挂监听。
3. 用户仍可通过其他可用入口添加附件；file picker 永远可用。

输出目标：JSX 渲染。

---

## 三、Interface Definition（接口定义）

### 1. 浏览器侧（外部）

- DragEvent、ClipboardEvent、ChangeEvent on `<input type="file">`：标准 Web API，前端按规范使用。
- `getDisplayMedia(video: true)`：返回 Promise<MediaStream>；用后立即 stop track。
- `URL.createObjectURL(blob)` / `URL.revokeObjectURL(url)`：本地 blob URL 管理。
- `<dialog>` showModal / close：用于 lightbox。

### 2. backend HTTP（外部）

- `POST /api/v1/chat/sessions/{session_id}/images`
  - Content-Type: `multipart/form-data`
  - 字段：`files`（一项）
  - 成功 200：`{ images: [{ image_id, mime_type, size_bytes, width, height, preview_url, thumbnail_url }], errors: [] }`
  - 失败 4xx/5xx：现有 ApiError 形态。
- `GET /api/v1/chat/images/{image_id}/thumbnail`
  - 直接作为 `<img src>` 使用；带同站 cookie。
- `GET /api/v1/chat/images/{image_id}/data`
  - 同上，原图。
- `POST /api/v1/chat/notebooks/{notebookId}/chat/stream`
  - 现有路径；扩展 ChatRequest body 增 `image_ids`。

### 3. lib/api/chat-images.ts（新增内部 API client）

- `uploadChatImages(sessionId: string, file: File) -> Promise<UploadResponse>`
- `getChatImageThumbnailUrl(imageId: string) -> string`
- `getChatImageDataUrl(imageId: string) -> string`

后两者返回字符串（拼路径），不发请求；浏览器渲染 `<img>` 时实际加载。

### 4. useChatImageUpload（新增内部 hook）

- 签名：`useChatImageUpload({ sessionId }): { attachments, add, retry, remove, reset, allReady, imageIds }`
- 副作用：自动上传；session 变化触发 reset；unmount 释放所有 ObjectURL。

### 5. chat-input 扩展（既有组件）

- `onSend` 签名扩展为携带 `imageIds`（或在 ChatInputProps 中新增 `attachments` 受控字段；二选一在实现时锁定）。
- 发送门禁条件由 `!input.trim()` 扩展为 `!input.trim() || attachmentsNotReady`。

### 6. message-item 扩展（既有组件）

- 接收 `image_ids` 字段，按 id 渲染缩略图行。
- 提供点击放大入口。

### 7. lib/api/types.ts 扩展

```ts
interface ChatRequest {
  ...
  image_ids?: string[];
}
interface ChatMessage {
  ...
  image_ids?: string[];
}
```

---

## 四、Data Ownership & Responsibility（数据归属与责任）

### 数据创建

- Attachment：由 `useChatImageUpload.add` 在客户端创建。
- ObjectURL：与 Attachment 同步创建。
- image_id：由后端创建并通过 upload 响应返回；前端只读。
- ChatRequest.image_ids：由 chat-input 在提交时即时构造。

### 数据更新与销毁

- Attachment.status 转移：仅由 hook 内部 reducer 推进。
- ObjectURL：必须在 `remove` / `reset` / `unmount` 三处释放（任一遗漏即内存泄漏）。
- image_id：前端从不修改、不删除（删除由后端 session/message 删除联动）。
- ChatRequest 提交后丢弃。

### 责任边界

- 浏览器 API 与各 trigger hook 只产出 File[]，**不**做校验、**不**触上传。
- `useChatImageUpload` 只管状态与上传调度，**不**渲染 UI。
- `attachment-bar` / `attachment-card` 只渲染 UI，**不**发起网络。
- `lib/api/chat-images` 只发请求、映射错误，**不**管状态机。
- chat-input 只管"门禁条件"与"提交时拼 image_ids"，**不**管附件状态与上传细节。
- message-item 只管历史消息渲染，**不**碰当前编辑中的附件状态。

### 与 Zustand chat-store 的隔离

附件状态机不进 chat-store；store 不感知附件存在。理由：附件生命周期与"当前正在编辑的消息"完全一致，全局化反而带来"何时清空"的协议风险。

### 与 useChatStream 的协作

useChatStream 维持现有签名，只是 ChatRequest 多了一个可选字段。SSE 解析、错误处理、cancel 行为不需为附件做任何特殊路径。

---

## 五、文档自检

- [x] 9 条数据流覆盖了 4 类入口、客户端校验、上传、发送、历史回看、能力降级。
- [x] 每个外部 / 内部接口都映射到至少一条数据流。
- [x] 责任边界清晰：trigger / hook / UI / API client / 宿主组件互不重叠。
- [x] ObjectURL 释放契约在三个位置都被显式登记。
- [x] 不引入超出 architecture.md 的子组件，不为未在数据流中使用的接口留位置。
