# img_upload 模块 goals-duty.md

本文档定义 `img_upload` 模块的设计目标与职责边界。

该模块面向 Newbee Notebook 的 main 面板 agent 对话框，用于让用户在聊天输入框处上传图片，并以原生多模态消息的形式提交给当前 LLM provider，使 agent 能"看图回答"。

---

## 一、模块定位

**一句话说明**：`img_upload` 模块是 Newbee Notebook 聊天链路上的多模态输入接入层；它负责"用户上传 → 持久化存储 → 在当前一轮对话中以 OpenAI 兼容 image_url 形式送入 LLM"，并保证当前所选 LLM model 不具备视觉能力时，仅在本次调用临时切换到 provider 默认视觉模型。

**如果没有这个模块**：

- 用户无法在对话框中附带图片向 agent 提问，所有"看图说话"类需求被迫绕到外部工具或文档上传链路。
- 当用户选择的 LLM model 没有视觉能力时，系统无法给出明确的引导或自动兜底。
- 上传图片的存储、生命周期、安全边界没有统一归属，容易与现有的 `generated_images` 工具产物混在一起。
- 历史会话中曾经附带的图片在多轮对话或 agent 工具循环中是否重传给 LLM 没有明确契约，导致 token 成本不可预测。

---

## 二、Design Goals（设计目标）

### G1：让用户在聊天框附图问问题

模块的首要目标是支持用户在 main 面板的聊天输入框附上图片，与同一条文本消息一起提交给 agent，并由 agent 看到图后再生成回答。

### G2：复用现有聊天 LLM 配置，不新增多模态独立配置

视觉能力使用用户当前在设置面板选择的 provider 与 API key；模块不为多模态新增 provider 选择、不暴露独立的视觉模型选项 UI。

### G3：在当前所选 model 不具备视觉能力时单次兜底

如果用户当前所选 model 不在 provider 视觉白名单内，本模块允许在本次 chat 调用上临时切换到 provider 的默认视觉模型，仅本调用生效，不写回任何持久化配置。

### G4：图片输入只影响当前一轮，不污染历史压缩链路

上传的图片以 OpenAI content parts 的形式注入"当前一轮 user 消息"；历史轮次的图片不重新传给 LLM，也不破坏现有 dual-track session memory 与 token compaction 子系统的字符串语义。

### G5：上传是事实，送 LLM 是消费

模块永久保留上传原图，不因任何"为了 LLM 调用而做的尺寸/编码处理"丢失原图；交给 LLM 时可对原图做不持久化的缩放或重编码以控制带宽与 token。

### G6：失败可见，不悄悄退化

上传失败、视觉兜底切换、image_id 跨会话非法等情况都必须以可观测的方式（4xx/207、结构化日志、明确的错误项）呈现给前端或运维，不允许在静默状态下退化为"纯文本继续发送"。

### G7：边界与现有 generated_images 严格分开

用户上传图片是"外部输入事实"，与 image_generation 工具产出的"生成图片"在生命周期、来源信任、UI 语义上完全不同；两者使用平行的存储路径与 DB 表，互不重叠。

---

## 三、Duties（职责）

### D1：接收用户上传图片

模块负责通过聊天会话维度的上传接口接收一组图片文件，进行格式（PNG / JPEG / WEBP）、大小、张数与真实 MIME 校验，并落盘到统一的 storage backend。

### D2：维护 chat_images 资产

模块负责为每一张上传成功的图片维护一条 `chat_images` 记录，承载 storage_key、mime_type、尺寸、来源 session 以及软删标记，并提供按 image_id 读取原图与缩略图的接口。

### D3：把 image_id 绑定到聊天消息

模块负责扩展现有 ChatRequest，让前端可以携带 `image_ids` 列表；后端在处理聊天请求时，将这些 id 解析并绑定到当前消息，使消息历史可以回看到该消息曾附带哪些图。

### D4：在当前轮 user 消息上注入多模态 content

模块负责在 ContextBuilder 构造"当前一轮 user 消息"时，把绑定到该消息的 image_id 加载为 inline base64 data URL，并以 OpenAI 兼容的 `{type: "image_url", image_url: {url: ...}}` part 形式追加到 content 数组。

### D5：判断当前 model 是否具备视觉能力

模块负责维护并提供一个视觉模型白名单与 provider 默认视觉模型的查询能力，使聊天链路在调用 LLM 前能判断当前 runtime model 是否能处理图片。

### D6：在不具备视觉能力时单次兜底切换

当本轮聊天确实携带图片，且当前 runtime model 不在视觉白名单时，模块负责对 runtime config 做一次只在本次调用生效的 model 替换，并记录可诊断日志。

### D7：保护跨会话边界

模块负责校验聊天请求中传入的所有 image_id 必须属于当前 session，禁止跨会话引用图片资源。

### D8：与会话生命周期联动清理

模块负责在 session 或 message 被删除时，对其名下 chat_images 做联动软删除，并提供后续 storage 文件清理的契约入口。

### D9：限制上送 LLM 时的图片体积

模块负责在把图片转成 base64 给 LLM 之前，对长边超过既定阈值的图执行不持久化的缩放，使 chat 请求体可控。原图不被改动。

### D10：记录可诊断状态，不泄密

模块负责在上传校验失败、视觉兜底、跨会话非法引用等情况下输出结构化日志，但不得记录 base64 图像内容、API key 或完整请求体。

---

## 四、Non-Duties（非职责）

### N1：不改造非聊天链路

模块不为 RAG 检索、文档解析、嵌入、索引等非聊天链路加入视觉能力或图片输入；那些链路若需要视觉能力，由各自模块自行讨论。

### N2：不让上传图进入向量索引

上传图片只服务"当前一轮 user 消息"以及前端历史回看，不进入 pgvector / Elasticsearch / RAG 检索。

### N3：不在历史轮次重传图给 LLM

历史消息中的 image_id 仅作为应用层语义被前端读取与显示；ContextBuilder 不会在后续轮次或 agent 工具循环中把它们重新注入 LLM 的 content。

### N4：不接入视频与文件多模态

本期仅支持图片输入。GLM-5V 系列与 Qwen 视觉模型同时支持的 video_url / file_url 类型不在本模块范围内。

### N5：不改写用户的 LLM 配置

视觉模型兜底是一次性 runtime 替换，模块不写回 config DB、不修改 llm.yaml、不改变前端设置面板里的当前选择。

### N6：不实现 explain / conclude 模式的附图

ChatRequest 的 mode 中只有 agent 与 ask 允许携带 image_ids；explain 与 conclude 是基于已选中文档片段的右键指令，本模块不为其增加附图语义。

### N7：不复用 generated_images 表

`generated_images` 是 image_generation 工具的产物，与用户上传图片在来源信任与生命周期上不同；本模块新建独立的 `chat_images` 表，不在 generated_images 上加 source 字段做合并。

### N8：不负责前端样式系统

模块仅约定前端附件栏的行为契约（多张图、上传中状态、失败重试、未全 ready 禁送）；具体视觉样式、动效、深色模式适配交给前端组件库与现有 chat-input 风格。

### N9：不承诺第三方视觉模型的回答质量

模块只确保把图片以 provider 文档要求的格式传到 LLM；最终回答质量由所选模型决定，不在本模块责任范围。

---

## 五、设计约束与假设

### 约束

1. Qwen 与 Zhipu 的 OpenAI-compatible 端点都接受同一形式的 `{type: "image_url", image_url: {url: ...}}` content part，url 可为 https URL 或 `data:image/...;base64,` data URL。
2. 现有聊天链路通过 `LLMClient`（基于 `AsyncOpenAI`）发送消息，messages 透传给上游 SDK；当前消息 schema 仅支持字符串 content。
3. 现有 `core/context/session_memory.StoredMessage.content` 是 `str`，是 dual-track memory、Compressor、token_counter 等子系统共同依赖的不变量。
4. 现有 storage 抽象 `StorageBackend` 同时支持 local 与 MinIO 后端，已被 generated_images 与文档资产复用。
5. 部署形态可能是内网 / docker-compose / 本地，不能假设上游 LLM 能反向访问 Newbee 后端的 URL。
6. API key 不允许写入日志、metadata 或前端响应。

### 假设

1. 用户在 main 面板对话时，附图问问题的核心场景是"基于这张图问 agent"，而不是"长时间保留图作为知识库素材"。
2. 用户可以接受发送按钮在所有附图上传完成前保持禁用，不需要"边发边上传"。
3. 单条消息最多 10 张图、单图最多 10 MB 是合理上限，覆盖截屏、设计稿对比等典型场景。
4. Zhipu 已将默认模型切换为 `glm-5v-turbo`，但仍然存在用户主动选择 `glm-5` 等非视觉模型的情况。
5. 用户当前所选 provider 的 API key 可同时调用同 provider 的视觉模型，不需要为视觉单独申请 key。

---

## 六、与其他模块的关系

| 模块 | 关系 | 说明 |
|------|------|------|
| Chat API（chat router） | 调用方 | 在 ChatRequest 增加 image_ids 字段，转交给 ChatService |
| ChatService / SessionManager | 协作方 | 接收 image_ids，调用 ContextBuilder 构造多模态当前轮消息，并在调用 LLMClient 前应用 VisionPolicy |
| LLMClient | 被依赖 | 透传 OpenAI 兼容多模态 messages，不需要感知"视觉"概念 |
| LLMRuntimeConfig | 被依赖 | 提供当前 provider 与 model；本模块通过 dataclasses.replace 单次覆盖 model |
| ContextBuilder | 协作方 | 在"当前一轮 user 消息"上拼接 content parts；历史消息保持字符串 content |
| StorageBackend | 被依赖 | 持久化原图至 `chat-images/{session_id}/{image_id}.{ext}` |
| generated_images | 平行模块 | 独立表与独立路径，互不复用 |
| 设置面板 / Config API | 关联模块 | `/config/models` 增加 vision 能力标记，但不新增独立视觉配置项 |
| llm_title_aided | 关联规划 | 共享"Zhipu 默认模型 = glm-5v-turbo"这一既定方向；不共享代码路径 |

---

## 七、文档自检

- [x] 可以用一句话说明模块存在意义：让用户在 main 面板对话框中附上图片向 agent 提问。
- [x] 明确只服务聊天链路，不污染检索 / 索引 / 文档解析。
- [x] 明确复用现有聊天 LLM 配置，不新增视觉专用 provider/model 配置。
- [x] 明确历史中的图片不重传 LLM，仅作为应用层语义。
- [x] 明确与 generated_images 的边界。
- [x] Duties 可被后续 architecture / data-model / dfd-interface / test 文档验证。
