# ToolRegistry 与 BuiltinToolProvider 设计

## 1. 目标

ToolRegistry 是 runtime 获取工具列表的唯一入口。

它解决三个问题：

1. 模式和工具集合的映射统一
2. 内置工具和 MCP 工具统一暴露
3. 不再让各 mode 自己拼工具列表

## 2. 组件关系

```text
ToolRegistry
  -> BuiltinToolProvider
  -> MCPClientManager
```

其中：

- `BuiltinToolProvider` 负责内置工具
- `MCPClientManager` 负责外部 MCP 工具
- `ToolRegistry` 负责统一组装和模式过滤

## 3. 返回类型

`ToolRegistry` 返回值统一为：

- `list[ToolDefinition]`

不再使用 LlamaIndex `BaseTool` 作为 runtime 主协议。

## 4. 模式-工具映射

| 工具 | `agent` | `ask` | `explain` | `conclude` |
|------|---------|-------|-----------|------------|
| `knowledge_base` | Y | Y | Y | Y |
| `time` | Y | Y | N | N |
| Web 搜索 | 可选 | N | N | N |
| MCP 工具 | 后段支持 | N | N | N |

说明：

- `ask` 在 batch-2 固定为 `knowledge_base + time`
- `explain / conclude` 固定为 `knowledge_base only`
- Web 搜索和 MCP 只属于 `agent`

## 5. `BuiltinToolProvider`

`BuiltinToolProvider` 的职责：

- 管理内置工具注册
- 按 mode 返回可用工具
- 读取环境能力，但不决定请求级 scope

非职责：

- 不处理 `selected_text`
- 不处理 request-scoped RAG 参数绑定
- 不处理 session 状态

## 6. 请求级参数绑定

ToolRegistry 返回的是“基础工具定义”。

请求级参数绑定在 ModeConfig / runtime 侧完成，例如：

- `allowed_document_ids`
- `current_document_id`
- `rag_config`

这能避免 ToolRegistry 变成会话状态容器。

## 7. MCP 接入边界

MCP 工具只在 batch-2 后段接入，并且：

- 仅开放给 `agent`
- 通过 adapter 转成同样的 `ToolDefinition`

ToolRegistry 不需要知道工具来自哪里，只需要保证名称唯一和接口统一。
