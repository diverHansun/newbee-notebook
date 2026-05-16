# img_upload 前端模块 goals-duty.md

本文档定义 `frontend-v3/img-upload` 前端模块的设计目标与职责边界。

该模块在 main 面板的聊天输入框（`chat-input`）中新增图片附件能力，用户可以通过文件选择 / 拖拽 / 剪贴板 / 截屏添加图片，与文本一同发送给 agent；并对接 [backend-v4/img-upload](../../backend-v4/img-upload/goals-duty.md) 已规划完成的后端两阶段上传契约。

---

## 一、模块定位

**一句话说明**：`frontend-v3/img-upload` 是 main 面板聊天输入区的图片附件入口，负责"在 textarea 上方维护一排可上传/可重试/可删除的缩略图卡片，等所有图就绪后才允许发送，把 image_ids 与文本一起提交给 chat 接口"。

**如果没有这个模块**：

- 后端 `chat_images` 上传接口与 ChatRequest.image_ids 契约存在但前端无入口，能力等同于 0。
- 用户在 main 面板对话框中无法粘贴截屏、无法拖拽设计稿向 agent 提问。
- 视觉模型兜底（backend goals-duty G3）发挥不了作用，因为前端从来不发图。

---

## 二、Design Goals（设计目标）

### G1：让用户在聊天输入区附图问问题

提供 file picker / 拖拽 dropzone / 剪贴板 paste / 截屏（getDisplayMedia）四条入口，统一汇聚到同一个附件状态机中。

### G2：附件视觉与"消息一部分"对齐

附件栏作为缩略图一行**显示在 textarea 上方**，与同一条消息文本视觉上是一组；不弹窗、不抽屉，符合 ChatGPT / 微信桌面端的常见交互习惯。

### G3：上传与发送解耦但有强契约

按 backend goals-duty 两阶段契约：选图后立即并发上传，每张图独立显示 uploading / ready / failed 状态；**所有图均为 ready 之前发送按钮保持禁用**，永不出现"图未就绪也送出去"的状态。

### G4：不阻断聊天主路径

每张图的上传、缩放、网络异常都被严格限制在附件栏内部，不影响 textarea 输入、不阻塞 SSE 流、不阻塞 source-selector / mode segmented control。

### G5：视觉响应零延迟

用户选图 / 粘贴 / 拖入的瞬间，**用本地 `URL.createObjectURL` 立即渲染缩略图**；上传成功后可选切换到后端 thumbnail_url（用于历史回看场景），但当前会话期内的发送路径不依赖后端缩略接口。

### G6：浏览器能力差异下保留主路径

剪贴板粘贴、截屏、拖拽这三类能力在不同浏览器存在能力差异；任一类不可用时模块只隐藏对应入口，不阻断 file picker 与发送。

### G7：错误可见、可重试、可删除

任意单张失败：在该张缩略图上叠加 error 视觉、提供"重试"和"移除"两个动作；不静默吃错。

### G8：复用现有 ChatRequest 流程

通过扩展 `ChatRequest.image_ids` 与现有 `useChatStream` hook 的契约让 image_ids 走到后端；不另开聊天 API、不另开 SSE 通道。

### G9：历史回看不重传

用户回看历史消息时，前端展示缩略图；不会因此自动把图重传给 LLM（与 backend N3 一致）。

---

## 三、Duties（职责）

### D1：管理一组附件的状态机

维护当前消息绑定的附件集合，每张图至少有 `idle | uploading | ready | failed` 四态；附件集合在发送或主动清空时归零。

### D2：提供四条入口

- file picker：paperclip 按钮 + `<input type="file" multiple accept="image/*">`。
- 拖拽：textarea 与附件栏区域作为 dropzone，监听 `dragenter / dragover / drop`。
- 剪贴板：聊天输入框聚焦时监听 `paste`，捕获 `ClipboardEvent.clipboardData.files`。
- 截屏：getDisplayMedia 一帧捕获并截图（仅在浏览器支持时显示按钮）。

### D3：本地校验

在调用上传 API 之前做客户端预校验：MIME / size / 单消息张数；不通过的项以 toast 或行内错误提示，不进入上传队列。

### D4：并发上传

每张通过预校验的图独立调用 `POST /api/v1/chat/sessions/{sid}/images`；失败可重试；成功取得 image_id 与缩略尺寸。

### D5：缩略图来源切换

uploading / ready 阶段优先用 `URL.createObjectURL(file)`；ready 后允许在历史路径中切到后端 `thumbnail_url`。

### D6：发送门禁

在所有附件 status === "ready" 之前，将 `chat-input` 的发送按钮 disabled；textarea 仍可编辑。

### D7：把 image_ids 注入聊天请求

发送时收集附件的 `image_id` 列表，扩展 `ChatRequest`，通过现有 chat 流式接口提交；提交完成后清空附件集合。

### D8：消息历史回看

接收 chat history 中带 `image_ids` 的消息时，调 `GET /api/v1/chat/images/{id}/thumbnail` 获取缩略图渲染；点击放大走 `GET /api/v1/chat/images/{id}/data`。

### D9：跨浏览器入口降级

检测 `navigator.clipboard`、`navigator.mediaDevices.getDisplayMedia`、`HTMLInputElement.files`；不可用时各自隐藏对应入口，但永不让整套机制崩溃。

### D10：i18n 与无障碍

新增的所有文案与 ARIA label 走 uiStrings 命名空间；附件栏键盘可达；缩略图卡片有 aria-label。

---

## 四、Non-Duties（非职责）

### N1：不实现"以图搜文档"或图像检索

附件只为 LLM 当前轮看图，不参与 RAG / 嵌入（与 backend N2 一致）。

### N2：不在 explain / conclude 模式提供附图

ChatRequest mode 不在 {agent, ask} 时附件栏不渲染，发送按钮不携带 image_ids（与 backend N6 一致）。

### N3：不实现"边发边传"

不允许"图还在 uploading 时点发送、后端继续等"的模型；G3 / D6 的契约是发送门禁。

### N4：不在前端做图片压缩或 resize

backend 已规定 long-edge>2048 在 `load_for_llm` 内缩放；前端只校验大小，不为节省带宽自行 resize。理由：避免在两端各做一次缩放，事实失真不可控。

### N5：不接管 generated_images 展示

image_generation 工具产出的图由现有 `image-card-list` 渲染；本模块不与之合并 UI。

### N6：不实现独立的"附件管理器"页面

附件只在当前消息维度存在；不提供"我所有的上传图片"列表视图。历史消息中的图通过历史 chat 列表回看，不通过总览页。

### N7：不实现 OCR 兜底

backend N4 已禁止；前端不替 LLM 做 OCR / caption。

### N8：不实现视频 / 文件多模态入口

PNG / JPEG / WEBP 之外的类型本期一律拒绝（与 backend N4 一致）。

### N9：不与 source-selector 联动

用户附图时无需也不应自动改变文档选择；附件与 source documents 是两条独立的上下文输入。

---

## 五、设计约束与假设

### 约束

1. backend 契约已在 [docs/backend-v4/img-upload](../../backend-v4/img-upload/) 中固化：
   - `POST /api/v1/chat/sessions/{session_id}/images`（multipart 多图，可能 207 partial）
   - `GET /api/v1/chat/images/{id}/data` / `thumbnail`
   - `ChatRequest` 新增 `image_ids: list[str]`
   - 单图 ≤ 10 MB，单消息 ≤ 10 张，PNG/JPEG/WEBP
2. main 面板宿主组件是 [chat-input.tsx](../../../frontend/src/components/chat/chat-input.tsx) 与 [chat-panel.tsx](../../../frontend/src/components/chat/chat-panel.tsx)。
3. 现有 chat 流走 SSE 流式调用，扩展 `ChatRequest.image_ids` 不影响 SSE。
4. 前端无现成的拖拽 / 剪贴板 hook 可复用，需要自实现。
5. mode segmented control 的取值是 `"agent" | "ask"`，附件入口仅在这两种 mode 下渲染。

### 假设

1. 用户主流浏览器为现代 Chromium / Firefox / Safari；getDisplayMedia 在 Safari 桌面端可用、移动 Safari 不可用——按 G6 / D9 降级隐藏。
2. 用户通常单消息附 1–3 张图；10 张是上限不是常态，UI 不必为 10 张做强优化。
3. 主流截屏来源是用户主动触发"屏幕分享一帧"，不需要做"区域选择"高级功能。
4. session_id 在调用上传时一定可得（main 面板必然先创建 session 才进入聊天）。

---

## 六、与其他模块的关系

| 模块 | 关系 | 说明 |
|------|------|------|
| backend img_upload | 上游契约提供方 | 两阶段上传 + chat 扩展 + 历史回看接口 |
| frontend chat-input | 宿主 | 在 toolbar 与 textarea 之间嵌入附件栏；扩展发送门禁 |
| frontend chat-panel | 协作 | 历史消息渲染时在文本旁展示缩略图 |
| frontend useChatStream | 协作 | ChatRequest payload 增加 image_ids |
| frontend lib/api/* | 协作 | 新增 lib/api/chat-images.ts |
| frontend lib/hooks/* | 新增 | useChatImageUpload（队列 + 状态机 + 重试） |
| backend ChatService VisionPolicy | 间接 | 前端不感知 vision_fallback；后端在用户原 model 不支持视觉时单次切换 |
| frontend image-card-list | 邻居 | 工具生成图的渲染组件，本模块不与之合并 |

---

## 七、文档自检

- [x] 一句话说明模块意义：在聊天输入区附图问问题。
- [x] 明确 4 条入口、上传 / 发送解耦契约、缩略图双源策略。
- [x] 明确不做的事：OCR、视频、压缩、独立附件管理器。
- [x] 与 backend goals-duty 中的边界严格对应。
- [x] Duties 都能在 architecture / data-model / dfd-interface / test 文档中找到落点。
