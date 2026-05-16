# img_upload 模块 dfd-interface.md

本文档描述 `img_upload` 模块与外部模块之间的数据流与接口边界。本文档基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md) 与 [data-model.md](data-model.md)。

---

## 一、Context & Scope（上下文与范围）

`img_upload` 模块位于 Newbee Notebook 的聊天链路中，连接以下模块：

- 前端 chat-input 与 chat-panel：负责图片选取、上传状态展示、附图发送、历史回看。
- Chat API（chat router）与 ChatService：负责消费 image_ids、协调 ContextBuilder 与 LLMClient。
- Chat Image Service / Repository / StorageBackend：负责 Chat Image 的写入与读取。
- ContextBuilder 与 SessionMemory：负责将 image_url part 拼到当前一轮 user 消息，历史保持字符串 content。
- Vision Policy：负责裁决 (provider, model) 是否具备视觉能力，以及 provider 默认视觉模型。
- LLMClient 与 AsyncOpenAI：负责把多模态 messages 透传给上游 provider。

本文档只描述与图片上传、当前轮多模态注入、视觉模型兜底相关的外部接口与数据流。不描述 RAG 检索、文档解析、嵌入、索引、image_generation 工具链。

---

## 二、Data Flow Description（数据流描述）

### 1. 图片上传流

1. 用户在前端 chat-input 通过 file picker / 拖拽 / 剪贴板 / 截屏选取 1 至 N 张图。
2. 前端对每张图本地预校验文件类型与大小，立即调用上传接口。
3. Upload Surface 接收 multipart 文件，逐项执行 magic byte MIME 校验、size 校验、累计 count 校验。
4. Chat Image Service 把通过校验的图写入 StorageBackend `chat-images/{session_id}/{image_id}.{ext}`，并写入 chat_images 行。
5. Upload Surface 返回结构化结果：成功项的 image_id 与摘要、失败项的 error 项。
6. 前端按返回结果更新附件栏：成功项标记 ready，失败项给出重试或移除入口。
7. 在所有附件栏图均为 ready 之前，发送按钮保持禁用。

输出目标：StorageBackend、chat_images 表、前端附件栏。

关键约束：

- 上传响应不回显二进制内容。
- 失败项的 error 描述只包含原因码（unsupported_mime / oversize / count_exceeded 等），不包含敏感信息。
- 单条消息允许的最大上传张数与单图最大字节数遵循 non-functional.md 中的限额。

### 2. 附图发送流

1. 用户点击发送，前端组装 ChatRequest，将 image_ids 列表与 message 文本一起放入请求。
2. Chat API 接收请求，进入 ChatService。
3. ChatService 调用 Chat Image Service 校验 image_ids 全部属于当前 session，否则返回 400。
4. ChatService 调用 Vision Policy 判断 (provider, model) 是否具备 Vision Capability。
5. 当本轮存在 image_ids 且不具备视觉能力时，ChatService 通过 dataclasses.replace 生成临时 LLMRuntimeConfig 副本，将 model 替换为 provider 默认视觉模型，并写一条 vision_fallback 日志。
6. ChatService 将 image_ids 与文本一起交给 ContextBuilder 构造当前一轮 user 消息：历史消息保持 `{role, content: str}`；当前 user 消息构造为 `{role: "user", content: [{type: "text", text}, {type: "image_url", image_url: {url: data_url}}, ...]}`。
7. ContextBuilder 从 Chat Image Service 通过 load_for_llm 取得每张图的 base64 data URL；load_for_llm 内部完成长边缩放与 base64 编码，原图不被改写。
8. ChatService 调用 LLMClient.chat_stream，使用临时 runtime config 副本。
9. LLMClient 透传 messages 给 AsyncOpenAI，AsyncOpenAI 调用 provider OpenAI-compatible endpoint。
10. SSE 流回写到前端；ChatService 同步把 image_ids 写入 chat_messages.image_ids 列以便后续历史回看。

输出目标：LLM provider、SSE 流、chat_messages 表。

关键约束：

- mode 不在 {agent, ask} 内时，image_ids 必须为空，否则返回 400。
- vision_fallback 仅作用于本次调用，绝不写回 LLM 配置 DB 或 llm.yaml。
- image_ids 校验失败时整个 chat 请求失败，不允许"丢图保送文本"的隐式退化。

### 3. 历史回看流

1. 前端打开历史会话或滚动加载历史消息。
2. Chat API 返回 chat_messages 列表，每条消息携带 image_ids（可能为空）。
3. 前端对非空 image_ids 调用缩略图读取接口，按消息顺序渲染缩略卡片。
4. 用户点击缩略图时，前端调用原图读取接口在大图查看器中展示。
5. ContextBuilder 在后续聊天构造历史时不重新加载这些图给 LLM。

输出目标：前端 chat-panel。

关键约束：

- 缩略图与原图读取接口必须执行 session 归属校验，禁止跨用户、跨会话访问。
- 历史回看不会触发 LLM 调用，也不会消耗 token。

### 4. 删除联动流

1. 用户在前端删除 chat session 或 chat message。
2. Chat API 调用现有会话/消息删除路径，并触发 Chat Image Repository 联动软删：将关联 chat_images 行的 deleted_at 写为当前时间。
3. 后台 sweeper 任务周期性扫描 deleted_at 非空且超过保留窗口的行，从 StorageBackend 删除对应 Storage Object，再删 DB 行。
4. 任何业务读取接口都不返回 deleted_at 非空的图。

输出目标：chat_images 表、StorageBackend。

关键约束：

- 软删要在事务内联动写入，避免出现"消息没了但图还能被引用"的窗口。
- sweeper 失败必须重试；不允许在 chat 流程内同步执行 storage 删除。

### 5. Provider model 列表披露流

1. 前端在设置面板请求 `/config/models` 获取 provider 模型列表。
2. Config API 返回模型条目，每项包含 vision 能力标记，标记来源是 Vision Policy。
3. 前端在模型下拉中可选地显示视觉徽章，但不强制用户必须选择视觉模型。
4. 用户保留选择非视觉模型的权利；附图发送时由 ChatService 单次兜底处理。

输出目标：前端设置面板。

关键约束：

- vision 标记仅是展示信号，不影响发送行为。
- 修改 Vision Policy 常量需要同步覆盖 Config API 输出与前端徽章逻辑。

---

## 三、Interface Definition（接口定义）

### 1. 上传图片

- 名称：`upload_chat_images`
- HTTP 形式：`POST /api/v1/chat/sessions/{session_id}/images`
- 请求语义：multipart/form-data 中的 `files` 字段携带 1 至上限张数的图片文件；session_id 在路径中给出。
- 响应语义：返回成功项与失败项两类条目；只要存在至少一项失败即采用 207 multi-status，全部失败时退化为对应 4xx。
- 同步特性：同步返回。
- 错误语义：限额超限、不支持的 MIME、单图超大、跨会话非法等都以稳定错误码呈现，不透传内部异常。

### 2. 读取原图

- 名称：`get_chat_image`
- HTTP 形式：`GET /api/v1/chat/images/{image_id}/data`
- 请求语义：通过 image_id 全局读取原图字节。
- 响应语义：以图片 MIME 返回二进制。
- 同步特性：同步返回。
- 鉴权语义：必须在 handler 内查询 image 所属 session，并校验当前用户对该 session 的访问权限。

### 3. 读取缩略图

- 名称：`get_chat_image_thumbnail`
- HTTP 形式：`GET /api/v1/chat/images/{image_id}/thumbnail`
- 请求语义：通过 image_id 读取 256px 长边缩略图，用于历史回看的轻量渲染。
- 响应语义：以 image/webp 或 image/png 返回二进制。
- 同步特性：同步返回；缩略图允许后端缓存。

### 4. 发起聊天（扩展现有）

- 名称：`chat_stream`
- HTTP 形式：`POST /api/v1/chat/notebooks/{notebook_id}/chat/stream`
- 请求语义：在现有 ChatRequest 上增加 `image_ids: list[string]` 可选字段，仅在 mode 为 agent 或 ask 时允许非空。
- 响应语义：保持现有 SSE 事件结构不变。
- 同步特性：SSE 流。
- 错误语义：image_ids 跨会话或不存在时返回 400；其他既有错误语义保持不变。

### 5. 列出可用模型（扩展现有）

- 名称：`list_models`
- HTTP 形式：`GET /api/v1/config/models`
- 请求语义：保持现有路由不变。
- 响应语义：每个模型条目增加 `vision: bool`，由 Vision Policy 推导。
- 同步特性：同步返回。

### 6. Vision Policy（内部接口）

- 名称：`is_vision_capable(provider, model) -> bool`
- 输入：provider 字符串、model 字符串。
- 输出：布尔。
- 语义：基于代码常量裁决；纯函数，无状态。

- 名称：`fallback_vision_model(provider) -> str | None`
- 输入：provider 字符串。
- 输出：默认视觉模型名，未知 provider 时返回 None。
- 语义：基于代码常量裁决；纯函数，无状态。

### 7. Chat Image Service（内部接口）

- 名称：`upload(session_id, files) -> {images, errors}`
- 名称：`assert_belongs_to_session(image_ids, session_id)`
- 名称：`load_for_llm(image_id) -> (bytes, mime)`，bytes 为可能经过缩放的内存副本。
- 名称：`load_preview(image_id) -> (bytes, mime)`，原图。
- 名称：`load_thumbnail(image_id) -> (bytes, mime)`。
- 名称：`soft_delete_by_session(session_id)` / `soft_delete_by_message(message_id)`。

### 8. ContextBuilder（扩展现有）

- 名称：`build(..., current_image_data_urls: list[str] | None = None) -> list[dict]`
- 输入：在原有参数基础上增加 `current_image_data_urls`，按顺序对应当前轮要附带的 image_url。
- 输出：与现有相同的 OpenAI messages 列表；当 `current_image_data_urls` 非空时，最后一条 user message 的 content 形式为 OpenAI content parts 数组。
- 同步特性：同步函数。

---

## 四、Data Ownership & Responsibility（数据归属与责任）

### 数据创建

- Chat Image：由 Chat Image Service 在上传请求中创建，写入 chat_images 表与 StorageBackend。
- Image Reference：由 ChatService 在处理 chat 请求时写入 chat_messages.image_ids。
- LLM Image Part：由 Multimodal Context Adapter 在 ContextBuilder 内即时构造，不持久化。
- Effective Vision Model：由 ChatService 通过 dataclasses.replace 即时构造，不持久化。

### 数据更新与销毁

- chat_images 行：仅允许由 Chat Image Repository 写入与软删；任何其他模块不应直接 UPDATE 该表。
- chat-images storage 对象：仅允许由 Chat Image Service 写入；只有 sweeper 任务在软删后清理。
- chat_messages.image_ids：写入归属 ChatService；删除联动来自 chat_messages 主体的删除。
- Vision Policy 常量：由 core/llm/vision_policy.py 维护，随版本发布更新。

### 责任边界

- Chat Image Service 不感知"视觉模型"概念；它只负责图片资产的存与取。
- ChatService 不感知"如何把图编码为 base64"；它只负责裁决是否需要兜底 model、是否需要把 image_url part 注入当前轮消息。
- LLMClient 不感知"图片"或"视觉"概念；它只负责把 messages 透传给 AsyncOpenAI。
- ContextBuilder 不感知 image_id 与 storage；它只接受由调用方构造好的 data URL 列表，并在最后一条 user 消息上拼装 content parts。
- 前端 chat-input 不感知 LLM 的视觉能力；它只负责"附件栏全 ready 才允许发送"以及与上传接口的契约。

### 与现有模块的责任分离

- 与 generated_images：互不读写对方数据；image_generation 工具链产出的图不会进入 chat_images 路径。
- 与 RAG / 嵌入 / 检索：上传图不进入 embedding 索引，不影响检索召回。
- 与 LLM 配置 / 设置面板：本模块只读取 provider 与 model；不写入持久化配置；vision 标记仅是 `/config/models` 输出层的派生信息。
- 与 dual-track session memory：StoredMessage.content 保持字符串约束；image_ids 仅作为 metadata 出现，不参与 token_counter 与 Compressor 的字符串度量。

---

## 五、文档自检

- [x] 每条数据流都能找到对应的输入来源与输出目标。
- [x] 每个接口都映射到至少一条数据流。
- [x] 上传、发送、历史回看、删除联动、模型披露五条流互不交叉、责任清晰。
- [x] 内部接口与外部接口区分清楚，外部接口集中在 chat / config 路由命名空间。
- [x] 数据归属与销毁责任未在多个模块之间漂移。
- [x] 不引入超出 architecture.md 的子组件，不为未在数据流中使用的接口留位置。
