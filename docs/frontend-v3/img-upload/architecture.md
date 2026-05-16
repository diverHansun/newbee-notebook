# img_upload 前端模块 architecture.md

本文档描述 `frontend-v3/img-upload` 前端模块的内部结构与设计选择。设计严格服从 [goals-duty.md](goals-duty.md)：四类入口统一汇聚、缩略图本地优先、发送门禁、不实现压缩、与 backend 契约严格对齐。

---

## 一、Architecture Overview（总体架构）

模块由六个子组件协作：

1. **Attachment State Machine（附件状态机）**：`useChatImageUpload` hook 维护当前消息的附件集合（每张图 idle/uploading/ready/failed）、提供 add / retry / remove / reset 动作。
2. **Input Triggers（四类输入触发器）**：
   - `PaperclipButton`：file picker 触发组件
   - `useDropzone`：textarea + 附件栏区域的拖拽 hook
   - `usePasteImage`：捕获剪贴板图片的 hook
   - `ScreenshotButton` + `useScreenshot`：通过 getDisplayMedia 截屏的按钮与 hook
   每个 trigger 唯一职责是产出 `File[]`，统一交给状态机。
3. **Attachment Bar（附件栏 UI）**：`ChatImageAttachmentBar` 组件，渲染缩略图行；每张图卡片含进度环 / error 标记 / 重试 / 删除。
4. **Send Gate（发送门禁）**：`chat-input` 内部把 `sendDisabled` 计算从单纯 `!input.trim()` 扩展为 `!input.trim() || attachments.some(a => a.status !== 'ready')`。
5. **Chat Image API Client**：`lib/api/chat-images.ts`，三个函数 `uploadChatImages` / `getChatImageThumbnail` / `getChatImageData`。
6. **History Image Renderer（历史缩略渲染）**：`MessageItem` 中 `image_ids` 的渲染逻辑——使用后端 thumbnail 端点；点击放大走 data 端点（lightbox 暂用 native dialog）。

### 高层依赖关系

```text
PaperclipButton  ─┐
useDropzone     ─┤
usePasteImage   ─┼─► useChatImageUpload (state machine)
useScreenshot   ─┘     │
                       ├─► ChatImageAttachmentBar (uses ObjectURL)
                       │
                       ├─► uploadChatImages (POST per file or batched)
                       │     │
                       │     └─► /api/v1/chat/sessions/{sid}/images
                       │           returns image_id, mime, size, w, h
                       │
                       └─► chat-input.tsx
                             sendDisabled := text empty || any !ready
                             on submit:
                               text + image_ids → onSend
                               useChatImageUpload.reset()

chat-panel.tsx history
  ├─► MessageItem displays text + image_ids
  │     │
  │     └─► <img src=/api/v1/chat/images/{id}/thumbnail>
  └─► click thumbnail
        └─► fetch /api/v1/chat/images/{id}/data → lightbox
```

### 状态机摘要

每个附件 `Attachment`：
```text
idle              # 局部 File 已纳入；ObjectURL 已创建
  → uploading     # POST 中
    → ready       # 成功；image_id 已收
    → failed      # 网络/校验/服务端失败；保留 errorMessage 与可重试动作
  ← retry()       # failed → uploading
  ← remove()      # 任何状态 → 从集合中移除并 URL.revokeObjectURL
```

集合上的派生：
- `allReady = attachments.every(a => a.status === 'ready')`
- `imageIds = attachments.filter(a => a.status === 'ready').map(a => a.image_id)`
- `sendDisabled = !text.trim() || attachments.length > 0 && !allReady`

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. State Machine in a Hook：附件集合是一个本地状态机

不进 Zustand / React Query；附件集合的生命周期与"当前正在编辑的消息"完全一致，发送 / 切 session / unmount 都应连带销毁。用 `useChatImageUpload` hook + `useReducer` 管理是最简方案。

服务于 goals-duty **G3 / G4 / D1**。

### 2. Triggers as Pure File Producers：四类入口职责单一

四个 trigger 全部只产出 `File[]`，由状态机统一接入。这样新增触发方式（例如未来加"从剪贴板 URL 拉图"）时不必改动状态机。

服务于 architecture-guide 的"以角色而非功能命名"。

### 3. ObjectURL First, Thumbnail Endpoint Second

ChatImageAttachmentBar 中：
- attachment.status ∈ { idle, uploading, ready, failed } 全部用 `URL.createObjectURL(file)`；
- 仅在历史消息回看时使用后端 `thumbnail` 端点。

这样发送前的视觉响应完全本地，零网络等待；同时避免"上传完后又去拉缩略图"的无意义往返。

服务于 goals-duty **G5**。

### 4. Send Gate as a Pure Predicate

发送门禁不是"上传完成后发事件触发解锁"，而是渲染期一行 `attachments.every(...)`。这样不可能出现"事件丢失导致按钮永久禁用"的死锁。

服务于 goals-duty **G3 / D6**。

### 5. Per-File POST instead of single multipart batch

虽然 backend 接口接受 multipart 多文件一次性提交，但前端选择**每文件一个独立请求**。理由：
- 单文件失败不影响其他；不需要消费 207 partial
- 重试粒度自然变成单文件
- 进度条天然按文件计算
- 不需要在前端复制 backend 的 207 错误项映射逻辑

服务于 goals-duty **G7**。

### 6. Cross-Browser Capability Detection at Mount

四类入口在组件挂载时各自做能力探测：
- 拖拽：所有现代浏览器原生支持，无需检测。
- 剪贴板：检测 `'clipboard' in navigator` 或直接挂 `paste` 监听。
- 截屏：检测 `'getDisplayMedia' in navigator.mediaDevices`。
- file picker：始终可用。

不可用入口在 JSX 中根本不渲染对应按钮（与 llm_title_aided 同款"条件渲染优于 disabled"原则）。

服务于 goals-duty **G6 / D9**。

### 7. History Renderer Reuses Existing MessageItem

历史消息中的图渲染嵌入 `message-item.tsx` 既有结构，不新建独立 history image 组件。理由：
- 图始终是某条消息的附属物，独立组件会让"消息整体"被切碎
- ImageCardList 是给生成图用的、视觉风格不同；本模块的历史缩略图嵌入消息正文，不复用它

服务于 goals-duty **G8 / N5**。

### 8. 拒绝在前端做压缩或 resize

backend `load_for_llm` 已经做长边缩放；前端再做一次会让事实失真且不可控。前端的责任只到客户端预校验。

服务于 goals-duty **N4**。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

```text
frontend/src/
├ components/
│  └ chat/
│     ├ chat-input.tsx                         扩展：附件栏槽位 + 发送门禁
│     ├ chat-input.test.tsx                    扩展：附件栏渲染、发送禁用、四类入口
│     ├ chat-image-attachments/                新增子目录
│     │  ├ attachment-bar.tsx                  缩略图行容器；接收 attachments + 动作
│     │  ├ attachment-card.tsx                 单张图卡片：缩略 / 进度 / error / 重试 / 删除
│     │  ├ paperclip-button.tsx                file picker
│     │  ├ screenshot-button.tsx               getDisplayMedia 一帧截屏
│     │  └ index.ts                            re-exports
│     ├ message-item.tsx                       扩展：显示 image_ids 缩略图
│     └ message-item.test.tsx                  扩展：历史回看渲染
├ lib/
│  ├ api/
│  │  └ chat-images.ts                         新增：upload / get thumbnail / get data
│  └ hooks/
│     ├ useChatImageUpload.ts                  新增：附件状态机 + 上传调度
│     ├ useDropzone.ts                         新增：拖拽 hook
│     ├ usePasteImage.ts                       新增：剪贴板 hook
│     └ useScreenshot.ts                       新增：getDisplayMedia 一帧截屏
├ lib/api/
│  └ types.ts                                  扩展：ChatRequest 增 image_ids；ChatMessage 增 image_ids
└ lib/i18n/
   └ strings.ts                                新增 chat.attachments.* 命名空间
```

### 工件职责

| 工件 | 职责 | 不应承担 |
|------|------|----------|
| `useChatImageUpload` | 附件集合状态机；分发上传任务；暴露 add/retry/remove/reset | UI 渲染；具体网络层重试策略 |
| `attachment-bar` | 行级布局；空集合时不渲染 | 状态变更 |
| `attachment-card` | 单张视觉；触发 onRetry / onRemove | 网络调用 |
| 四类 trigger hook / button | 产出 `File[]` | 校验、上传 |
| `lib/api/chat-images` | 网络调用，错误映射成普通 `ChatImageError` | 状态机、UI |
| `MessageItem` 内的图渲染 | 显示历史缩略 + 点击放大 | 上传、重试 |

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 1. 不接入第三方文件上传库

**取舍**：放弃 react-dropzone / filepond / uppy 等成熟库，接受自实现 hook 的代价。
**理由**：项目目前没引入；为本模块引入会带来一整套可见性 / 主题 / 国际化的对齐成本，且这些库的状态模型未必与 backend 两阶段契约对齐。

### 2. 单文件 POST 而非批量 multipart

**取舍**：放弃了"一次请求，错误项 207 处理"的方式；接受 N 张图发 N 个请求的代价。
**理由**：错误隔离粒度自然变成单文件；前端不需要复制 backend 的 207 解析逻辑；并发由前端 hook 控制（max 4，与 non-functional 一致）。

### 3. 历史回看走 thumbnail 端点而非现场再生 ObjectURL

**取舍**：放弃了"打开历史会话时把所有图都拉为 base64 注入 ObjectURL"的方案，接受历史每张图各发一个 thumbnail 请求。
**理由**：base64 注入会让历史会话首屏体积膨胀；分别拉缩略图可懒加载、可缓存（HTTP cache）。

### 4. 不在前端做图片压缩

**取舍**：放弃了"前端 canvas resize 节省带宽"，接受单图最多 10 MB 上传的带宽。
**理由**：与 backend `load_for_llm` 二次缩放叠加会失真；前端校验 ≤ 10 MB 已是上限。

### 5. 截屏入口仅做"屏幕分享一帧"

**取舍**：放弃了"区域截屏 / 录制"等高级能力，接受单帧抓取的简化体验。
**理由**：高级截屏需要本地剪裁 UI，复杂度与本模块"图片附件"目标不匹配；用户需要时可用系统截屏快捷键再粘贴进来（覆盖度由 paste 入口兜底）。

### 6. 拒绝把附件提升到全局 store

**取舍**：放弃了把 attachments 放进 Zustand `chat-store` 的方案，保持在 chat-input 局部 hook。
**理由**：附件生命周期等于"当前正在编辑的消息"，没有跨组件读取需求；放全局会把"清空时机"变成易错的协议。

### 7. 不在 message-item 中复用 image-card-list

**取舍**：放弃了"all-in-one 图卡组件"的统一抽象，接受两个相邻但不重合的渲染路径（生成图 vs 上传图）。
**理由**：两者来源信任、点击行为、回退视觉都不同；强行合并会让 ImageCardList 长出多分支。

### 8. lightbox 用 native `<dialog>` 起步

**取舍**：放弃了引入 lightbox 库，接受较朴素的放大查看体验。
**理由**：体验需求未明确到需要 zoom / 旋转 / 多图横滑；先用 native `<dialog>` 满足"放大看清楚"的最小需求，演进余地保留。
