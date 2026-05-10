# Shell And Permission Alignment Investigation

本文档汇总 2026-05-10 对后端 shell/bash 与 permission/confirmation 语义的代码调查。实施前先阅读同目录的 [implementation-plan.md](implementation-plan.md)，确认后再分批修改。

## 实施状态

本轮实施后，Agent 可见工具已经统一到 `shell` 与 `shell_task_*`，权限等待事件和解析入口已经统一到 `permission_request` 与 `/permission-requests/resolve`。旧 `confirmation_request`、`/confirm`、`confirmation_required`、`confirmation_meta` 保留为兼容入口；旧 `bash` Agent 工具调用会在运行时归一化为 `shell`。用户确认可删除的 legacy 工具文件 `newbee_notebook/core/tools/bash.py`、`newbee_notebook/core/tools/bash_tasks.py` 与 `newbee_notebook/core/engine/confirmation.py` 已删除，低层 sandbox 仍保留 `bash -lc` 作为容器内执行机制。

## 结论

后端目前是两套语义交叠：

- 执行环境已经叫 `core/shell`、`ShellExecutor`、`ShellEnvironment`，但 Agent 可见工具仍叫 `bash`，背景任务也叫 `bash_task_*`。
- 权限系统核心已经叫 `core/permission`、`PermissionGateway`、`PermissionRequest`，但等待用户响应的低层 primitive、SSE 事件、HTTP endpoint、skill manifest 字段仍叫 confirmation。

建议采用渐进兼容策略：

1. 后端 canonical 名称改为 `shell` 与 `permission_request`。
2. 低层实现仍允许容器内使用 `bash -lc`，这是执行机制，不是产品语义。
3. 旧 `bash` 工具调用、`confirmation_request` SSE、`/confirm` endpoint 先保留兼容入口，内部立即归一化到新语义。
4. 前端在后端切换前先接受 `permission_request`，之后再移除 `confirmation_request` 兼容。

## Shell 现状

### 活跃代码

| 位置 | 当前语义 | 调查结论 |
|---|---|---|
| `newbee_notebook/core/tools/bash.py` | `build_bash_tool()`，`ToolDefinition.name="bash"` | Agent 可见工具名，是 shell 语义统一的主入口。 |
| `newbee_notebook/core/tools/bash_tasks.py` | `bash_task_list/output/stop` | Agent 可见后台任务工具名，需要同步改为 `shell_task_*`。 |
| `newbee_notebook/core/shell/executor.py` | `ShellExecutor.execute_bash()` 内部构造 `("bash", "-lc", command)` | 方法名应改为 `execute_shell()`；argv 保留 `bash -lc` 作为实现细节。 |
| `newbee_notebook/core/shell/background_tasks.py` | `BackgroundBashTaskManager/Record/Output` | 类名和错误文案应改为 Shell。 |
| `newbee_notebook/core/policy/contracts.py` | `ToolClass.BASH = "bash"` | 策略分类应改为 `ToolClass.SHELL = "shell"`，并兼容旧 `"bash"` 输入。 |
| `newbee_notebook/core/policy/decider.py` | `ToolClass.BASH` 与 “dangerous bash tools” | 决策文案和判断应改为 shell。危险命令 matcher 里的管道到 `bash` 是命令内容，保留。 |
| `newbee_notebook/core/policy/signature.py` | signature 使用 raw `tool_name` | 切换后新 allow key 会是 `global:shell:<hash>`；旧 `global:bash:<hash>` 建议不迁移，按 fail-closed 重新授权。 |
| `newbee_notebook/core/tools/builtin_provider.py` | 注入 bash 工具和 bash task 工具 | 需改为 shell 工具，保留 Python 旧函数 alias。 |

### 测试影响面

- `newbee_notebook/tests/unit/core/tools/test_bash_tool.py`
- `newbee_notebook/tests/integration/core/tools/test_bash_tool_docker.py`
- `newbee_notebook/tests/unit/core/tools/test_filesystem_tool_contracts.py`
- `newbee_notebook/tests/unit/core/tools/test_tool_registry.py`
- `newbee_notebook/tests/unit/core/policy/test_policy_decider.py`
- `newbee_notebook/tests/unit/core/shell/test_executor.py`
- `newbee_notebook/tests/unit/core/shell/test_background_tasks.py`
- `newbee_notebook/tests/unit/core/engine/test_stream_events.py`
- sandbox 测试里 `argv=("bash", "-lc", "echo ok")` 这类断言是容器内真实命令，不属于用户可见语义，默认保留。

## Permission 现状

### 活跃代码

| 位置 | 当前语义 | 调查结论 |
|---|---|---|
| `newbee_notebook/core/permission/contracts.py` | `PermissionChoice`、`PermissionRequest`、`PermissionResponse` | 核心命名已经正确。 |
| `newbee_notebook/core/permission/gateway.py` | `PermissionGateway.create_confirmation()` | 对外方法应改为 `create_request()` 或通过新 request gateway 承担。 |
| `newbee_notebook/core/permission/dispatcher.py` | `ConfirmationDispatcher` | 应改为 `PermissionRequestDispatcher` 或删除 dispatcher 名称，内部依赖新 gateway。 |
| `newbee_notebook/core/engine/confirmation.py` | `ConfirmationGateway`、`PendingConfirmation` | 已迁到 `core/permission/request_gateway.py`，旧文件删除。 |
| `newbee_notebook/core/engine/stream_events.py` | `ConfirmationRequestEvent(event="confirmation_request")` | 已改为 `PermissionRequestEvent(event="permission_request")`。 |
| `newbee_notebook/core/engine/agent_loop.py` | 大量 `confirmation_*` 内部字段和 `_create_confirmation_event()` | 应改为 permission request 语义；旧 `confirmation_required` skill path 作为 legacy alias。 |
| `newbee_notebook/api/models/confirm_models.py` | `ConfirmActionRequest` | 应新增 `PermissionResolveRequest`，旧 model 兼容。 |
| `newbee_notebook/api/routers/chat.py` | `POST /chat/{session_id}/confirm` | 应新增 `POST /chat/{session_id}/permission-requests/resolve`，旧 `/confirm` 兼容。 |
| `newbee_notebook/application/services/chat_service.py` | `confirm_action()`，SSE type `confirmation_request` | 应新增 `resolve_permission_request()` 并发出 `permission_request`。 |
| skill providers | `confirmation_required`、`confirmation_meta`、`ConfirmationMeta` | 这表示“需要权限审批”的 manifest 字段，应迁到 `permission_required`、`permission_meta`、`PermissionMeta`，保留旧字段兼容。 |

### 不应误改的名称

- `confirm_diagram_type` 是业务工具，含义是“确认图表类型”，不是权限语义，保留。
- `confirmation` 出现在旧版历史 docs 中可不作为本批代码阻塞项。
- `bash` 出现在低层 `SandboxRequest(argv=("bash", "-lc", "echo ok"))` 是容器内 shell 实现，保留。

## 文件清单

### 后端 shell 待改

- Create: `newbee_notebook/core/tools/shell.py`
- Create: `newbee_notebook/core/tools/shell_tasks.py`
- Delete: `newbee_notebook/core/tools/bash.py`
- Delete: `newbee_notebook/core/tools/bash_tasks.py`
- Modify: `newbee_notebook/core/tools/__init__.py`
- Modify: `newbee_notebook/core/tools/builtin_provider.py`
- Modify: `newbee_notebook/core/shell/__init__.py`
- Modify: `newbee_notebook/core/shell/executor.py`
- Modify: `newbee_notebook/core/shell/background_tasks.py`
- Modify: `newbee_notebook/core/policy/contracts.py`
- Modify: `newbee_notebook/core/policy/decider.py`
- Modify: `newbee_notebook/core/engine/agent_loop.py`
- Modify: shell and policy tests listed above.

### 后端 permission 待改

- Create: `newbee_notebook/core/permission/request_gateway.py`
- Delete: `newbee_notebook/core/engine/confirmation.py`
- Modify: `newbee_notebook/core/engine/stream_events.py`
- Modify: `newbee_notebook/core/engine/agent_loop.py`
- Modify: `newbee_notebook/core/permission/__init__.py`
- Modify: `newbee_notebook/core/permission/gateway.py`
- Modify: `newbee_notebook/core/permission/dispatcher.py`
- Modify: `newbee_notebook/core/session/session_manager.py`
- Modify: `newbee_notebook/application/services/chat_service.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Modify: `newbee_notebook/api/models/confirm_models.py`
- Modify: `newbee_notebook/api/routers/chat.py`
- Modify: `newbee_notebook/core/skills/contracts.py`
- Modify: `newbee_notebook/skills/note/provider.py`
- Modify: `newbee_notebook/skills/diagram/provider.py`
- Modify: `newbee_notebook/skills/video/provider.py`
- Modify: permission, engine, API, skill tests listed in the implementation plan.

### 前端边界待改

后端切换 SSE type 前，前端需要先兼容新事件：

- Modify: `frontend/src/lib/api/types.ts`
- Modify: `frontend/src/lib/hooks/useChatSession.ts`
- Modify: `frontend/src/lib/api/chat.ts`
- Modify: `frontend/src/lib/hooks/useChatSession.test.tsx`

## 风险点

- 直接把工具名从 `bash` 改为 `shell` 会让旧 LLM textual tool call 失败。需要在 `AgentLoop` 做 `bash -> shell` alias 归一化。
- 直接把 SSE 从 `confirmation_request` 改为 `permission_request` 会打断当前前端。需要前端先接受双事件。
- `always_persist` 旧 allow key 使用 `global:bash:<hash>`。建议不迁移到 `global:shell:<hash>`，因为权限语义变更时 fail-closed 更安全。
- skill manifest 字段改名必须保留旧字段读取，否则已安装用户 skills 会失效。

## 推荐分批

1. 前端协议兼容：接受 `permission_request`，仍接受 `confirmation_request`。
2. 后端 shell canonical：新增 shell 工具，保留 bash shim 和 alias。
3. 后端 permission API/SSE canonical：新增 permission request gateway、event、endpoint，保留 confirmation shim。
4. skill manifest 字段迁移：新增 permission meta 字段，旧 confirmation 字段兼容。
5. 清理测试和 docs：只保留低层 `bash -lc` 和业务 `confirm_diagram_type`。
