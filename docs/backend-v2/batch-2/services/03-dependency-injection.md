# 依赖注入层变更设计

## 1. 当前 DI 架构

### 1.1 整体结构

`api/dependencies.py` 使用 FastAPI 的 `Depends()` 机制实现依赖注入，分为三层:

```
请求进入
  |
  v
Repository 层 (每请求新建)
  get_db_session() -> SQLAlchemy AsyncSession
  get_library_repo(), get_notebook_repo(), get_session_repo(), ...
  |
  v
Core 单例层 (应用生命周期)
  get_llm_singleton()           -> LLM (模块全局变量)
  get_embedding_singleton()     -> BaseEmbeddingModel (模块全局变量)
  get_pg_index_singleton()      -> VectorStoreIndex (模块全局变量)
  get_es_index_singleton()      -> VectorStoreIndex (模块全局变量)
  |
  v
Service 层 (每请求新建)
  get_session_manager_singleton() -> SessionManager (每请求新建，含单例 index)
  get_chat_service()             -> ChatService
  get_document_service()         -> DocumentService
  ...
```

### 1.2 生命周期管理

| 组件 | 作用域 | 创建方式 | 原因 |
|------|--------|---------|------|
| DB Session | 每请求 | async generator + yield | 请求结束自动关闭连接 |
| Repository | 每请求 | Depends 链 | 绑定到请求级 DB Session |
| LLM | 应用级单例 | 模块全局变量 | 重量级资源，复用 |
| Embedding | 应用级单例 | 模块全局变量 | 重量级资源，复用 |
| PGVector Index | 应用级单例 | 异步模块全局变量 | 连接池复用 |
| ES Index | 应用级单例 | 异步模块全局变量 | 连接池复用 |
| SessionManager | 每请求 | Depends 链 | 包含请求级 repo + 每请求新建 LLM |
| ChatService | 每请求 | Depends 链 | 包含请求级 repo + SessionManager |

注意: `get_session_manager_singleton()` 名称有误导性，实际是每请求新建（内部 `build_llm()` 每次调用创建新实例）。保留单例的仅有 index 资源。

### 1.3 LLM 每请求新建的原因

代码注释说明:

```python
# Use a fresh LLM client per request. A shared singleton client can leak
# transport state across aborted stream + immediate fallback requests.
```

当用户中断流式请求后立即发起新请求时，共享的 LLM 客户端可能残留 httpx transport 状态，导致新请求失败。每请求新建避免此问题。

### 1.4 运行时重置机制

```python
reset_llm_singleton()       # LLM 提供商切换时调用
reset_embedding_singleton() # Embedding 提供商切换时，同时清除 pgvector/ES index
```

由 AppSettingsService 在运行时配置变更后触发。

## 2. Core 重构后的 DI 变更

### 2.1 SessionManager 构造变更

当前 SessionManager 构造:

```python
async def get_session_manager_singleton(session_repo, message_repo):
    llm = build_llm()
    pg_index = await get_pg_index_singleton()
    es_index = await get_es_index_singleton()
    return SessionManager(
        llm=llm,
        session_repo=session_repo,
        message_repo=message_repo,
        pgvector_index=pg_index,
        es_index=es_index,
        es_index_name="newbee_notebook_docs",
    )
```

重构后，新 SessionManager（`core/session/session_manager.py`）的构造参数将变化:
- 移除 `session_repo` 和 `message_repo`: SessionManager 不再直接访问数据库
- 移除 `es_index`: ES 检索由 RAG Tool 内部管理，不再通过 SessionManager 传递
- 保留 `llm`: AgentLoop 需要 LLM 进行工具调用和最终回答
- 保留 `pgvector_index`: 传递给 RAG Tool 构建

预计新构造:

```python
async def get_session_manager_dep(
    session_repo: SessionRepositoryImpl = Depends(get_session_repo),
    message_repo: MessageRepositoryImpl = Depends(get_message_repo),
):
    llm = build_llm()
    pg_index = await get_pg_index_singleton()
    es_index = await get_es_index_singleton()
    return SessionManager(
        llm=llm,
        pgvector_index=pg_index,
        es_index=es_index,
        es_index_name="newbee_notebook_docs",
    )
```

具体参数需等 core/session 模块实现后确定。

### 2.2 ChatService 注入变更

当前:

```python
async def get_chat_service(
    session_repo, notebook_repo, reference_repo,
    document_repo, ref_repo, message_repo,
    session_manager: SessionManager = Depends(get_session_manager_dep),
) -> ChatService:
    return ChatService(
        session_repo=session_repo,
        notebook_repo=notebook_repo,
        reference_repo=reference_repo,
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=message_repo,
        session_manager=session_manager,
    )
```

重构后新增 `pgvector_index` 注入:

```python
async def get_chat_service(
    session_repo, notebook_repo, reference_repo,
    document_repo, ref_repo, message_repo,
    session_manager: SessionManager = Depends(get_session_manager_dep),
) -> ChatService:
    pg_index = await get_pg_index_singleton()
    return ChatService(
        session_repo=session_repo,
        notebook_repo=notebook_repo,
        reference_repo=reference_repo,
        document_repo=document_repo,
        ref_repo=ref_repo,
        message_repo=message_repo,
        session_manager=session_manager,
        pgvector_index=pg_index,
    )
```

`pgvector_index` 供 ChatService 的 `_get_context_chunks()` 方法使用（Explain/Conclude 模式的选区邻近 chunk 检索），不再通过 `session_manager.vector_index` 间接获取。

### 2.3 不变的 DI 配置

以下服务的 DI 配置无需变更:

| DI 函数 | 原因 |
|---------|------|
| `get_library_service()` | 不依赖 core 模块 |
| `get_notebook_service()` | 不依赖 core 模块 |
| `get_session_service()` | 参数不变 |
| `get_document_service()` | 不依赖 core 模块 |
| `get_notebook_document_service()` | 不依赖 core 模块 |

### 2.4 单例层不变

| 单例 | 是否变更 | 说明 |
|------|---------|------|
| `get_llm_singleton()` | 不变 | LLM 仍然每请求新建（通过 `build_llm()`） |
| `get_embedding_singleton()` | 不变 | Embedding 模型全局复用 |
| `get_pg_index_singleton()` | 不变 | pgvector 连接池全局复用 |
| `get_es_index_singleton()` | 不变 | ES 连接池全局复用 |
| `reset_llm_singleton()` | 不变 | 运行时 LLM 切换机制保留 |
| `reset_embedding_singleton()` | 不变 | 运行时 embedding 切换机制保留 |

## 3. import 路径变更

当前:

```python
from newbee_notebook.core.engine import load_pgvector_index, load_es_index, SessionManager
```

重构后:

```python
from newbee_notebook.core.session import SessionManager
from newbee_notebook.core.engine import load_pgvector_index, load_es_index
```

`load_pgvector_index` 和 `load_es_index` 属于基础设施初始化，不属于 engine 模块的 AgentLoop 职责，后续可考虑迁移到 infrastructure 层。但此次重构不涉及此变更。

## 4. 迁移注意事项

### 4.1 SessionManager 名称清理

建议将 `get_session_manager_singleton()` 重命名为 `build_session_manager()`，消除名称与实际行为的不一致（它并非单例）。

### 4.2 向后兼容

DI 层的变更对 API router 透明。router 只通过 `Depends(get_chat_service)` 获取 ChatService 实例，不关心内部构造细节。只要 ChatService 的对外接口（`chat()`、`chat_stream()`、`prevalidate_mode_requirements()`）签名兼容，router 无需修改。

### 4.3 测试影响

单元测试中的 `_build_service()` 辅助函数需要适配:
- 新增 `pgvector_index` 参数（可传 `None` 或 mock）
- `_DummySessionManager` 的接口需与新 SessionManager 对齐
