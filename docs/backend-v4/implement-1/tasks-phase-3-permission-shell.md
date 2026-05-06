# Backend V4 Permission Gateway And Shell Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Phase 2 的 policy `ASK` 决策接入统一 `core/permission` 决策门，并为下一批 `core/shell`、`bash`、`read/grep/glob/edit/write` 工具实现锁定模块边界。

**Architecture:** `policy` 继续保持纯决策；`permission` 负责确认、allow 记忆、拒绝与审计；`core/tools` 承载 Agent 可见工具；`core/shell` 提供执行环境并委托 `core/sandbox`。本批实现 `permission` 的全局网关，不实现真实 bash 与文件读写工具。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic/dataclass、SQLAlchemy `app_settings`、pytest、现有 `AgentLoop`、`SessionManager`、`ConfirmationGateway`、`PolicyDecider`、`ToolRegistry`。

---

## 文档与测试约定

- 本文档使用 UTF-8 编码。
- 模块设计文档遵循 `docs-plan/README.md` 指定的顺序。
- 测试设计遵循 `docs-plan/test-guide.md`。
- 测试代码组织遵循 `docs-test/README.md`、`docs-test/classification.md`、`docs-test/directory-convention.md`、`docs-test/writing-guide.md`、`docs-test/ci-strategy.md`。
- 本批提交只包含计划文档与后续实现入口说明；代码实现从本文档的 Task P301 开始单独推进。

## Scope Notes

- `core/permission` 是 Phase 2 policy `ASK` 之后的唯一运行期决策门，覆盖全局工具、内置 skill、用户 config skill、未来 scripts 与文件系统工具。
- `permission` 不负责判断工具风险；风险由 `policy` 输出，`permission` 只消费 `Decision.capability_signature`、`risk_level`、`tool_name`、`tool_args`、`skill_context`。
- `permission` 不直接执行工具，也不直接修改 `ToolDefinition`。
- `core/shell` 在本批只定义边界：它提供 cwd、workspace roots、run_dir、env、timeout、输出限制与 sandbox 适配。
- `read/grep/glob/edit/write` 放在 `newbee_notebook/core/tools/` 下；建议使用 `core/tools/filesystem/` 子包，以避免把多个工具堆进单个大文件。
- `bash` 作为 Agent 可见工具也放在 `core/tools`，但实际执行必须经过 `core/shell -> core/sandbox`。
- 本批不把本地参考仓库 `deepagents/`、`kimi-cli/` 纳入提交范围，它们仅作为设计参考。

## Target File Layout

### Permission Gateway

- Create: `newbee_notebook/core/permission/__init__.py`
- Create: `newbee_notebook/core/permission/contracts.py`
- Create: `newbee_notebook/core/permission/session_cache.py`
- Create: `newbee_notebook/core/permission/allow_store.py`
- Create: `newbee_notebook/core/permission/dispatcher.py`
- Create: `newbee_notebook/core/permission/recorder.py`
- Create: `newbee_notebook/core/permission/gateway.py`
- Modify: `newbee_notebook/core/engine/confirmation.py`
- Modify: `newbee_notebook/core/engine/agent_loop.py`
- Modify: `newbee_notebook/core/session/session_manager.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Modify: `newbee_notebook/api/models/confirm_models.py`
- Modify: `newbee_notebook/api/routers/chat.py`
- Modify: `newbee_notebook/application/services/chat_service.py`

### Tests

- Create: `newbee_notebook/tests/unit/core/permission/__init__.py`
- Create: `newbee_notebook/tests/unit/core/permission/test_session_cache.py`
- Create: `newbee_notebook/tests/unit/core/permission/test_allow_store.py`
- Create: `newbee_notebook/tests/unit/core/permission/test_gateway.py`
- Create: `newbee_notebook/tests/unit/core/engine/test_permission_gate.py`
- Modify: `newbee_notebook/tests/unit/core/engine/test_agent_loop_policy_gate.py`
- Modify: `newbee_notebook/tests/unit/core/session/test_session_manager.py`
- Create: `newbee_notebook/tests/contract/api/test_chat_confirm.py`

### Shell And Filesystem Tool Planning

- Create: `docs/backend-v4/filesys-tools/goals-duty.md`
- Create: `docs/backend-v4/filesys-tools/architecture.md`
- Create: `docs/backend-v4/filesys-tools/dfd-interface.md`
- Create: `docs/backend-v4/filesys-tools/non-functional.md`
- Create: `docs/backend-v4/filesys-tools/test.md`

## Phase 3 Task List

- [X] P301 Extend `ConfirmationGateway` with rich responses while preserving `approved: bool` compatibility.
- [X] P302 Add permission contracts for request, response, allow scope, decision source, and rejection suggestion.
- [X] P303 Implement `SessionAllowCache` with session-scoped signature lookup and skill-scoped cleanup.
- [X] P304 Implement `AllowStore` as the only reader/writer for `permissions.*` app_settings keys.
- [X] P305 Implement `ConfirmationDispatcher` to translate permission requests into confirmation events and response choices.
- [X] P306 Implement `PermissionGateway` orchestration: session allow, permanent allow, ask, record, fail-closed.
- [X] P307 Wire `PermissionGateway` into `AgentLoop` for all policy `ASK` paths, including final-synthesis textual tool calls.
- [X] P308 Wire request-scoped `PermissionGateway` through FastAPI dependencies and `SessionManager`.
- [X] P309 Extend chat confirm API to accept either legacy `approved: bool` or explicit `response: once | always_session | always_persist | reject`.
- [X] P310 Add `clear_skill_permissions(name)` integration point for skill uninstall and session cache cleanup.
- [X] P311 Add focused unit and contract tests according to `docs-test/` rules.
- [X] P312 Run targeted verification, update this task file with discovered scope corrections, then commit Phase 3 implementation.

## Phase 3 Implementation Notes

- Implemented permission as the global gate for policy `ASK` decisions while retaining the legacy `confirmation_required` path for built-in skill compatibility.
- `ConfirmationGateway` now supports `wait_response()` and `resolve_response()`; existing `wait()` and `resolve(approved: bool)` remain compatible.
- `AllowStore` uses exact key lookup for capability signatures and scans `permissions.` keys only for skill uninstall cleanup because `AppSettingsService` currently exposes prefix deletion, not SQL LIKE pattern deletion.
- The current batch intentionally does not implement `core/shell`, `bash`, or filesystem tools; their module boundary is documented under `docs/backend-v4/filesys-tools/`.

## Acceptance Criteria

- `PolicyDecider` remains synchronous and IO-free.
- Every `PolicyVerdict.ASK` decision reaches `PermissionGateway` before a tool can execute.
- Legacy built-in skill confirmation behavior remains compatible while being replaceable by permission choices.
- `once` allows only the current request; it does not write session or permanent allow.
- `always_session` stores allow in process memory keyed by session id and capability signature.
- `always_persist` writes an allow record through `AllowStore` using a content-hash-bound signature.
- A rejected or timed-out confirmation never executes the tool.
- A DB read error in `AllowStore` is treated as a miss and enters ASK.
- A DB write error for `always_persist` fails closed and does not execute the tool.
- `clear_skill_permissions(name)` removes all `skill:<name>@...` permanent allows and clears matching session allows.
- Confirmation SSE events include `capability_signature`, `risk_level`, `skill_name`, `content_hash`, and response options.
- Existing boolean confirm requests still resolve pending confirmations.

## Verification Commands

Use the project virtual environment explicitly:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/permission/ -q
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/engine/ newbee_notebook/tests/unit/core/session/ -q
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/contract/api/ -q
```

Minimum pre-commit gate for Phase 3 implementation:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/permission/ newbee_notebook/tests/unit/core/policy/ newbee_notebook/tests/unit/core/engine/ newbee_notebook/tests/unit/core/session/ newbee_notebook/tests/unit/application/services/test_chat_runtime_routing.py newbee_notebook/tests/unit/application/services/test_chat_service_guards.py -q
```

## Stop Conditions

- Stop if permission needs to classify risk by itself; that belongs to `policy`.
- Stop if permission would execute tools or mutate tool arguments.
- Stop if a missing confirmation gateway would default to allow.
- Stop if permanent allow is not bound to `skill_name + content_hash` for skill-scoped tools.
- Stop if the shell/filesystem tool design requires executing host shell commands before sandbox is available.
- Stop if `deepagents/` or `kimi-cli/` files appear in `git status` as staged changes.

## Next Batch Handoff

After Phase 3 passes, start the shell/filesystem batch from `docs/backend-v4/filesys-tools/`. The next executable batch should implement `core/shell` environment contracts first, then add `core/tools/filesystem` read-only tools, then write/edit tools, and finally `bash` through `core/sandbox`.
