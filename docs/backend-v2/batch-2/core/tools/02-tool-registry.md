# ToolRegistry 与 BuiltinToolProvider 设计

## 1. 设计目标

### 1.1 统一工具列表组装

当前工具构建逻辑分散在三处：ChatMode 调用 `build_tool_registry()`，AskMode 在 `_build_tools()` 中自行构建，Explain/Conclude 各自独立构建。引入 ToolRegistry 作为统一组装点，成为 ModeConfigFactory 获取工具列表的唯一入口。

### 1.2 内置工具与 MCP 工具的透明合并

ToolRegistry 将内置工具（knowledge_base、web_search、time）和 MCP 外部工具合并为统一的 `List[BaseTool]`。AgentLoop 不区分工具来源，LLM 根据工具描述自主决策调用。

### 1.3 模式感知的工具分发

不同交互模式可用的工具集合不同。ToolRegistry 根据 mode 参数返回该模式下的工具子集，替代当前各 Mode 子类各自维护工具列表的做法。

## 2. 架构

### 2.1 组件关系

```
ToolRegistry（应用级单例）
    |
    ├── BuiltinToolProvider            内置工具
    |       持有 pgvector_index, es_index 引用
    |       按 mode 过滤，环境变量控制可用性
    |
    └── MCPClientManager               MCP 外部工具
            懒加载连接，缓存工具列表
            仅 Agent 模式注入
```

### 2.2 调用链

```
ChatService
    |
    +--> ToolRegistry.get_tools(mode, mcp_enabled)
    |        |
    |        +--> BuiltinToolProvider.get_tools(mode)     内置工具
    |        +--> MCPClientManager.get_tools()             MCP 工具（仅 Agent）
    |        +--> 合并，返回 List[BaseTool]
    |
    +--> ModeConfigFactory.build(tools, allowed_document_ids, rag_config, ...)
             |
             +--> 绑定 allowed_document_ids 到 RAG/ES 工具
             +--> 产出 ModeConfig（含完整工具列表）
             |
             v
         AgentLoop 执行
```

### 2.3 与当前实现的对比

| 维度 | 当前实现 | 重构后 |
|------|---------|--------|
| 工具构建入口 | ChatMode/AskMode 各自构建 | ToolRegistry 统一入口 |
| 模式过滤 | 各 Mode 类硬编码 | BuiltinToolProvider 按 mode 映射表分发 |
| MCP 工具 | 不存在 | ToolRegistry 合并内置 + MCP |
| 请求级参数 | build_tool_registry(allowed_doc_ids=...) | ModeConfigFactory 后续绑定 |
| 依赖获取 | 函数参数 + os.getenv | 构造时注入 index + 构造时检测 env |

## 3. ToolRegistry

### 3.1 职责

1. 持有 BuiltinToolProvider 和 MCPClientManager 两个具体组件（直接组合，不抽象公共接口）。
2. 根据 mode 和 mcp_enabled 参数，合并两个来源的工具列表。
3. 工具名称冲突防御性校验（MCP 工具已有 `server__tool` 前缀）。

### 3.2 非职责

- 不管理工具实现逻辑。
- 不管理 MCP 连接生命周期（MCPClientManager 的事）。
- 不关心 allowed_document_ids、RAGConfig 等请求级参数。
- 不参与工具执行和结果处理。
- 不关心 Source 提取。

### 3.3 接口

```python
class ToolRegistry:
    def __init__(
        self,
        builtin_provider: BuiltinToolProvider,
        mcp_provider: MCPClientManager,
    ) -> None:
        self._builtin = builtin_provider
        self._mcp = mcp_provider

    async def get_tools(
        self,
        mode: ModeType,
        mcp_enabled: bool = False,
    ) -> List[BaseTool]:
        """返回该模式下可用的工具列表。

        每次调用新建工具实例，不缓存。
        MCP 工具仅在 Agent 模式且 mcp_enabled=True 时注入。
        """
        tools = self._builtin.get_tools(mode)
        if mode == ModeType.AGENT and mcp_enabled:
            mcp_tools = await self._mcp.get_tools()
            tools.extend(mcp_tools)
        return tools
```

### 3.4 生命周期

应用级单例。构造时注入 BuiltinToolProvider 和 MCPClientManager。`get_tools()` 每次调用新建工具实例（工具实例是轻量的 index 引用封装），不存在跨请求状态。

## 4. BuiltinToolProvider

### 4.1 职责

管理内置工具的注册与按模式分发。重构自当前的 `build_tool_registry()` 函数。

### 4.2 模式-工具映射表

| 工具 | Agent | Ask | Explain | Conclude |
|------|-------|-----|---------|----------|
| knowledge_base (RAG + ES) | Y | Y | Y | Y |
| tavily_search | Y | Y | N | N |
| zhipu_search | Y | Y | N | N |
| time | Y | Y | N | N |

knowledge_base 是四种模式共有的检索基础设施（内部封装 pgvector 语义检索 + ES 关键词检索）。Tavily、Zhipu、time 是 Agent/Ask 的扩展能力。

Tavily 和 Zhipu Web 搜索工具同时注册（环境变量都存在时），使用优先级通过 system prompt 控制。

### 4.3 环境变量检测

| 工具 | 可用条件 | 环境变量 |
|------|---------|---------|
| knowledge_base | pgvector_index 不为 None | 始终可用（核心能力） |
| knowledge_base (keyword 模式) | es_index 不为 None | ELASTICSEARCH_URL |
| tavily_search | Tavily API Key 存在 | TAVILY_API_KEY |
| zhipu_search | Zhipu API Key 存在 | ZHIPU_API_KEY |
| time | 无条件 | 无 |

knowledge_base 在 ES 不可用时仍然可用（退化为仅支持 semantic 模式）。

### 4.4 接口

```python
class BuiltinToolProvider:
    def __init__(
        self,
        pg_index: Optional[VectorStoreIndex],
        es_index: Optional[ElasticsearchStore],
    ) -> None:
        self._pg_index = pg_index
        self._es_index = es_index
        self._tavily_available = bool(os.getenv("TAVILY_API_KEY"))
        self._zhipu_available = bool(os.getenv("ZHIPU_API_KEY"))

    def get_tools(self, mode: ModeType) -> List[BaseTool]:
        """根据模式返回可用的内置工具列表。每次调用新建实例。"""
        tools = []

        # RAG + ES：所有模式
        if self._pg_index:
            tools.append(self._build_knowledge_base_tool())
        if self._es_index:
            tools.append(self._build_es_tool())

        # Agent/Ask 模式额外工具
        if mode in (ModeType.AGENT, ModeType.ASK):
            if self._tavily_available:
                tools.append(self._build_tavily_tool())
            if self._zhipu_available:
                tools.append(self._build_zhipu_tool())
            tools.append(self._build_time_tool())

        return tools
```

### 4.5 与当前 build_tool_registry() 的差异

| 维度 | 当前 build_tool_registry() | 重构后 BuiltinToolProvider |
|------|---------------------------|---------------------------|
| 形式 | 独立函数 | 类，构造时注入依赖 |
| 模式感知 | 不区分模式，返回全部 | 按 mode 参数过滤 |
| allowed_doc_ids | 参数传入，绑定到工具 | 不处理，ModeConfigFactory 后续绑定 |
| ES 工具 | 独立的 es_search_tool | 统一为 knowledge_base |
| 依赖获取 | os.getenv 运行时检测 | 构造时检测并缓存 |

## 5. DI 集成

```python
# api/dependencies.py

_tool_registry: Optional[ToolRegistry] = None

async def get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        pg_index = await get_pg_index_singleton()
        es_index = await get_es_index_singleton()
        mcp_manager = await get_mcp_client_manager()
        builtin = BuiltinToolProvider(pg_index, es_index)
        _tool_registry = ToolRegistry(builtin, mcp_manager)
    return _tool_registry

async def get_chat_service(
    ...,
    tool_registry: ToolRegistry = Depends(get_tool_registry),
) -> ChatService:
    return ChatService(..., tool_registry=tool_registry)
```

ToolRegistry 单例持有 BuiltinToolProvider（含 index 引用）和 MCPClientManager（含连接池）。

## 6. 变更影响

| 文件 | 变更内容 |
|------|---------|
| core/tools/registry.py | 新增 ToolRegistry |
| core/tools/builtin_provider.py | 新增，重构自 build_tool_registry() |
| core/tools/knowledge_base.py | 新增，替代 es_search_tool，封装 HybridRetriever |
| core/tools/tool_registry.py | 废弃，由 registry.py + builtin_provider.py 替代 |
| core/tools/es_search_tool.py | 保留源文件，不再注册为工具 |
| core/tools/tavily_tools.py | 保持 |
| core/tools/zhipu_tools.py | 保持 |
| core/tools/time.py | 保持 |
| core/engine/mode_config.py | build() 接收外部 tools 参数，不再内部构建工具 |
| application/services/chat_service.py | 注入 ToolRegistry，调用 get_tools() |
| api/dependencies.py | 新增 get_tool_registry() 单例 |

## 7. 设计决策汇总

| 决策 | 结论 | 依据 |
|------|------|------|
| 生命周期 | 应用级单例 | 与 pgvector/ES index 单例模式一致 |
| 内置工具注册 | 环境变量驱动 | 工具可用性由基础设施决定，非用户偏好 |
| Source 提取 | 不关心 | 单一职责，Source 在工具实现层处理 |
| Provider 接口 | 不抽象，直接组合 | 只有两个来源，调用语义不同，避免过度抽象 |
| document_ids | 不在 ToolRegistry | 请求级参数，ModeConfigFactory 绑定 |
| 模块位置 | core/tools/ 下 | 语义自然，不需独立模块 |
| 工具实例 | 每次 get_tools() 新建 | 无状态，避免跨请求状态污染 |
| 依赖注入 | 构造时注入 | 标准 DI 模式，避免时序依赖 |
| Web 搜索 | Tavily + Zhipu 同时注册 | 提示词控制优先级 |
| ES 搜索 | 统一为 knowledge_base | search_type 参数已覆盖独立 ES 搜索能力 |
