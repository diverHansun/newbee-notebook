# img_upload 模块 data-model.md

本文档描述 `img_upload` 模块中的核心概念与数据归属。该文档是精简概念词典，不定义 ORM、类结构或完整字段清单。

---

## 一、Core Concepts（核心概念）

### 1. Chat Image

用户在某次聊天会话中上传的图片资产。

它是用户输入事实的持久化记录，独立于该图被哪条消息引用。一张 Chat Image 可以被多条消息引用，但不能被跨会话引用。

### 2. Image Reference

聊天消息上对若干 Chat Image 的引用。

它表达"这条消息当时附带了哪些图"，是消息层的元数据，不是 LLM 上下文层的内容。Image Reference 在历史回看时被前端读取，但不会让 ContextBuilder 重新把图送给 LLM。

### 3. Vision Capability

某个 (provider, model) 组合是否能处理 image content part 的能力声明。

它不是用户配置项，而是项目对 provider 模型空间的事实判断。该判断的来源是 provider 官方文档，由代码常量维护。

### 4. Effective Vision Model

当前一轮聊天调用实际使用的 model。

当用户当前所选 model 不具备 Vision Capability 且本轮携带图片时，Effective Vision Model 等于 provider 的默认视觉模型；否则等于用户当前所选 model。该值仅本次调用生效，不写回任何配置。

### 5. LLM Image Part

OpenAI 兼容多模态消息中的图片片段。

它表现为 `{"type": "image_url", "image_url": {"url": ...}}`，url 取值为 `data:image/...;base64,<encoded>`。LLM Image Part 由 Chat Image 经"读取原图 → 长边缩放 → base64 编码"派生而来，属于 transient value，不持久化。

### 6. Chat Images Storage Object

存储后端中保存图片二进制的对象。

它的对象 key 形如 `chat-images/{session_id}/{image_id}.{ext}`，由 `StorageBackend` 抽象统一访问。该对象与 Chat Image 元数据是一一对应的两份记录，删除时按软删 → 后台清理顺序执行。

---

## 二、Entity / Value Object 区分

### Entity

| 概念 | 身份 | 生命周期 |
|------|------|----------|
| Chat Image | image_id（UUID） | 上传时创建；session/message 删除时软删；后台清理 storage 对象 |
| Chat Images Storage Object | storage_key | 上传时创建；后台 sweeper 在软删后清理 |

### Value Object

| 概念 | 说明 |
|------|------|
| Image Reference | 作为 chat_messages.image_ids JSONB 数组持久化；本身没有独立身份 |
| Vision Capability | 由代码常量推导，不持久化 |
| Effective Vision Model | 每次聊天调用时计算得到，作为不可变 LLMRuntimeConfig 副本的一个字段；不持久化 |
| LLM Image Part | 仅作为内存 dict 出现在 LLM 请求中；不持久化 |

---

## 三、Key Data Fields（关键数据字段）

### Chat Image

- `image_id`：用户上传图片的全局唯一标识。
- `session_id`：图片所属的聊天会话；用于跨会话引用校验与级联软删。
- `uploaded_by`：上传者用户标识，用于审计；当前阶段允许为空以兼容尚未引入用户体系的部署。
- `storage_key`：在 StorageBackend 下的对象 key。
- `mime_type`：经过 magic byte 校验后的真实 MIME，取值 `image/png` / `image/jpeg` / `image/webp`。
- `size_bytes`：原图字节数。
- `width` / `height`：像素尺寸；缺失时表示 Pillow 解析失败但仍允许保留。
- `sha256`：原图内容哈希，用于会话内去重与审计追踪。
- `created_at`：上传时间。
- `deleted_at`：软删时间；非空表示该图已被联动删除，等待 sweeper 清理 storage。

### Image Reference

- `image_ids`：一条 chat_messages 上绑定的 Chat Image 标识数组；以 JSONB 数组形式存储。

### Vision Capability

- `provider`：聊天 LLM provider，例如 `qwen` / `zhipu` / `openai`。
- `vision_models`：该 provider 已知具备视觉能力的 model 名集合。
- `default_vision_model`：当当前 model 不具备 vision capability 时的兜底 model 名。

### Effective Vision Model

- `provider`：保持不变。
- `model`：本次调用实际使用的 model；仅在 `provider × model` 不具备 Vision Capability 且本轮有图时被替换。
- `reason`：可诊断字段，记录是否因 vision_fallback 而被替换。

### LLM Image Part

- `type`：固定为字符串 `"image_url"`。
- `image_url.url`：data URL，形如 `data:{mime};base64,{b64}`，其中 mime 与 b64 来自经过缩放的内存副本。

### Chat Images Storage Object

- `storage_key`：与 Chat Image 元数据一致。
- `bytes`：原图二进制（不存放经过缩放的副本）。

---

## 四、Lifecycle & Ownership（生命周期与归属）

### 1. Chat Image 生命周期

1. 前端在聊天输入框选取或粘贴图片，触发上传请求。
2. Upload Surface 接收 multipart 文件，逐项做校验（MIME magic byte、size、count）。
3. Chat Image Service 写入 Storage Object，再写入 chat_images 行。
4. 接口返回 image_id 给前端。
5. 前端在发送 chat 时携带 image_ids；后端绑定到 chat_messages.image_ids。
6. session 或 message 删除时，Repository 联动写 deleted_at。
7. 后台 sweeper 任务读取软删记录，从 StorageBackend 删除对应 Storage Object，并清掉 chat_images 行。

归属：Chat Image Service（写）、Chat Image Repository（DB）、Storage Backend（对象）。

### 2. Image Reference 生命周期

1. 前端组装 ChatRequest，把当前消息绑定的 image_ids 放入请求。
2. Chat API 调用 Chat Image Service 校验 ids 全部属于当前 session。
3. Chat Pipeline Hook 把 image_ids 传递给 ContextBuilder 与 SessionMemory metadata。
4. 持久化时，image_ids 落入 chat_messages 表的 JSONB 列。
5. 历史回看时，前端读取 chat_messages.image_ids，再请求缩略图接口展示。
6. 在后续轮次或 agent 工具循环中，ContextBuilder 不基于历史消息的 image_ids 重新加载图。

归属：ChatService（请求级）、SessionMemory（运行期）、chat_messages 表（持久化）。

### 3. Vision Capability 生命周期

1. 项目代码中维护 provider→vision models 与 provider→default_vision_model 常量。
2. ChatService 在 Chat Pipeline Hook 中调用 Vision Policy。
3. 当 provider 升级出新视觉模型，需在代码常量中显式登记，并随版本发布。

归属：core/llm/vision_policy。

### 4. Effective Vision Model 生命周期

1. ChatService 取得当前 LLMRuntimeConfig。
2. 若本轮存在 image_ids 且 (provider, model) 不在 Vision Capability 内，使用 dataclasses.replace 生成新 LLMRuntimeConfig 副本，model 替换为 default_vision_model。
3. 副本仅作为本次 LLMClient 调用的参数；调用结束后副本被丢弃。
4. 任一情况下，原 LLMRuntimeConfig 与持久化配置都保持不变。

归属：ChatService（持有副本一次）。

### 5. LLM Image Part 生命周期

1. Multimodal Context Adapter 在构造当前一轮 user 消息时，对每个 image_id 调用 Chat Image Service.load_for_llm。
2. Chat Image Service 读取 Storage Object，必要时执行长边缩放，编码为 base64 data URL。
3. Adapter 将 LLM Image Part 拼到当前 user 消息的 content 数组。
4. LLMClient 透传 messages 给 AsyncOpenAI；调用结束后 LLM Image Part 被释放。

归属：Multimodal Context Adapter（装配）、Chat Image Service（计算）。

### 6. Chat Images Storage Object 生命周期

1. 上传成功时由 Chat Image Service 写入。
2. 读取时区分 `load_preview`（原图）、`load_thumbnail`（256px 缩略，可选缓存）、`load_for_llm`（不持久化的内存副本）。
3. 软删后等待 sweeper 删除。

归属：StorageBackend。

---

## 五、数据边界

### 本模块拥有的数据

- `chat_images` 表的全部字段语义。
- `chat-images/` storage 命名空间。
- `chat_messages.image_ids` 列的写入语义（与现有 chat_messages 表的其他列共同存在；读由 ChatService 协作完成）。
- Vision Capability 常量。
- Effective Vision Model 在内存中的派生策略。

### 本模块不拥有的数据

- 用户当前所选 provider/model 的来源规则与持久化（属于 LLM 配置模块）。
- chat_messages / chat_sessions 主体生命周期（属于聊天会话模块）。
- generated_images 资产与生成图工具链。
- StoredMessage.content 字符串的语义与压缩策略。
- 嵌入、检索、索引相关数据。

---

## 六、数据安全约束

1. 上传响应中不得回显文件二进制；只返回 image_id 与摘要尺寸信息。
2. 日志中只允许出现 image_id、size、mime、provider、model 等元信息，禁止出现 base64 图像内容、API key、完整请求体。
3. Storage Object 仅通过经过鉴权的读取接口对外暴露；不暴露公网直连 URL。
4. 跨会话引用必须在写入 chat_messages.image_ids 之前被拒绝，写入后再校验已迟。
5. 软删后未清理的 Storage Object 不应被任何业务读取接口返回。
6. Vision fallback 切换时记录的诊断信息只允许包含 from_model / to_model / reason，不允许包含 api_key 或图片内容。

---

## 七、文档自检

- [x] 概念数量保持克制，与现有 `generated_images` 概念清晰分离。
- [x] Image Reference 与 LLM Image Part 区分明确：前者是消息层语义，后者是 LLM 请求层 transient value。
- [x] 明确"上传是事实，送 LLM 是消费"的归属：原图与 send-to-LLM 副本走两条读取路径。
- [x] Vision Capability 与 Effective Vision Model 区分清楚：前者是项目事实，后者是单次调用计算结果。
- [x] 跨会话引用与软删两条强约束被显式登记。
- [x] 与 architecture.md 中的子组件一一对应，没有引入未在结构里出现的概念。
