# img_upload 模块 test.md

本文档说明如何验证 `img_upload` 模块在真实协作环境中是可信的。该文档基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md)、[data-model.md](data-model.md)、[dfd-interface.md](dfd-interface.md) 与 [non-functional.md](non-functional.md)。

---

## 一、Module Test Profile（模块测试档案）

- **模块原型**：混合原型
  - `Vision Policy`、`Chat Image Service.load_for_llm`、`ContextBuilder` 扩展 → **纯逻辑**
  - `ChatService` 视觉兜底与多模态注入编排 → **服务编排**
  - `chat_images` HTTP 路由与 ChatRequest 扩展 → **桥接 / 适配**
  - `Chat Image Service` 与 `StorageBackend` 协作 → **外部依赖封装（轻）**
- **主要测试类型**：unit + contract + integration
- **Mock 边界**：
  - `StorageBackend`：单元/契约测试中使用内存 fake；集成 smoke 测试中允许使用 local backend。
  - `LLMClient` 与 `AsyncOpenAI`：在 ChatService 编排测试中 mock，验证 messages 形态与 vision_fallback 命中情况；不在测试中对 provider 真实发送视觉请求。
  - DB（chat_images / chat_messages）：单元测试中使用 SQLite 或 in-memory；契约/集成测试中使用项目既有测试 DB 配置。
  - 前端浏览器 API（剪贴板 / 拖拽 / getDisplayMedia）：单元测试中通过 jsdom + 事件 dispatch 模拟。
- **测试归属目录**：
  - `tests/unit/core/llm/test_vision_policy.py`
  - `tests/unit/application/services/test_chat_image_service.py`
  - `tests/unit/application/services/test_chat_service_vision_fallback.py`
  - `tests/unit/core/context/test_context_builder_multimodal.py`
  - `tests/contract/api/test_chat_images_endpoints.py`
  - `tests/contract/api/test_chat_request_image_ids.py`
  - `tests/integration/chat_image_upload/`（端到端冒烟）

---

## 二、Test Scope（测试范围）

### 覆盖

- 上传请求的格式校验、MIME 真实性校验、限额拒绝、部分失败 207 响应。
- chat_images 行与 storage 对象的写入一致性、跨会话引用拒绝、软删联动。
- ChatRequest 增加 image_ids 字段后的契约（mode 限制、跨会话拒绝、空数组等价于无图）。
- Vision Policy 对已知 provider/model 的判定与默认视觉模型回退。
- ChatService 在本轮存在 image_ids 且 model 不在白名单时进行单次 model 替换、写入 vision_fallback 日志、不修改任何持久化配置。
- ContextBuilder 在传入 `current_image_data_urls` 时仅修改最后一条 user 消息的 content 形态；历史消息保持字符串 content。
- `Chat Image Service.load_for_llm` 的长边缩放与 base64 编码不修改原图。
- 删除 session 或 message 时联动写软删；后续读取接口拒绝返回软删图。

### 不覆盖

- StorageBackend 的具体后端实现行为（local / MinIO 各自的存储语义属于 infrastructure 层测试）。
- LLMClient 与 AsyncOpenAI 的 SDK 行为（属于 LLM 模块自身测试）。
- 上游 provider 的视觉理解质量（不在测试范围）。
- generated_images 工具链的功能（属于 image_generation 工具自身测试）。
- 前端样式与动效；前端测试只覆盖契约相关行为（禁送条件、附件栏状态机）。

### 混合原型的归属说明

- 纯逻辑部分（Vision Policy、缩放编码、ContextBuilder 扩展）以单元测试为主，重点在 Critical Scenarios。
- 桥接部分（chat_images 路由、ChatRequest 扩展）以契约测试为主，重点在 Contract Specification。
- 服务编排部分（ChatService 视觉兜底）以单元 + 集成测试为主，重点在 Integration Points 与 Critical Scenarios。

---

## 三、Critical Scenarios（关键场景）

### 1. Vision Policy

- 已知视觉模型：(qwen, qwen3.5-plus) / (zhipu, glm-5v-turbo) / (openai, gpt-4o) → `is_vision_capable` 返回 True。
- 已知非视觉模型：(zhipu, glm-5) / (openai, gpt-4o-mini-text-only-假设) → 返回 False。
- 未知 provider：`is_vision_capable("unknown", "x")` → False；`fallback_vision_model("unknown")` → None。
- 默认视觉模型查询：fallback_vision_model("zhipu") = "glm-5v-turbo"。

### 2. Chat Image Service

#### 正常路径
- 单图 PNG 上传：返回 image_id、mime=image/png、width/height 与原图一致；storage 对象与 chat_images 行均存在。
- 多图混合 (PNG + JPEG + WEBP) 一次上传：依次成功，每张图取得唯一 image_id。
- `load_for_llm` 对 4096×4096 PNG：返回 long-edge ≤ 2048 的 base64 data URL；原图不变（再次调用 `load_preview` 仍是原始尺寸）。

#### 异常路径
- 文件后缀是 .png 但二进制是 PDF：被 magic byte 校验拒绝。
- 文件大于 10 MB：拒绝。
- 一次性上传超过 10 张：超出部分进入 errors，前面成功项进入 images（207）。
- StorageBackend 写入失败：整笔上传 5xx；DB 不留半行。
- 跨会话引用 image_id：`assert_belongs_to_session` 抛错并被路由转为 400。

### 3. ChatService 视觉兜底

#### 正常路径
- 当前 (provider=zhipu, model=glm-5v-turbo)，本轮存在 image_ids → 不触发 fallback；LLMClient 收到 model=glm-5v-turbo。
- 当前 (provider=zhipu, model=glm-5)，本轮存在 image_ids → 触发 fallback；LLMClient 收到 model=glm-5v-turbo；运行期 LLMRuntimeConfig 副本被丢弃，DB 与 yaml 未变。
- 当前 (provider=qwen, model=qwen3-max)，本轮存在 image_ids → 触发 fallback；LLMClient 收到 model=qwen3.5-plus。
- 本轮不存在 image_ids 且 model 不在视觉白名单 → 不触发 fallback；按用户原 model 调用。

#### 异常路径
- vision_fallback 命中但 provider 没有默认视觉模型（构造一个未知 provider 注入测试）→ chat 请求 400 而不是悄悄不切换。
- image_ids 中存在跨会话条目 → 整个 chat 请求 400；不调用 LLMClient；不写 chat_messages.image_ids。
- image_ids 中存在不存在的 id → 整个 chat 请求 400。

### 4. ContextBuilder 多模态扩展

- 不传 `current_image_data_urls`：行为与现有完全一致；历史消息和 current user message 都是 `{role, content: str}`。
- 传入 1 个 data URL：最后一条 user 消息为 `{role: "user", content: [{type: "text", text}, {type: "image_url", image_url: {url: data_url}}]}`；历史消息保持字符串 content。
- 传入 N 个 data URL：按顺序追加 N 个 image_url part。
- current_message 为空但 data_urls 非空：拒绝（行为定义为不构造空 user 消息；具体由实现决定，但需要单元测试锁定）。

### 5. Chat Image Service 缩放与编码

- long-edge ≤ 2048 的 PNG：load_for_llm 返回字节与原图等价（允许重新编码但尺寸不变）。
- long-edge > 2048 的 PNG：返回字节解码后 long-edge = 2048。
- 透明通道 PNG：保持透明信息或被允许转为带白底 JPEG（实现选其一，需在测试中锁定）。
- 输入 WEBP：返回字节可被 LLM provider 解读（最低保证为 PNG/JPEG/WEBP 之一）。

### 6. 删除联动

- 删除 chat_session：所有关联 chat_images.deleted_at 被写；后续读取接口对这些 image_id 返回 404。
- 删除单条 chat_message：消息上的 image_ids 引用被释放；若该图未被同 session 其他消息引用，可选择立即软删（实现选其一，需测试锁定）。
- sweeper 任务：在测试 mock 时间轴下，软删超过保留窗口的图被清理；DB 行被移除；StorageBackend 对象被删除。

---

## 四、Contract Specification（契约规约）

### 1. POST /api/v1/chat/sessions/{session_id}/images

- 请求：multipart/form-data，`files` 字段重复出现，1 至 10 项；session_id 在路径中。
- 鉴权：未认证 401；session 不存在或不属于当前用户 403。
- 全部成功（HTTP 200）：
  ```json
  {
    "images": [
      {"image_id": "uuid", "mime_type": "image/png", "size_bytes": 12345,
       "width": 1024, "height": 768,
       "preview_url": "/api/v1/chat/images/<uuid>/data",
       "thumbnail_url": "/api/v1/chat/images/<uuid>/thumbnail"}
    ],
    "errors": []
  }
  ```
- 部分成功（HTTP 207）：images + errors 同时存在；errors 中包含 `{filename, code, detail}`，code 取值在固定枚举中。
- 全部失败（HTTP 400）：返回 `{detail: "..."}`，不返回 207。
- 限额超限（HTTP 413）：单图 > 10 MB 时使用 413；count > 10 时使用 422 或 400（实现选其一，测试锁定）。

### 2. GET /api/v1/chat/images/{image_id}/data

- 鉴权：未认证 401；图不属于当前用户的可访问 session 时 403；不存在或软删后 404。
- 成功：HTTP 200，Content-Type 为图片 MIME，body 为原图字节。

### 3. GET /api/v1/chat/images/{image_id}/thumbnail

- 鉴权：同上。
- 成功：HTTP 200，Content-Type 为 `image/webp` 或 `image/png`，body 为缩略图字节。

### 4. POST /api/v1/chat/notebooks/{notebook_id}/chat/stream（扩展现有）

- 请求体增加 `image_ids: list[string]`，可选；缺省视为空数组。
- mode 不在 {agent, ask} 时若 image_ids 非空 → HTTP 400 `{detail: "image_ids only allowed in agent/ask mode"}`。
- image_ids 中含跨会话或不存在条目 → HTTP 400 `{detail: "invalid image_ids: ..."}`。
- 成功：保持现有 SSE 事件结构不变；不引入新的 SSE 事件类型。

### 5. GET /api/v1/config/models（扩展现有）

- 响应中每个模型条目新增字段 `vision: bool`，由 Vision Policy 推导。
- 历史消费方未更新时不应破坏（vision 字段为新增，旧客户端忽略即可）。

---

## 五、Integration Points（集成点测试）

### 1. 与 StorageBackend 交互

- 上传写入失败时，chat_images 行不应被创建；测试通过注入 fake backend raise 验证。
- 读取 deleted_at 非空的图：业务接口必须 404；StorageBackend 直接调用允许成功（这是为 sweeper 留出的能力）。
- 软删后 sweeper 调用 StorageBackend.delete：失败时应记录错误并保留软删标记，下一轮重试；不应让 chat 流程感知。

### 2. 与 chat_messages 表交互

- ChatService 在 LLM 成功响应后写入 chat_messages.image_ids；image_ids 为非空数组时使用 JSONB 序列化。
- 当 LLM 调用失败时，image_ids 是否写入由 ChatService 既有失败语义决定（与现有"消息写入失败时回滚"保持一致），测试需锁定不出现"图被绑定到不存在的消息"。

### 3. 与 ContextBuilder / SessionMemory 交互

- 当前轮注入 image_url part 不应改变 SessionMemory 的存储形态：测试断言写入 SessionMemory 的 `StoredMessage.content` 仍是字符串，`metadata.image_ids` 包含本次的 ids。
- 后续轮聊天构造时，ContextBuilder 在不传 `current_image_data_urls` 的情况下不能从历史 metadata 自动重传图。

### 4. 与 LLMClient 交互

- LLMClient 收到的 messages 在末位 user 消息上有 image_url part；其余消息保持字符串 content。
- vision_fallback 命中时 LLMClient 收到的 model 与原 LLMRuntimeConfig 不同；fallback 后再次发起非附图 chat，model 恢复为用户原选择。

### 5. 与 LLM 配置 / Config API 交互

- vision_fallback 不修改 config_db；测试断言一次附图 chat 后 `get_llm_config_async` 返回值与之前相同。
- `/config/models` 返回的 vision 标记与 Vision Policy 常量保持一致；任何对常量的修改需要在该契约测试中体现。

### 6. 与 generated_images 隔离

- 任何 chat_images 接口不应返回 generated_images 行，反之亦然；通过对两类资产分别构造样本数据后调用对应接口验证。

---

## 六、Verification Strategy（验证策略）

- **单元测试**：使用 pytest + fake backend；不依赖网络；运行时间应在毫秒级，可在每次提交本地与 CI 中执行。
- **契约测试**：使用 FastAPI TestClient 对路由端点真实发送 HTTP 请求；ChatService 与 StorageBackend 替换为 fake 实现；DB 使用项目既有测试 DB fixture。
- **集成 smoke 测试**：在 docker-compose 起的本地后端 + local StorageBackend 上跑端到端：上传 → 发起非视觉 chat（mock LLM）→ 历史回看 → 删除联动 → sweeper 清理。视觉 LLM 的真实调用不在自动化范围内，仅由开发者在引入新视觉模型时人工验证。
- **前端测试**：使用 vitest + testing-library + jsdom；剪贴板 / 拖拽 / 截屏入口通过事件 dispatch 模拟；契约关注"附件栏状态机"与"发送按钮禁送条件"。
- **mock 边界声明**：所有自动化测试中，调用真实第三方 LLM API 是被禁止的；只能 mock LLMClient 或更上游的 AsyncOpenAI transport。
- **人工验证**：
  - 视觉真实质量（看图准确性）需在引入新模型或修改 Vision Policy 时人工触发。
  - 大图（接近 10 MB）的上传与缩放性能在性能回归阶段人工抽样。
  - 浏览器剪贴板 / 截屏入口在主流浏览器上的兼容性人工抽样。
- **CI 标记**：
  - unit + contract 测试为默认门禁。
  - integration 测试标记为 smoke，在 PR 合入主干前的 pipeline 中执行一次。
  - 视觉 LLM 真实调用不进 CI。

---

## 七、文档自检

- [x] 已声明模块原型（混合原型）并解释各部分归属。
- [x] 已根据原型调整章节侧重：契约部分详细，关键场景详细，验证策略中明确了 mock 边界与 CI 标记。
- [x] 关键职责（D1–D9）每条都有对应的验证场景：上传校验、image_id 绑定、跨会话拒绝、视觉兜底、当前轮注入、缩放编码、删除联动。
- [x] 桥接部分包含 Contract Specification（5 个端点）。
- [x] 集成点说明了与 StorageBackend、ContextBuilder、LLMClient、Config API 的失败处理预期。
- [x] mock 边界明确：禁止测试中调用真实第三方 LLM API。
- [x] 测试归属目录与项目既有 `tests/unit`、`tests/contract`、`tests/integration` 分类一致。
