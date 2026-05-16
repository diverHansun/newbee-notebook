# img_upload 模块 non-functional.md

本文档明确 `img_upload` 模块在功能正确之外必须满足的工程约束。该文档基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md) 与 [dfd-interface.md](dfd-interface.md)。

---

## 一、Quality Priorities（质量优先级）

按重要性从高到低：

1. **结果可预测性优先于带宽节省**。当用户附图发送时，附图必须以 provider 文档要求的形式抵达 LLM；不允许因网络或编码捷径出现"图被静默丢弃""图变成纯文本占位"等行为。
2. **聊天主路径不被图片处理拖慢**。图片读取、缩放、base64 编码必须在 thread executor 中执行，事件循环不被 Pillow 的同步调用阻塞；任何上传或读取错误不应阻断已经成功的部分。
3. **安全边界优先于功能丰富**。在跨会话引用、API key 安全、日志含密这三件事上不允许打折；可以在体验细节上让步，不可以在边界守卫上让步。
4. **简单实现优先于横向扩展能力**。当前阶段优先 docker-compose / 内网 / 本地部署形态可用；多副本上传一致性、storage 跨可用区复制等延后。
5. **token 成本可预测优先于多轮视觉记忆**。历史不重传图是为了 token 上限可控；放弃多轮视觉记忆能力以换取成本边界。

---

## 二、Operational Constraints（运行约束）

### 1. 限额（强约束）

- 单次上传请求最多 10 张图。
- 单图最大字节数 10 MB。
- 单图必须为 PNG / JPEG / WEBP 之一，由 magic byte 校验。
- 单条聊天消息引用的 image_ids 数量与一次上传上限一致；超出由后端拒绝。
- 送 LLM 时，单图长边超过 2048 px 时由 `load_for_llm` 缩放至 2048 px；原图保留。

### 2. 性能与时延

- 上传接口在通过校验后应在百毫秒级返回，不等待 sweeper 或缩略图缓存预热。
- `load_for_llm` 的缩放与编码应在 thread executor 中执行，避免阻塞 asyncio 事件循环；单图处理目标 < 200 ms（在 8 MB JPEG 输入下）。
- chat 请求在 vision_fallback 命中后不应叠加可感知延迟；fallback 仅是一次配置副本构造，不引入额外网络往返。

### 3. 吞吐与并发

- 当前阶段假定单进程后端、docker-compose 单副本部署，不针对多副本一致性设计。
- 同一用户在同一会话内同时上传多张图时允许并发，前端控制最大并发为 4，避免压垮后端事件循环。
- chat 流式请求并发度由现有 ChatService 决定，本模块不引入额外限流。

### 4. 资源占用

- 上传时不在内存中保留完整请求体；通过流式或分块写入 StorageBackend 减少峰值占用。
- `load_for_llm` 处理过程中允许加载完整原图到内存（受 10 MB 上限保护）；编码后立即释放。
- 缩略图允许后端落盘缓存或仅在内存中按 LRU 缓存，缓存大小受现有进程内存预算约束。

### 5. 外部依赖稳定性

- 上游 LLM provider（Qwen / Zhipu / OpenAI）超时与失败由 LLMClient 已有重试与超时策略覆盖；本模块不为视觉调用引入额外重试，避免与重试策略叠加。
- StorageBackend 失败时上传请求必须明确报错，不允许"DB 行已写但对象未落盘"的不一致状态。
- 上传与读取接口都不依赖外网；单图 long-edge 缩放与 base64 编码完全在本进程内完成。

### 6. 成本与限额

- 视觉模型单次调用成本明显高于纯文本模型；模块不在后台主动重发视觉请求，重试由用户主动触发。
- 不为附图聊天引入"自动思维链放大"；vision_fallback 仅替换 model 名，不打开 thinking 模式或调高 max_tokens。
- 历史不重传图本身就是成本控制手段，不应在体验细节中悄悄回退。

### 7. 运行环境

- 后端 Python 进程需引入 Pillow 依赖；filetype 或等价 magic byte 库需引入。
- 前端依赖现代浏览器的 ClipboardEvent、DataTransfer、`navigator.mediaDevices.getDisplayMedia`；不可用时降级隐藏对应入口，但保留 file picker 与拖拽。
- StorageBackend 已有 local 与 MinIO 后端均需支持新的 `chat-images/` 命名空间；不引入新的存储类型。

---

## 三、Reliability & Observability（可靠性与可观测性）

### 1. 失败语义

- 上传请求中存在部分失败时返回 207 multi-status，body 同时包含 `images` 与 `errors` 字段。前端必须能消费两类条目。
- 全部失败的上传退化为对应 4xx，不返回 207。
- chat 请求中 image_ids 跨会话或不存在时整个请求 400 失败；不允许丢图保送文本。
- vision_fallback 不算失败，但必须是可观测事件。
- StorageBackend 写入失败时整笔上传 5xx 失败；不允许"DB 行已写但对象未落盘"。

### 2. 日志要求

- 上传成功：记录 image_id、size_bytes、mime、width、height、session_id（哈希后或截断），不记录 base64。
- 上传失败：记录原因码（unsupported_mime / oversize / count_exceeded / storage_error / mime_sniff_failed）与计数，不记录文件名（用户可控字段）。
- vision_fallback：记录 provider、from_model、to_model、reason，不记录 api_key。
- 跨会话非法引用：记录 session_id、被拒 image_id、user_id（若可得），并打印为 warning 级。
- 软删与 sweeper：记录批次大小、清理成功 / 失败计数；sweeper 失败必须可重入。

### 3. 指标（建议）

- chat_image_upload_total：按结果（success / partial / failed）打标签的计数器。
- chat_image_upload_bytes：按 MIME 与 result 打标签的直方图。
- vision_fallback_total：按 provider、from_model、to_model 打标签的计数器，用于观测用户配置偏离视觉模型的频率。
- chat_image_load_for_llm_seconds：base64 化前的 IO + 缩放耗时直方图。

### 4. 不可接受的失败

- 上传完成后 image_id 在后续 chat 请求中找不到。
- chat 请求声称含图但 LLM 收到的是纯文本（隐式丢图）。
- 跨会话引用未被拦截，导致用户 A 的图被用户 B 的会话读取。
- API key、base64 内容或完整请求体出现在日志、metadata 或前端响应。
- session/message 删除后 chat_images 仍可被业务接口读取。

### 5. 允许的退化

- 上游视觉 LLM 暂时不可用时，整个 chat 请求按 LLMClient 既有失败语义返回错误；前端可提示"模型不可用"。
- 缩略图接口在缓存未命中时即时计算，允许首次响应略慢。
- 截屏入口在浏览器 API 不可用时隐藏；其他上传方式仍可用。
- vision_fallback 命中时若 provider 没有默认视觉模型（理论上不应发生），整个 chat 请求 400，并提示用户切换到支持视觉的 provider。

---

## 四、Trade-offs & Deferred Requirements（权衡与暂缓项）

### 1. 不实现多副本上传一致性

当前阶段不针对多后端副本场景设计上传幂等键、对象 ETag 校验、跨副本同步。理由：单副本部署足够覆盖现有场景；多副本一致性会引入幂等键 schema 与回收策略两条复杂线，超出本期范围。

### 2. 不实现按图搜索 / 视觉检索

上传图不进入 embedding，因此不支持"用图找历史会话"或"以图搜文档"。理由：与 RAG 索引的边界一致性；视觉检索是一项独立功能，应独立讨论。

### 3. 不实现视觉多轮记忆

历史不重传图。如果未来需要让 agent 在多轮对话中持续看到旧图，应在 agent 记忆模块独立讨论；本模块不预留多轮视觉路径。

### 4. 不实现自动 OCR 兜底

当前不对上传图做 Newbee 内部 OCR / 视觉理解兜底。理由：让 LLM 自己看图是模块的核心价值；如果 LLM 看不懂，不应再叠加一层非确定性。

### 5. 不在 LLMClient 中加视觉策略

视觉策略保持在 ChatService 一侧。理由：LLMClient 是面向 batch-2 的薄封装；将业务概念塞入会破坏分层。详见 architecture.md 中"被放弃的方案"。

### 6. 不在本期接入视频与文件多模态

GLM-5V 与 Qwen 视觉模型同时支持 video_url 与 file_url。本期不接入，原因是 video / file 与现有 MinerU 文档解析职责重叠，需要独立讨论后再合并。

### 7. 不在本期实现强细粒度限流

允许同一用户在同一会话内并发上传，但不引入用户级 / 会话级 RPS 限流。理由：现有部署用户体量未到限流阈值；后续若出现滥用迹象可在 Upload Surface 前置加一层中间件，不影响本模块结构。

### 8. 不在本期为旧 zhipu.model=glm-5 用户做强制迁移

如果用户主动选择了 glm-5，本模块通过 vision_fallback 在附图时单次切换到 glm-5v-turbo；不做 DB 中现存配置的批量重写。理由：尊重用户主动选择是 goals-duty.md 中已确认的边界（N5）。
