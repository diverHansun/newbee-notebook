# 服务层 (Application Services) 变更设计

## 背景

`application/services/` 是系统的应用服务层，位于 API 路由与领域/核心模块之间。core 模块的重构（context/engine/session/tools 四模块拆分）将直接影响服务层的调用方式和职责边界。

此外，当前文档处理阻塞逻辑存在两类问题:
1. Agent/Ask 模式: 任意一个文档处于处理中，整个 notebook 的 RAG 功能被阻塞
2. Explain/Conclude 模式: 文档 MinerU 转换完成可查看 markdown，但索引未构建时点击解释/总结失败

## 文档索引

| 文档 | 说明 |
|------|------|
| [01-blocking-fix.md](./01-blocking-fix.md) | 文档处理阻塞逻辑修复设计（独立于 core 重构，可先行实施） |
| [02-chat-service-refactor.md](./02-chat-service-refactor.md) | ChatService 适配 core 模块重构的变更分析 |
| [03-dependency-injection.md](./03-dependency-injection.md) | 依赖注入层（DI）变更设计 |
| [04-api-layer.md](./04-api-layer.md) | API 路由层、SSE 协议、请求响应模型适配设计 |

## 建议阅读顺序

01-blocking-fix --> 02-chat-service-refactor --> 03-dependency-injection --> 04-api-layer

01 可独立阅读和实施。02-04 描述 core 重构后的适配变更，建议按序阅读。

## 涉及的文件

### 服务层 (application/services/)

| 文件 | 变更程度 | 说明 |
|------|---------|------|
| `chat_service.py` | 大幅重构 | 阻塞逻辑修复 + 适配新 SessionManager/AgentLoop + 流式事件处理 |
| `session_service.py` | 小幅调整 | context_summary 更新时机变化 |
| `document_service.py` | 无变更 | 文档生命周期管理，不依赖 core 模块 |
| `notebook_document_service.py` | 无变更 | notebook-document 关联管理，不依赖 core 模块 |
| `notebook_service.py` | 无变更 | notebook CRUD，不依赖 core 模块 |
| `library_service.py` | 无变更 | library CRUD，不依赖 core 模块 |
| `app_settings_service.py` | 无变更 | 键值配置，不依赖 core 模块 |

### DI 层 (api/dependencies.py)

| 函数 | 变更程度 | 说明 |
|------|---------|------|
| `get_session_manager_singleton()` | 重构 | SessionManager 构造参数变更，import 路径变更 |
| `get_chat_service()` | 小幅调整 | 新增 pgvector_index 注入 |
| 其他 DI 函数 | 无变更 | 不依赖 core 模块 |
| 单例层 | 无变更 | LLM/Embedding/Index 单例管理不变 |

### API 层 (api/routers/, api/models/)

| 文件 | 变更程度 | 说明 |
|------|---------|------|
| `api/routers/chat.py` | 中等 | SSEEvent 新增 warning/phase/tool_call/tool_result 方法，ChatResponse 新增 warnings 字段 |
| `api/middleware/error_handler.py` | 无变更 | 全局异常处理已完善 |
| `api/models/requests.py` | 无变更 | ChatContext 字段不变 |
| `api/models/responses.py` | 无变更 | ChatResponse 定义在 chat.py 内 |

## 关键设计决策

| 决策 | 结论 | 依据 |
|------|------|------|
| 消息持久化归属 | 保留在 ChatService | SessionManager 只管运行时内存，不直接写 DB |
| `_get_context_chunks()` | 保留在 ChatService | 位置检索（邻近 chunk）与 RAG 语义检索是不同操作，直接注入 pgvector_index |
| 阻塞逻辑修复时机 | 可独立先行实施 | 不依赖 core 模块重构 |
| SSE 协议 | `phase` 为正式协议，`thinking` 仅兼容映射 | 避免旧命名继续成为长期真源 |
| include_ec_context | 保留字段但标记废弃 | 避免前端立即报错，下版本移除 |
