# img_upload 前端模块 test.md

本文档说明如何验证 `frontend-v3/img-upload` 在真实协作环境中是可信的。基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md)、[data-model.md](data-model.md)、[dfd-interface.md](dfd-interface.md)、[non-functional.md](non-functional.md)。

---

## 一、Module Test Profile（模块测试档案）

- **模块原型**：混合原型
  - `useChatImageUpload` reducer / 状态转移、客户端校验函数、Send Gate Predicate → **纯逻辑**
  - `useDropzone` / `usePasteImage` / `useScreenshot` / `PaperclipButton` 触发器到状态机的接入 → **服务编排**
  - `lib/api/chat-images` 封装 → **桥接 / 适配（HTTP client 适配）**
  - `attachment-bar` / `attachment-card` / chat-input 扩展 / message-item 扩展 → **服务编排（UI 编排）**
- **主要测试类型**：unit（vitest + testing-library）。本模块不直接发后端 HTTP，所有 API 调用都通过 mock。
- **Mock 边界**：
  - `lib/api/chat-images` 的 3 个函数全部 mock。
  - `URL.createObjectURL` / `URL.revokeObjectURL`：使用 vitest spy 替换，验证调用与释放。
  - `navigator.mediaDevices.getDisplayMedia`：mock 返回受控 MediaStream / 拒绝。
  - `ClipboardEvent` / `DragEvent`：用 testing-library `fireEvent` 派发。
  - 后端契约由 [backend-v4/img-upload/test.md](../../backend-v4/img-upload/test.md) 负责，不重复测试。
- **测试归属目录**：
  - `frontend/src/components/chat/chat-input.test.tsx`（已存在；扩展）
  - `frontend/src/components/chat/chat-image-attachments/attachment-bar.test.tsx`（新增）
  - `frontend/src/components/chat/chat-image-attachments/attachment-card.test.tsx`（新增）
  - `frontend/src/components/chat/message-item.test.tsx`（已存在；扩展）
  - `frontend/src/lib/hooks/useChatImageUpload.test.ts`（新增）
  - `frontend/src/lib/hooks/useDropzone.test.ts` / `usePasteImage.test.ts` / `useScreenshot.test.ts`（新增）
  - `frontend/src/lib/api/chat-images.test.ts`（新增）

---

## 二、Test Scope（测试范围）

### 覆盖

- 客户端预校验：MIME / size / 张数。
- Attachment 状态机：add → uploading → ready / failed；retry；remove；reset。
- ObjectURL 生命周期：创建 / 释放（remove / reset / unmount 三处）。
- Send Gate Predicate：`!text.trim() || any !ready` 在不同组合下的真值。
- 四类入口：file picker change、drop、paste、screenshot 各自把 File[] 喂给状态机。
- 上传 API 客户端：multipart 请求 body / 错误映射。
- Chat-input 提交流程：发送 payload 中 image_ids 仅含 ready 项；mode∉{agent,ask} 时不携带；发送后 reset。
- Message-item 历史渲染：image_ids 渲染缩略图、点击放大、加载失败 placeholder。
- 浏览器能力降级：getDisplayMedia 不支持时按钮不渲染。
- i18n：附件相关文案 zh / en 都有。

### 不覆盖

- 后端 multipart 请求体真实落盘（属于 backend test.md）。
- LLMClient 的 vision_fallback 行为（属于 backend）。
- 流式 SSE 事件解析（属于现有 useChatStream 测试）。
- 浏览器跨版本兼容性（属于人工抽测）。

### 混合原型的归属说明

- 纯逻辑（reducer / 校验 / predicate）：unit 测试，毫秒级。
- 服务编排（hook 与触发器、UI 组件）：testing-library + 模拟事件。
- 桥接（chat-images API client）：mock fetch / `apiFetch` 验证 method、path、body、错误映射。

---

## 三、Critical Scenarios（关键场景）

### 1. 客户端预校验

- 添加 1 张合法 PNG → 进入集合，status=`uploading`（mock upload pending）或 `ready`（mock 立即解析）。
- 添加 1 张 PDF（mime=application/pdf）→ 不进入集合；toast 显示 `unsupported_mime`。
- 添加 1 张 12MB 图 → 不进入集合；toast 显示 `oversize`。
- 已有 9 张 ready，再批量加 2 张 → 9 张保持，第 1 张允许进，第 2 张被 `count_exceeded` 拒。

### 2. 状态机正常路径

- add 单张 → 立即出现 idle/uploading 卡片 + ObjectURL。
- mock upload 200 → 卡片转 ready，imageId 落入 state。
- 用户输入文本 + ready 卡片在 → 发送按钮可点。
- 点击发送 → onSend 被调用，payload 包含 image_ids；hook reset 触发；ObjectURL 释放。

### 3. 状态机异常路径

- mock upload 500 → 卡片转 failed，errorCode/Message 落入 state；retry 按钮可见；text 不被影响。
- 点 retry → 重新发起 POST；mock 第二次成功 → 卡片转 ready。
- 点 remove（任何状态）→ 卡片移除；ObjectURL.revoke 被调用一次。
- 同一张图 add 两次 → 默认允许重复（与 macOS 文件管理一致），各自独立卡片。

### 4. Send Gate

- text 空 + 0 张图 → disabled。
- text 非空 + 0 张图 → 可发。
- text 非空 + 1 张 uploading → disabled。
- text 非空 + 1 张 failed → disabled。
- text 非空 + 1 张 ready → 可发。
- text 空 + 1 张 ready → disabled（仍要求文本；可在 goals-duty 后续讨论是否允许"无文本只发图"，本期默认 disabled）。

### 5. 四类入口

- File picker：fireEvent.change(input, { target: { files: [file] } }) → add 被调用一次。
- Drop：fireEvent.drop(zone, { dataTransfer: { files: [file] } }) → add 被调用一次。
- Paste：fireEvent.paste(textarea, { clipboardData: { files: [file] } }) → add 被调用；textarea 不接收 base64 文本。
- Screenshot：mock getDisplayMedia → 一帧抓取 → File 进 add；之后 stream.stop 被调用。

### 6. ObjectURL 生命周期

- add → createObjectURL 被调一次。
- remove → revokeObjectURL 被调一次（针对该 attachment 的 url）。
- reset → 集合中所有 attachment 的 url 都被 revoke。
- 组件 unmount → 所有 attachment 的 url 都被 revoke。
- 测试通过 spy 计数验证 create vs revoke 平衡。

### 7. 历史回看

- ChatMessage 含 image_ids=["a","b"] → 渲染两个 `<img src=/api/v1/chat/images/{id}/thumbnail>`。
- 点击缩略图 → `<dialog>` showModal 被调用，dialog 内 `<img src=.../data>`。
- thumbnail 加载失败（onError 触发）→ 切到 placeholder 占位；不让消息卡片崩塌。

### 8. 浏览器能力降级

- mock `navigator.mediaDevices.getDisplayMedia = undefined` → screenshot 按钮不渲染。
- mock `navigator.clipboard = undefined` 但 ClipboardEvent 仍能 fire → paste 入口仍工作。
- file picker 永远渲染。

### 9. mode 切换

- mode=agent → 附件栏可见；发送 payload 含 image_ids。
- mode=ask → 同上。
- mode=explain / conclude（如未来在该面板出现）→ 附件栏不渲染或被禁用；发送 payload 不携带 image_ids。

### 10. i18n

- 切 zh：所有附件相关文案显示中文。
- 切 en：显示英文。
- 没有 fallback 到 key 名的渲染。

### 11. 无障碍

- paperclip 按钮、screenshot 按钮、attachment-card 都有 aria-label。
- attachment-card 上的 retry / remove 按钮可被键盘 Tab 到，Enter / Space 触发动作。
- `<dialog>` lightbox 关闭时焦点回到触发缩略图。

---

## 四、Contract Specification（契约规约）

### `lib/api/chat-images.ts` 函数契约

#### `uploadChatImages(sessionId: string, file: File)`
- 调用 `apiFetch` 发 `POST /api/v1/chat/sessions/${sessionId}/images`，body 是 FormData `files`=[file]。
- 成功：解析响应 `{ images: [...], errors: [] }`，返回 `images[0]`（断言 length===1）。
- 失败：抛出 `ApiError`（沿用项目现有错误形态）。

#### `getChatImageThumbnailUrl(imageId)` / `getChatImageDataUrl(imageId)`
- 返回字符串路径，不发请求；浏览器 `<img src>` 触发实际加载。
- URL 形式必须与 backend 约定一致：`/api/v1/chat/images/{id}/thumbnail` / `/data`。

### `useChatImageUpload(opts)` 行为契约

- 返回的 `imageIds` 仅含 ready 项 image_id，按集合中顺序排列。
- `allReady`：集合空 → true；任一非 ready → false。
- `add(files)`：对每个非法文件触发回调（toast）；合法文件立即进入 idle 并自动调度上传。
- `reset()`：必须释放所有 ObjectURL。
- session 切换：hook 监听 sessionId 变化并自动 reset。

---

## 五、Integration Points（集成点测试）

### 1. 与 chat-input

- chat-input 挂载 `useChatImageUpload`；附件栏接受其 `attachments` 与动作。
- chat-input 的 sendDisabled 取自 hook 派生 + text 状态。
- onSend 触发时，hook.reset() 在同一 tick 内被调用。

### 2. 与 useChatStream

- ChatRequest 携带 image_ids；mock useChatStream 验证它接收到的 payload 形态。
- chat 流失败不触发 hook.reset。

### 3. 与 message-item

- 历史消息含 image_ids 时渲染缩略图；不含时不渲染附件区域。
- 不复用 image-card-list 组件（生成图与上传图两条独立 UI）。

### 4. 与 lib/api/chat-images

- 上述函数契约的失败映射（4xx → 用户 error 消息；5xx → 通用 error）传递到 attachment.errorMessage。

### 5. 与 backend session_id

- 必要前置：sessionId 必须存在；hook 在 sessionId 为空时 attachments 始终空、不接受 add（编程错误）。

---

## 六、Verification Strategy（验证策略）

- **单元测试**：vitest + testing-library + jsdom；mock fetch / apiFetch；不需要后端运行。
- **快照敏感的测试**：仅对附件卡片状态显示用快照；其他用断言（避免快照膨胀）。
- **ObjectURL 平衡断言**：每个相关测试结束 expect createObjectURL.calls === revokeObjectURL.calls；防止泄漏回归。
- **可访问性**：testing-library 内置查询（getByRole / getByLabelText）替代 querySelector，强制 ARIA 完备。
- **手工 smoke**：开发者在引入或修改本模块时手工抽测：4 类入口各试一次 + 截屏在 Chrome / Firefox / Safari 桌面端各确认一次 + 移动端 Safari 确认 file picker 可用。
- **CI 标记**：unit 进 frontend lint/test pipeline；smoke 不进 CI。

---

## 七、文档自检

- [x] 已声明模块原型（混合）并对各部分映射测试类型。
- [x] 关键职责（D1–D10）每条都有验证场景：
  - D1 状态机 → 场景 2、3
  - D2 四类入口 → 场景 5
  - D3 客户端校验 → 场景 1
  - D4 并发上传 → 场景 2、3 + hook 队列单测
  - D5 缩略图来源 → 场景 6
  - D6 发送门禁 → 场景 4
  - D7 image_ids 注入 → 场景 2、集成点 2
  - D8 历史回看 → 场景 7
  - D9 浏览器降级 → 场景 8
  - D10 i18n / a11y → 场景 10、11
- [x] 桥接（chat-images API client）写入 Contract Specification。
- [x] mock 边界明确：不打真实后端、不真实抓屏。
- [x] 测试归属目录与现有 frontend 结构一致，新增子目录。
