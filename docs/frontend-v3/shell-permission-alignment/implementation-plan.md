# Shell And Permission Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify backend product semantics around `shell` and permission requests while preserving compatibility for legacy `bash`, `confirmation_request`, and `/confirm` callers during the migration.

**Architecture:** Introduce canonical backend names first, then route legacy names through thin adapters. The runtime should expose `shell` and `permission_request` to clients, while low-level container execution may continue to use `bash -lc` internally. Permission remains the global gate after policy `ASK`; confirmation becomes a deprecated compatibility layer only.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, dataclasses, pytest, current `AgentLoop`, `SessionManager`, `ToolRegistry`, `PermissionGateway`, Next.js frontend API adapters.

**Implementation update:** After user confirmation, `newbee_notebook/core/tools/bash.py`, `newbee_notebook/core/tools/bash_tasks.py`, and `newbee_notebook/core/engine/confirmation.py` were deleted instead of retained as Python shims. Legacy `bash` model tool calls remain supported through AgentLoop and policy normalization, while the registry only exposes canonical `shell` tools.

---

## Semantic Decisions

- Canonical Agent tool name: `shell`.
- Legacy Agent tool alias: `bash`, accepted only as input compatibility.
- Canonical background task tools: `shell_task_list`, `shell_task_output`, `shell_task_stop`.
- Container argv: keep `("bash", "-lc", command)` in sandbox requests.
- Canonical SSE event type: `permission_request`.
- Legacy SSE event type: `confirmation_request`, accepted by frontend during migration.
- Canonical resolve endpoint: `POST /api/v1/chat/{session_id}/permission-requests/resolve`.
- Legacy resolve endpoint: `POST /api/v1/chat/{session_id}/confirm`.
- Canonical skill manifest fields: `permission_required`, `permission_meta`.
- Legacy skill manifest fields: `confirmation_required`, `confirmation_meta`.
- Business tool `confirm_diagram_type` remains unchanged.
- Existing persistent allows keyed with `global:bash:<hash>` are not migrated; they naturally miss and require fresh approval.

## Target File Layout

### Shell

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

### Permission

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

### Frontend Boundary

- Modify: `frontend/src/lib/api/types.ts`
- Modify: `frontend/src/lib/hooks/useChatSession.ts`
- Modify: `frontend/src/lib/api/chat.ts`
- Modify: `frontend/src/lib/hooks/useChatSession.test.tsx`

---

## Task 1: Frontend Accepts New Permission SSE Type

**Files:**
- Modify: `frontend/src/lib/api/types.ts`
- Modify: `frontend/src/lib/hooks/useChatSession.ts`
- Modify: `frontend/src/lib/hooks/useChatSession.test.tsx`

- [ ] **Step 1: Write the failing frontend hook test**

Add a test beside the existing `confirmation_request` coverage:

```tsx
it("stores pending permission request when the stream emits a permission request", async () => {
  streamController.enqueue({
    type: "permission_request",
    request_id: "req-1",
    tool_name: "shell",
    action_type: "confirm",
    target_type: "unknown",
    args_summary: { command: "echo ok" },
    description: "AI requested to run shell",
    response_options: ["once", "always_session", "always_persist", "reject"],
  });

  await act(async () => {
    await result.current.sendMessage("Run command", "agent");
  });

  const assistantMessage = useChatStore
    .getState()
    .messagesBySession["session-1"]
    ?.find((message) => message.role === "assistant");

  expect(assistantMessage?.pendingPermissionRequest?.requestId).toBe("req-1");
  expect(assistantMessage?.pendingPermissionRequest?.toolName).toBe("shell");
});
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
cd frontend
pnpm vitest run src/lib/hooks/useChatSession.test.tsx
```

Expected: FAIL because `permission_request` is not yet part of the SSE union or hook branch.

- [ ] **Step 3: Add frontend compatibility**

Update `frontend/src/lib/api/types.ts`:

```ts
export type SseEventPermissionRequest = Omit<SseEventConfirmation, "type"> & {
  type: "permission_request";
};

export type SseEvent =
  | SseEventStart
  | SseEventPhase
  | SseEventContent
  | SseEventIntermediateContent
  | SseEventThinking
  | SseEventSources
  | SseEventDone
  | SseEventError
  | SseEventHeartbeat
  | SseEventConfirmation
  | SseEventPermissionRequest
  | SseEventToolCall
  | SseEventToolResult
  | SseEventImageGenerated;
```

Update `frontend/src/lib/hooks/useChatSession.ts`:

```ts
if (event.type === "confirmation_request" || event.type === "permission_request") {
  trackPermissionRequestFromConfirmationEvent(sessionId, activeAssistantIdRef.current, event);
  continue;
}
```

- [ ] **Step 4: Verify**

Run:

```powershell
cd frontend
pnpm vitest run src/lib/hooks/useChatSession.test.tsx src/components/chat/permission-request-card.test.tsx
pnpm typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/lib/api/types.ts frontend/src/lib/hooks/useChatSession.ts frontend/src/lib/hooks/useChatSession.test.tsx
git commit -m "feat(frontend): accept permission request events"
```

## Task 2: Introduce Canonical Shell Tool With Bash Compatibility

**Files:**
- Create: `newbee_notebook/core/tools/shell.py`
- Modify: `newbee_notebook/core/tools/bash.py`
- Modify: `newbee_notebook/core/shell/executor.py`
- Modify: `newbee_notebook/core/shell/background_tasks.py`
- Modify: `newbee_notebook/core/shell/__init__.py`
- Modify: `newbee_notebook/core/tools/__init__.py`
- Test: `newbee_notebook/tests/unit/core/tools/test_shell_tool.py`
- Test: `newbee_notebook/tests/unit/core/shell/test_executor.py`

- [ ] **Step 1: Write the failing shell tool test**

Create `newbee_notebook/tests/unit/core/tools/test_shell_tool.py`:

```python
from __future__ import annotations

import pytest

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.shell import ShellEnvironment
from newbee_notebook.core.tools.shell import build_shell_tool

pytestmark = pytest.mark.unit


def test_shell_tool_exposes_shell_name_and_policy_metadata(tmp_path):
    tool = build_shell_tool(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))

    assert tool.name == "shell"
    assert tool.tool_class == ToolClass.SHELL
    assert tool.risk_level == RiskLevel.DANGEROUS
    assert tool.sandbox_required is True
    assert "shell command" in tool.description.lower()
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/tools/test_shell_tool.py -q
```

Expected: FAIL because `core.tools.shell` does not exist.

- [ ] **Step 3: Rename executor API with compatibility wrapper**

In `newbee_notebook/core/shell/executor.py`, add `execute_shell()` and make `execute_bash()` call it:

```python
async def execute_shell(
    self,
    command: str,
    *,
    timeout_seconds: float | None = None,
) -> ShellExecutionResult:
    # Move the current execute_bash body here unchanged.
    # Keep SandboxRequest argv as ("bash", "-lc", normalized_command).
    # The method name is product semantics; the argv is implementation detail.

async def execute_bash(
    self,
    command: str,
    *,
    timeout_seconds: float | None = None,
) -> ShellExecutionResult:
    return await self.execute_shell(command, timeout_seconds=timeout_seconds)
```

- [ ] **Step 4: Add shell tool and bash shim**

Create `newbee_notebook/core/tools/shell.py` with `build_shell_tool()` copied from the current bash tool, with these changes:

```python
shell_result = await executor.execute_shell(command, timeout_seconds=timeout_seconds)

return ToolDefinition(
    name="shell",
    description="Run a shell command inside the configured sandbox and return stdout, stderr, and exit code.",
    tool_class=ToolClass.SHELL,
    risk_level=RiskLevel.DANGEROUS,
    sandbox_required=True,
)
```

Change `newbee_notebook/core/tools/bash.py` to a compatibility shim:

```python
from newbee_notebook.core.tools.shell import build_shell_tool


def build_bash_tool(*args, **kwargs):
    return build_shell_tool(*args, **kwargs)
```

- [ ] **Step 5: Rename background shell classes with aliases**

In `newbee_notebook/core/shell/background_tasks.py`, rename canonical classes:

```python
@dataclass(frozen=True)
class BackgroundShellTaskRecord:
    task_id: str
    command: str
    description: str
    status: str
    log_path: Path
    created_at: float
    updated_at: float
    exit_code: int | None = None
    error_code: str | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class BackgroundShellTaskOutput:
    task_id: str
    status: str
    log_path: Path
    content: str
    truncated: bool = False


class BackgroundShellTaskManager:
    """Manage notebook-scoped background shell tasks."""

```

Update internal messages from “background bash task” to “background shell task”.

- [ ] **Step 6: Update exports**

Update `newbee_notebook/core/shell/__init__.py` and `newbee_notebook/core/tools/__init__.py` to export canonical shell names only.

- [ ] **Step 7: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/tools/test_shell_tool.py newbee_notebook/tests/unit/core/tools/test_bash_tool.py newbee_notebook/tests/unit/core/shell/test_executor.py newbee_notebook/tests/unit/core/shell/test_background_tasks.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add newbee_notebook/core/tools/shell.py newbee_notebook/core/tools/bash.py newbee_notebook/core/shell/executor.py newbee_notebook/core/shell/background_tasks.py newbee_notebook/core/shell/__init__.py newbee_notebook/core/tools/__init__.py newbee_notebook/tests/unit/core/tools/test_shell_tool.py newbee_notebook/tests/unit/core/tools/test_bash_tool.py newbee_notebook/tests/unit/core/shell/test_executor.py newbee_notebook/tests/unit/core/shell/test_background_tasks.py
git commit -m "feat(backend): introduce shell tool compatibility"
```

## Task 3: Switch Policy And Tool Registry To Shell

**Files:**
- Modify: `newbee_notebook/core/policy/contracts.py`
- Modify: `newbee_notebook/core/policy/decider.py`
- Modify: `newbee_notebook/core/tools/builtin_provider.py`
- Modify: `newbee_notebook/core/tools/shell_tasks.py`
- Modify: `newbee_notebook/core/tools/bash_tasks.py`
- Modify: `newbee_notebook/core/engine/agent_loop.py`
- Test: `newbee_notebook/tests/unit/core/policy/test_policy_decider.py`
- Test: `newbee_notebook/tests/unit/core/tools/test_tool_registry.py`
- Test: `newbee_notebook/tests/unit/core/tools/test_filesystem_tool_contracts.py`

- [ ] **Step 1: Write policy compatibility tests**

Extend `test_policy_decider.py`:

```python
def test_default_policy_upgrades_dangerous_shell_commands_to_ask():
    decider = PolicyDecider()

    decision = decider.decide(
        DecideRequest(
            session_id="s1",
            tool_name="shell",
            tool_args={"command": "rm -rf /tmp/demo"},
            tool_class=ToolClass.SHELL,
            risk_level=RiskLevel.SAFE,
        )
    )

    assert decision.verdict == PolicyVerdict.ASK
    assert decision.risk_level == RiskLevel.DANGEROUS
    assert "dangerous shell" in decision.reason


def test_policy_coerces_legacy_bash_tool_class_to_shell():
    decider = PolicyDecider()

    decision = decider.decide(
        DecideRequest(
            session_id="s1",
            tool_name="bash",
            tool_args={"command": "rm -rf /tmp/demo"},
            tool_class="bash",
            risk_level=RiskLevel.SAFE,
        )
    )

    assert decision.tool_class == ToolClass.SHELL
    assert decision.capability_signature.startswith("global:shell:")
```

- [ ] **Step 2: Run failing policy tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/policy/test_policy_decider.py -q
```

Expected: FAIL until `ToolClass.SHELL` and legacy coercion exist.

- [ ] **Step 3: Update policy contracts and signature input**

In `newbee_notebook/core/policy/contracts.py`:

```python
class ToolClass(StrEnum):
    READ = "read"
    WRITE = "write"
    EDIT = "edit"
    SHELL = "shell"
    MCP = "mcp"
    CUSTOM = "custom"
```

In `newbee_notebook/core/policy/decider.py`:

```python
def _coerce_tool_class(value: ToolClass | str) -> ToolClass:
    raw = str(value).strip().lower()
    if raw == "bash":
        return ToolClass.SHELL
    try:
        return ToolClass(raw)
    except ValueError:
        return ToolClass.CUSTOM

def _canonical_tool_name(tool_name: str) -> str:
    return "shell" if str(tool_name).strip().lower() == "bash" else str(tool_name)
```

Use `_canonical_tool_name(request.tool_name)` before `SignatureBuilder.build()`.

- [ ] **Step 4: Add agent loop tool alias**

In `newbee_notebook/core/engine/agent_loop.py`, add:

```python
LEGACY_TOOL_ALIASES = {"bash": "shell"}

def _canonical_tool_name(self, tool_name: str) -> str:
    normalized = str(tool_name or "").strip()
    return LEGACY_TOOL_ALIASES.get(normalized, normalized)
```

Call it before `_resolve_tool_arguments()` and `_tools[canonical_tool_name]` lookup in both tool-call loops. Emit canonical `tool_name` in `ToolCallEvent`, `ToolResultEvent`, and permission events.

- [ ] **Step 5: Switch registry tools**

Update `BuiltinToolProvider`:

```python
from newbee_notebook.core.tools.shell import build_shell_tool
from newbee_notebook.core.tools.shell_tasks import (
    build_shell_task_list_tool,
    build_shell_task_output_tool,
    build_shell_task_stop_tool,
)
```

Expected agent tool order:

```python
[
    "knowledge_base",
    "time",
    "read_file",
    "glob_files",
    "grep_files",
    "edit_file",
    "write_file",
    "shell",
    "shell_task_list",
    "shell_task_output",
    "shell_task_stop",
]
```

- [ ] **Step 6: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/policy/test_policy_decider.py newbee_notebook/tests/unit/core/tools/test_tool_registry.py newbee_notebook/tests/unit/core/tools/test_filesystem_tool_contracts.py newbee_notebook/tests/unit/core/engine/test_agent_loop_confirmation.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add newbee_notebook/core/policy/contracts.py newbee_notebook/core/policy/decider.py newbee_notebook/core/tools/builtin_provider.py newbee_notebook/core/tools/shell_tasks.py newbee_notebook/core/tools/bash_tasks.py newbee_notebook/core/engine/agent_loop.py newbee_notebook/tests/unit/core/policy/test_policy_decider.py newbee_notebook/tests/unit/core/tools/test_tool_registry.py newbee_notebook/tests/unit/core/tools/test_filesystem_tool_contracts.py
git commit -m "refactor(backend): make shell the canonical tool name"
```

## Task 4: Introduce Permission Request Gateway And Event

**Files:**
- Create: `newbee_notebook/core/permission/request_gateway.py`
- Delete: `newbee_notebook/core/engine/confirmation.py`
- Modify: `newbee_notebook/core/engine/stream_events.py`
- Modify: `newbee_notebook/core/permission/__init__.py`
- Modify: `newbee_notebook/core/permission/dispatcher.py`
- Modify: `newbee_notebook/core/permission/gateway.py`
- Test: `newbee_notebook/tests/unit/core/permission/test_gateway.py`
- Test: `newbee_notebook/tests/unit/core/engine/test_stream_events.py`

- [ ] **Step 1: Write request gateway tests**

Add to `test_gateway.py`:

```python
from newbee_notebook.core.permission import PermissionRequestGateway


@pytest.mark.anyio
async def test_permission_request_gateway_supports_rich_response_and_legacy_bool():
    gateway = PermissionRequestGateway()
    gateway.create("req-rich")
    assert gateway.resolve_response("req-rich", {"response": "always_session"})
    assert await gateway.wait_response("req-rich") == {"response": "always_session"}

    gateway.create("req-legacy")
    assert gateway.resolve("req-legacy", approved=True)
    assert await gateway.wait("req-legacy")
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/permission/test_gateway.py newbee_notebook/tests/unit/core/engine/test_stream_events.py -q
```

Expected: FAIL because `PermissionRequestGateway` and `PermissionRequestEvent` do not exist.

- [ ] **Step 3: Add canonical request gateway**

Create `newbee_notebook/core/permission/request_gateway.py`:

```python
@dataclass
class PendingPermissionRequest:
    event: asyncio.Event = field(default_factory=asyncio.Event)
    approved: bool = False
    response: Any = False


def _response_is_allowed(response: Any) -> bool:
    if isinstance(response, bool):
        return response
    if isinstance(response, str):
        return response in {"once", "always_session", "always_persist"}
    if isinstance(response, dict):
        value = response.get("approved")
        if isinstance(value, bool):
            return value
        choice = str(response.get("response") or response.get("choice") or "")
        return choice in {"once", "always_session", "always_persist"}
    return False


class PermissionRequestGateway:
    def create(self, request_id: str) -> None:
        self._pending[request_id] = PendingPermissionRequest()

    async def wait(self, request_id: str, timeout: float = 180.0) -> bool:
        response = await self.wait_response(request_id, timeout=timeout)
        return _response_is_allowed(response)

    async def wait_response(self, request_id: str, timeout: float = 180.0) -> Any:
        pending = self._pending.get(request_id)
        if pending is None:
            return False
        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout)
            return pending.response
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending.pop(request_id, None)

    def resolve(self, request_id: str, approved: bool) -> bool:
        return self.resolve_response(request_id, approved)

    def resolve_response(self, request_id: str, response: Any) -> bool:
        pending = self._pending.get(request_id)
        if pending is None:
            return False
        pending.approved = _response_is_allowed(response)
        pending.response = response
        pending.event.set()
        return True
```

Move the existing request-wait logic here with class and dataclass names changed to `PermissionRequestGateway` and `PendingPermissionRequest`.

- [ ] **Step 4: Delete confirmation shim after canonical imports are migrated**

Delete `newbee_notebook/core/engine/confirmation.py` after all runtime and test imports use `PermissionRequestGateway` from `newbee_notebook.core.permission`.

- [ ] **Step 5: Add canonical stream event**

In `newbee_notebook/core/engine/stream_events.py`:

```python
@dataclass(frozen=True)
class PermissionRequestEvent:
    request_id: str
    tool_name: str
    args_summary: dict
    description: str
    action_type: str = "confirm"
    target_type: str = "unknown"
    capability_signature: str = ""
    risk_level: str = ""
    skill_name: str | None = None
    content_hash: str = ""
    response_options: list[str] = field(default_factory=list)
    event: str = "permission_request"

```

- [ ] **Step 6: Rename dispatcher**

In `newbee_notebook/core/permission/dispatcher.py`, create `PermissionRequestDispatcher` as canonical.

- [ ] **Step 7: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/permission/test_gateway.py newbee_notebook/tests/unit/core/engine/test_stream_events.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add newbee_notebook/core/permission/request_gateway.py newbee_notebook/core/engine/confirmation.py newbee_notebook/core/engine/stream_events.py newbee_notebook/core/permission/__init__.py newbee_notebook/core/permission/dispatcher.py newbee_notebook/core/permission/gateway.py newbee_notebook/tests/unit/core/permission/test_gateway.py newbee_notebook/tests/unit/core/engine/test_stream_events.py
git commit -m "refactor(backend): add permission request gateway"
```

## Task 5: Rename AgentLoop Permission Internals

**Files:**
- Modify: `newbee_notebook/core/engine/agent_loop.py`
- Modify: `newbee_notebook/core/session/session_manager.py`
- Modify: `newbee_notebook/application/services/chat_service.py`
- Test: `newbee_notebook/tests/unit/core/engine/test_permission_gate.py`
- Test: `newbee_notebook/tests/unit/core/engine/test_agent_loop_confirmation.py`
- Test: `newbee_notebook/tests/unit/core/session/test_session_manager.py`

- [ ] **Step 1: Write canonical event test**

In `test_permission_gate.py`, assert permission request event naming:

```python
permission_events = [event for event in events if isinstance(event, PermissionRequestEvent)]
assert len(permission_events) == 1
assert permission_events[0].event == "permission_request"
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/engine/test_permission_gate.py -q
```

Expected: FAIL until AgentLoop yields `PermissionRequestEvent`.

- [ ] **Step 3: Rename AgentLoop internals**

In `AgentLoop`, rename:

```python
_confirmation_required -> _permission_required
_confirmation_meta -> _permission_meta
_confirmation_gateway -> _permission_request_gateway
_create_confirmation_event -> _create_permission_request_event
legacy_confirmation_required -> legacy_permission_required
confirmation_decision -> permission_decision
```

Keep constructor parameters `confirmation_required`, `confirmation_meta`, and `confirmation_gateway` as deprecated aliases, but normalize immediately into canonical fields.

- [ ] **Step 4: Update SessionManager and ChatService forwarding**

Add canonical parameters:

```python
permission_required: frozenset[str] | None = None
permission_meta: dict | None = None
permission_request_gateway: PermissionRequestGateway | None = None
```

Map legacy parameters only when canonical values are absent.

- [ ] **Step 5: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/engine/test_permission_gate.py newbee_notebook/tests/unit/core/engine/test_agent_loop_confirmation.py newbee_notebook/tests/unit/core/session/test_session_manager.py newbee_notebook/tests/unit/application/services/test_chat_service_guards.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add newbee_notebook/core/engine/agent_loop.py newbee_notebook/core/session/session_manager.py newbee_notebook/application/services/chat_service.py newbee_notebook/tests/unit/core/engine/test_permission_gate.py newbee_notebook/tests/unit/core/engine/test_agent_loop_confirmation.py newbee_notebook/tests/unit/core/session/test_session_manager.py newbee_notebook/tests/unit/application/services/test_chat_service_guards.py
git commit -m "refactor(backend): rename runtime approval internals to permission"
```

## Task 6: Add Permission Resolve API And Keep Confirm Compatibility

**Files:**
- Modify: `newbee_notebook/api/models/confirm_models.py`
- Modify: `newbee_notebook/api/routers/chat.py`
- Modify: `newbee_notebook/application/services/chat_service.py`
- Test: `newbee_notebook/tests/contract/api/test_chat_confirm.py`
- Test: `newbee_notebook/tests/contract/api/test_chat_router_sse.py`

- [ ] **Step 1: Write new endpoint contract tests**

Add to `test_chat_confirm.py`:

```python
def test_permission_resolve_endpoint_accepts_response_choice():
    chat_service = AsyncMock()
    chat_service.resolve_permission_request = AsyncMock(return_value=True)
    policy_service = _FakePolicyService()
    client = _build_client(chat_service, policy_service)

    response = client.post(
        "/api/v1/chat/session-1/permission-requests/resolve",
        json={"request_id": "req-1", "response": "always_session"},
    )

    assert response.status_code == 200
    chat_service.resolve_permission_request.assert_awaited_once_with(
        session_id="session-1",
        request_id="req-1",
        approved=None,
        response="always_session",
        suggestion=None,
    )
```

- [ ] **Step 2: Run failing contract test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/contract/api/test_chat_confirm.py -q
```

Expected: FAIL because the new endpoint does not exist.

- [ ] **Step 3: Add canonical API models**

In `confirm_models.py`, add:

```python
class PermissionResolveRequest(BaseModel):
    request_id: str
    approved: bool | None = None
    response: Literal["once", "always_session", "always_persist", "reject"] | None = None
    suggestion: str | None = None

    @model_validator(mode="after")
    def _validate_choice(self) -> "PermissionResolveRequest":
        if self.approved is None and self.response is None:
            raise ValueError("Either approved or response is required")
        if self.approved is not None and self.response is not None:
            raise ValueError("Use either approved or response, not both")
        return self


ConfirmActionRequest = PermissionResolveRequest
```

- [ ] **Step 4: Add canonical service method**

In `ChatService`:

```python
async def resolve_permission_request(
    self,
    session_id: str,
    request_id: str,
    approved: bool | None = None,
    response: str | None = None,
    suggestion: str | None = None,
) -> bool:
    session = await self._session_repo.get(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")
    if not self._permission_request_gateway:
        return False
    if response is not None:
        return bool(
            self._permission_request_gateway.resolve_response(
                request_id,
                {"response": response, "suggestion": suggestion},
            )
        )
    if approved is None:
        return False
    return bool(self._permission_request_gateway.resolve(request_id, approved))

async def confirm_action(
    self,
    session_id: str,
    request_id: str,
    approved: bool | None = None,
    response: str | None = None,
    suggestion: str | None = None,
) -> bool:
    return await self.resolve_permission_request(
        session_id=session_id,
        request_id=request_id,
        approved=approved,
        response=response,
        suggestion=suggestion,
    )
```

- [ ] **Step 5: Add canonical route and keep old route**

In `chat.py`, extract shared resolver helper and add:

```python
@router.post(
    "/{session_id}/permission-requests/resolve",
    response_model=ConfirmActionResponse,
    response_model_exclude_none=True,
)
async def resolve_permission_request(
    session_id: str,
    request: PermissionResolveRequest,
    chat_service: ChatService = Depends(get_chat_service),
    session_service: SessionService = Depends(get_session_service),
    policy_service: PolicyPreferenceService = Depends(get_policy_preference_service),
):
    return await _resolve_permission_request_response(
        session_id=session_id,
        request=request,
        chat_service=chat_service,
        session_service=session_service,
        policy_service=policy_service,
    )
```

The old `/{session_id}/confirm` route should call the same helper.

- [ ] **Step 6: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/contract/api/test_chat_confirm.py newbee_notebook/tests/contract/api/test_chat_router_sse.py newbee_notebook/tests/unit/application/services/test_chat_service_guards.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add newbee_notebook/api/models/confirm_models.py newbee_notebook/api/routers/chat.py newbee_notebook/application/services/chat_service.py newbee_notebook/tests/contract/api/test_chat_confirm.py newbee_notebook/tests/contract/api/test_chat_router_sse.py newbee_notebook/tests/unit/application/services/test_chat_service_guards.py
git commit -m "feat(backend): add permission resolve endpoint"
```

## Task 7: Migrate Skill Manifest Permission Fields

**Files:**
- Modify: `newbee_notebook/core/skills/contracts.py`
- Modify: `newbee_notebook/skills/note/provider.py`
- Modify: `newbee_notebook/skills/diagram/provider.py`
- Modify: `newbee_notebook/skills/video/provider.py`
- Test: `newbee_notebook/tests/unit/skills/note/test_note_tools.py`
- Test: `newbee_notebook/tests/unit/skills/diagram/test_tools.py`
- Test: `newbee_notebook/tests/unit/skills/video/test_tools.py`

- [ ] **Step 1: Write manifest tests for canonical fields**

Update provider tests to assert:

```python
assert manifest.permission_required == frozenset({"update_note", "delete_note"})
assert manifest.permission_meta["update_note"].action_type == "update"
```

Keep one test that constructs a manifest with legacy `confirmation_required` and verifies `permission_required` mirrors it.

- [ ] **Step 2: Run failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/skills/note/test_note_tools.py newbee_notebook/tests/unit/skills/diagram/test_tools.py newbee_notebook/tests/unit/skills/video/test_tools.py -q
```

Expected: FAIL until canonical fields exist.

- [ ] **Step 3: Add canonical dataclass fields**

In `core/skills/contracts.py`:

```python
@dataclass(frozen=True)
class PermissionMeta:
    action_type: str = "confirm"
    target_type: str = "unknown"


ConfirmationMeta = PermissionMeta
```

In `SkillManifest`, add canonical fields and mirror legacy values in `__post_init__`:

```python
permission_required: frozenset[str] = frozenset()
permission_meta: dict[str, PermissionMeta] = field(default_factory=dict)
confirmation_required: frozenset[str] = frozenset()
confirmation_meta: dict[str, PermissionMeta] = field(default_factory=dict)
```

- [ ] **Step 4: Update built-in providers**

Change note, diagram, and video providers to pass `permission_required` and `permission_meta`.

- [ ] **Step 5: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/skills/note/test_note_tools.py newbee_notebook/tests/unit/skills/diagram/test_tools.py newbee_notebook/tests/unit/skills/video/test_tools.py newbee_notebook/tests/unit/core/skills/test_contracts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add newbee_notebook/core/skills/contracts.py newbee_notebook/skills/note/provider.py newbee_notebook/skills/diagram/provider.py newbee_notebook/skills/video/provider.py newbee_notebook/tests/unit/skills/note/test_note_tools.py newbee_notebook/tests/unit/skills/diagram/test_tools.py newbee_notebook/tests/unit/skills/video/test_tools.py newbee_notebook/tests/unit/core/skills/test_contracts.py
git commit -m "refactor(backend): rename skill approval fields to permission"
```

## Task 8: Final Cleanup Scan And Docs

**Files:**
- Modify: `docs/backend-v4/permission/*.md`
- Modify: `docs/backend-v4/policy/*.md`
- Modify: `docs/backend-v4/filesys-tools/*.md`
- Modify: `docs/frontend-v3/policy-permission/*.md`
- Modify: tests with stale names discovered by the scans.

- [ ] **Step 1: Run semantic residue scans**

Run:

```powershell
rg -n "ToolClass\.BASH|BackgroundBash|build_bash|bash_task_|name=\"bash\"|dangerous bash|confirmation_request|ConfirmationRequestEvent|ConfirmationGateway|ConfirmationDispatcher|confirmation_required|confirmation_meta|ConfirmActionRequest|confirm_action" newbee_notebook frontend/src docs/backend-v4 docs/frontend-v3
```

Expected remaining allowed matches only:

- `argv=("bash", "-lc", "echo ok")`
- dangerous command matcher pattern matching shell command text that pipes to `bash`
- deleted legacy files may appear in historical docs: `core/tools/bash.py`, `core/tools/bash_tasks.py`, and `core/engine/confirmation.py`
- tests explicitly verifying legacy compatibility
- business tool `confirm_diagram_type`

- [ ] **Step 2: Update docs**

Update design docs so active architecture points to:

- `shell`
- `shell_task_*`
- `PermissionRequestEvent`
- `permission_request`
- `PermissionRequestGateway`
- `permission_required`
- `permission_meta`
- `/permission-requests/resolve`

- [ ] **Step 3: Run full targeted verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/shell/ newbee_notebook/tests/unit/core/tools/ newbee_notebook/tests/unit/core/policy/ newbee_notebook/tests/unit/core/permission/ newbee_notebook/tests/unit/core/engine/ newbee_notebook/tests/unit/core/session/ newbee_notebook/tests/unit/skills/ newbee_notebook/tests/contract/api/test_chat_confirm.py newbee_notebook/tests/contract/api/test_chat_router_sse.py -q
cd frontend
pnpm vitest run src/lib/hooks/useChatSession.test.tsx src/components/chat/permission-request-card.test.tsx
pnpm typecheck
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add docs/backend-v4 docs/frontend-v3 newbee_notebook frontend/src
git commit -m "docs: align shell and permission terminology"
```

## Stop Conditions

- Stop if a change would remove legacy `/confirm` before frontend and tests use the new endpoint.
- Stop if `permission_request` SSE is emitted before frontend accepts it.
- Stop if `bash` is removed from low-level sandbox argv.
- Stop if old `confirmation_required` manifests stop loading.
- Stop if persistent `global:bash:*` allows are silently treated as `global:shell:*`; require re-approval instead.

## Self-Review

- Spec coverage: shell naming, permission naming, file list, frontend protocol boundary, compatibility, tests, and docs are covered by Tasks 1 to 8.
- Placeholder scan: no task depends on unspecified files or unnamed tests.
- Type consistency: canonical backend names are `shell`, `PermissionRequestEvent`, `PermissionRequestGateway`, `PermissionResolveRequest`, `permission_required`, and `permission_meta`; legacy names remain compatibility aliases only.
