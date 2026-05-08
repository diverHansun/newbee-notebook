# Policy Permission UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the frontend-v3 policy selector and Permission Request Card so users can choose default vs full-access agent policy and resolve permission requests with request/session/notebook scope.

**Architecture:** Add a small backend policy preference contract backed by `app_settings`, pass `agent_policy` through chat requests into `AgentLoop`, then update the chat frontend around a compact policy selector and a generic permission card. Permission scope is explicit: `once` resolves only the current request, `always_session` switches only the current session to full access, and `always_persist` switches the current notebook to full access.

**Tech Stack:** FastAPI + Pydantic + existing `AppSettingsService`; React 19 + Next.js 15; Zustand chat store; Testing Library + Vitest; existing CSS token system.

---

## File Structure

Backend contract files:

- Modify `newbee_notebook/api/models/requests.py`: add `agent_policy?: "default" | "yolo"` to `ChatRequest`.
- Modify `newbee_notebook/api/models/confirm_models.py`: keep `response` choice and extend response model in router.
- Create `newbee_notebook/api/models/policy_models.py`: request/response models for policy preference API.
- Create `newbee_notebook/application/services/policy_preference_service.py`: resolve and update notebook/session policy preferences in `app_settings`.
- Modify `newbee_notebook/api/dependencies.py`: add `get_policy_preference_service`.
- Create `newbee_notebook/api/routers/policy.py`: expose effective-policy read/update endpoints.
- Modify `newbee_notebook/api/main.py`: include policy router.
- Modify `newbee_notebook/api/routers/chat.py`: pass `agent_policy` into chat service and update confirm response.
- Modify `newbee_notebook/application/services/chat_service.py`: accept and forward `agent_policy`.
- Modify `newbee_notebook/core/session/session_manager.py`: pass `agent_policy` into `AgentLoop`.
- Modify `newbee_notebook/core/permission/session_cache.py`: support session-level allow-all for `always_session`.
- Modify `newbee_notebook/core/permission/recorder.py`: record `always_session` / `always_persist` as allow-all for the active session.
- Tests:
  - `newbee_notebook/tests/contract/api/test_policy_preferences.py`
  - `newbee_notebook/tests/contract/api/test_chat_confirm.py`
  - `newbee_notebook/tests/unit/core/session/test_session_manager.py`
  - `newbee_notebook/tests/unit/core/permission/test_gateway.py`

Frontend files:

- Modify `frontend/src/lib/api/types.ts`: add `AgentPolicy`, `PolicyScope`, expanded confirmation event, and chat request policy field.
- Modify `frontend/src/lib/api/chat.ts`: change confirm payload from boolean to response choice.
- Create `frontend/src/lib/api/policy.ts`: read/update policy preference API client.
- Modify `frontend/src/stores/chat-store.ts`: rename/extend pending confirmation model to permission-shaped data while preserving migration compatibility.
- Create `frontend/src/components/chat/policy-selector.tsx`: compact policy menu.
- Create `frontend/src/components/chat/policy-selector.test.tsx`: selector interaction tests.
- Modify `frontend/src/components/chat/confirmation-card.tsx`: convert the existing confirmation card into the generic permission request card.
- Modify `frontend/src/components/chat/confirmation-card.test.tsx`: four-choice card tests.
- Modify `frontend/src/components/chat/message-item.tsx`: call `onResolvePermission(requestId, response)`.
- Modify `frontend/src/components/chat/chat-panel.tsx`: pass policy state and callbacks.
- Modify `frontend/src/components/chat/chat-input.tsx`: render policy selector in toolbar.
- Modify `frontend/src/components/notebooks/notebook-workspace.tsx`: pass hook policy API into chat panel.
- Modify `frontend/src/lib/hooks/useChatSession.ts`: load policy, pass `agent_policy`, process expanded SSE event, resolve permission choices.
- Modify `frontend/src/lib/hooks/useChatSession.test.tsx`: policy scope and chat payload tests.
- Modify `frontend/src/lib/i18n/strings.ts`: add `policyPermission` strings.
- Modify `frontend/src/styles/chat.css`: add policy selector and permission card styles.

---

### Task 1: Backend Policy Preference Contract

**Files:**
- Create: `newbee_notebook/api/models/policy_models.py`
- Create: `newbee_notebook/application/services/policy_preference_service.py`
- Create: `newbee_notebook/api/routers/policy.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Modify: `newbee_notebook/api/main.py`
- Test: `newbee_notebook/tests/contract/api/test_policy_preferences.py`

- [ ] **Step 1: Write failing contract tests**

Create `newbee_notebook/tests/contract/api/test_policy_preferences.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from newbee_notebook.api.main import create_app
from newbee_notebook.api.dependencies import get_app_settings_service, get_session_service


class FakeSettings:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def get_many(self, prefix: str) -> dict[str, str]:
        return {key: value for key, value in self.values.items() if key.startswith(prefix)}

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


class FakeSession:
    session_id = "session-1"
    notebook_id = "nb-1"


class FakeSessionService:
    async def get_or_raise(self, session_id: str):
        assert session_id == "session-1"
        return FakeSession()


@pytest.fixture()
def client():
    settings = FakeSettings()
    app = create_app()
    app.dependency_overrides[get_app_settings_service] = lambda: settings
    app.dependency_overrides[get_session_service] = lambda: FakeSessionService()
    with TestClient(app) as test_client:
        yield test_client, settings
    app.dependency_overrides.clear()


def test_policy_effective_defaults_to_default(client):
    test_client, _settings = client

    response = test_client.get("/api/v1/policy/notebooks/nb-1/effective?session_id=session-1")

    assert response.status_code == 200
    assert response.json() == {
        "notebook_id": "nb-1",
        "session_id": "session-1",
        "policy": "default",
        "source": "default",
    }


def test_policy_update_session_scope(client):
    test_client, settings = client

    response = test_client.put(
        "/api/v1/policy/notebooks/nb-1",
        json={"scope": "session", "session_id": "session-1", "policy": "yolo"},
    )

    assert response.status_code == 200
    assert response.json()["policy"] == "yolo"
    assert response.json()["source"] == "session"
    assert settings.values["policy.sessions.session-1.agent_policy"] == "yolo"


def test_policy_update_notebook_scope(client):
    test_client, settings = client

    response = test_client.put(
        "/api/v1/policy/notebooks/nb-1",
        json={"scope": "notebook", "policy": "yolo"},
    )

    assert response.status_code == 200
    assert response.json()["policy"] == "yolo"
    assert response.json()["source"] == "notebook"
    assert settings.values["policy.notebooks.nb-1.agent_policy"] == "yolo"


def test_policy_default_clears_visible_session_scope(client):
    test_client, settings = client
    settings.values["policy.sessions.session-1.agent_policy"] = "yolo"

    response = test_client.put(
        "/api/v1/policy/notebooks/nb-1",
        json={"scope": "session", "session_id": "session-1", "policy": "default"},
    )

    assert response.status_code == 200
    assert response.json()["policy"] == "default"
    assert response.json()["source"] == "default"
    assert "policy.sessions.session-1.agent_policy" not in settings.values
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest newbee_notebook/tests/contract/api/test_policy_preferences.py -q`

Expected: FAIL because `newbee_notebook.api.routers.policy` and policy models do not exist.

- [ ] **Step 3: Add policy models**

Create `newbee_notebook/api/models/policy_models.py`:

```python
"""API models for frontend agent policy preferences."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

AgentPolicyValue = Literal["default", "yolo"]
PolicyScopeValue = Literal["session", "notebook"]
PolicySourceValue = Literal["default", "session", "notebook"]


class PolicyPreferenceUpdateRequest(BaseModel):
    scope: PolicyScopeValue
    policy: AgentPolicyValue
    session_id: str | None = None

    @model_validator(mode="after")
    def _validate_session_scope(self) -> "PolicyPreferenceUpdateRequest":
        if self.scope == "session" and not str(self.session_id or "").strip():
            raise ValueError("session_id is required for session scope")
        return self


class EffectivePolicyResponse(BaseModel):
    notebook_id: str
    session_id: str | None = None
    policy: AgentPolicyValue
    source: PolicySourceValue
```

- [ ] **Step 4: Add policy preference service**

Create `newbee_notebook/application/services/policy_preference_service.py`:

```python
"""Notebook/session-scoped agent policy preferences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

AgentPolicyValue = Literal["default", "yolo"]
PolicySourceValue = Literal["default", "session", "notebook"]


class SettingsStore(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str) -> None: ...
    async def delete(self, key: str) -> None: ...


@dataclass(frozen=True)
class EffectivePolicy:
    notebook_id: str
    session_id: str | None
    policy: AgentPolicyValue
    source: PolicySourceValue


class PolicyPreferenceService:
    def __init__(self, settings: SettingsStore) -> None:
        self._settings = settings

    @staticmethod
    def notebook_key(notebook_id: str) -> str:
        return f"policy.notebooks.{notebook_id}.agent_policy"

    @staticmethod
    def session_key(session_id: str) -> str:
        return f"policy.sessions.{session_id}.agent_policy"

    @staticmethod
    def _normalize(value: str | None) -> AgentPolicyValue:
        return "yolo" if str(value or "").strip().lower() == "yolo" else "default"

    async def get_effective(
        self,
        *,
        notebook_id: str,
        session_id: str | None = None,
    ) -> EffectivePolicy:
        if session_id:
            session_policy = self._normalize(await self._settings.get(self.session_key(session_id)))
            if session_policy == "yolo":
                return EffectivePolicy(notebook_id, session_id, "yolo", "session")
        notebook_policy = self._normalize(await self._settings.get(self.notebook_key(notebook_id)))
        if notebook_policy == "yolo":
            return EffectivePolicy(notebook_id, session_id, "yolo", "notebook")
        return EffectivePolicy(notebook_id, session_id, "default", "default")

    async def update_session(
        self,
        *,
        notebook_id: str,
        session_id: str,
        policy: AgentPolicyValue,
    ) -> EffectivePolicy:
        key = self.session_key(session_id)
        if policy == "yolo":
            await self._settings.set(key, "yolo")
        else:
            await self._settings.delete(key)
        return await self.get_effective(notebook_id=notebook_id, session_id=session_id)

    async def update_notebook(
        self,
        *,
        notebook_id: str,
        session_id: str | None,
        policy: AgentPolicyValue,
    ) -> EffectivePolicy:
        key = self.notebook_key(notebook_id)
        if policy == "yolo":
            await self._settings.set(key, "yolo")
        else:
            await self._settings.delete(key)
        return await self.get_effective(notebook_id=notebook_id, session_id=session_id)
```

- [ ] **Step 5: Add router and dependency**

Modify `newbee_notebook/api/dependencies.py`:

```python
from newbee_notebook.application.services.policy_preference_service import PolicyPreferenceService


def get_policy_preference_service(
    settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> PolicyPreferenceService:
    return PolicyPreferenceService(settings_service)
```

Create `newbee_notebook/api/routers/policy.py`:

```python
"""Agent policy preference endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from newbee_notebook.api.dependencies import get_policy_preference_service, get_session_service
from newbee_notebook.api.models.policy_models import (
    EffectivePolicyResponse,
    PolicyPreferenceUpdateRequest,
)
from newbee_notebook.application.services.policy_preference_service import PolicyPreferenceService
from newbee_notebook.application.services.session_service import SessionService, SessionNotFoundError

router = APIRouter(prefix="/policy")


@router.get("/notebooks/{notebook_id}/effective", response_model=EffectivePolicyResponse)
async def get_effective_policy(
    notebook_id: str = Path(...),
    session_id: str | None = Query(None),
    service: PolicyPreferenceService = Depends(get_policy_preference_service),
):
    policy = await service.get_effective(notebook_id=notebook_id, session_id=session_id)
    return EffectivePolicyResponse(**policy.__dict__)


@router.put("/notebooks/{notebook_id}", response_model=EffectivePolicyResponse)
async def update_policy(
    request: PolicyPreferenceUpdateRequest,
    notebook_id: str = Path(...),
    policy_service: PolicyPreferenceService = Depends(get_policy_preference_service),
    session_service: SessionService = Depends(get_session_service),
):
    session_id = request.session_id
    if request.scope == "session":
        try:
            session = await session_service.get_or_raise(str(session_id))
        except SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        if session.notebook_id != notebook_id:
            raise HTTPException(status_code=400, detail="Session does not belong to notebook")
        policy = await policy_service.update_session(
            notebook_id=notebook_id,
            session_id=str(session_id),
            policy=request.policy,
        )
    else:
        policy = await policy_service.update_notebook(
            notebook_id=notebook_id,
            session_id=session_id,
            policy=request.policy,
        )
    return EffectivePolicyResponse(**policy.__dict__)
```

Modify `newbee_notebook/api/main.py`:

```python
from newbee_notebook.api.routers import policy

app.include_router(policy.router, prefix="/api/v1", tags=["Policy"])
```

- [ ] **Step 6: Run contract tests**

Run: `pytest newbee_notebook/tests/contract/api/test_policy_preferences.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add newbee_notebook/api/models/policy_models.py newbee_notebook/application/services/policy_preference_service.py newbee_notebook/api/routers/policy.py newbee_notebook/api/dependencies.py newbee_notebook/api/main.py newbee_notebook/tests/contract/api/test_policy_preferences.py
git commit -m "feat(policy): add agent policy preference API"
```

---

### Task 2: Backend Agent Policy Plumbing

**Files:**
- Modify: `newbee_notebook/api/models/requests.py`
- Modify: `newbee_notebook/api/routers/chat.py`
- Modify: `newbee_notebook/application/services/chat_service.py`
- Modify: `newbee_notebook/core/session/session_manager.py`
- Modify: `newbee_notebook/core/permission/session_cache.py`
- Modify: `newbee_notebook/core/permission/recorder.py`
- Test: `newbee_notebook/tests/unit/core/session/test_session_manager.py`
- Test: `newbee_notebook/tests/unit/core/permission/test_gateway.py`

- [ ] **Step 1: Write failing tests for policy pass-through**

Add to `newbee_notebook/tests/unit/core/session/test_session_manager.py`:

```python
@pytest.mark.anyio
async def test_session_manager_passes_agent_policy_to_agent_loop():
    session_repo = AsyncMock()
    session_repo.get.return_value = Session(session_id="s1", notebook_id="nb1")
    message_repo = AsyncMock()
    message_repo.list_after_boundary.return_value = []
    message_repo.list_by_session.return_value = []
    tool_registry = DummyToolRegistry()
    manager = SessionManager(
        session_repo=session_repo,
        message_repo=message_repo,
        llm_client=DummyLLMClient(),
        tool_registry=tool_registry,
        lock_manager=None,
        agent_loop_cls=RecordingLoop,
        system_prompt_provider=lambda mode: f"prompt:{mode.value}",
    )
    await manager.start_session(session_id="s1")

    RecordingLoop.stream_events = [ContentEvent(delta="ok")]
    await manager.chat(message="hi", mode_type=ModeType.AGENT, agent_policy="yolo")

    assert RecordingLoop.instances[-1].agent_policy == "yolo"
```

- [ ] **Step 2: Write failing tests for session allow-all**

Add to `newbee_notebook/tests/unit/core/permission/test_gateway.py`:

```python
def test_session_allow_cache_can_allow_all_capabilities_in_session():
    cache = SessionAllowCache()

    cache.add_all("session-1")

    assert cache.contains("session-1", "global:bash:abc")
    assert cache.contains("session-1", "global:write_file:def")
    assert not cache.contains("session-2", "global:bash:abc")
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pytest newbee_notebook/tests/unit/core/session/test_session_manager.py::test_session_manager_passes_agent_policy_to_agent_loop newbee_notebook/tests/unit/core/permission/test_gateway.py::test_session_allow_cache_can_allow_all_capabilities_in_session -q
```

Expected: FAIL because `agent_policy` is not accepted by `SessionManager.chat_stream`, and `SessionAllowCache.add_all` does not exist.

- [ ] **Step 4: Add `agent_policy` to chat request model**

Modify `newbee_notebook/api/models/requests.py` `ChatRequest`:

```python
    agent_policy: Literal["default", "yolo"] = Field(
        "default",
        description="Agent execution policy. 'default' asks for sensitive actions; 'yolo' skips permission prompts while keeping sandbox.",
    )
```

- [ ] **Step 5: Thread `agent_policy` through chat router and service**

Modify `newbee_notebook/api/routers/chat.py` in both non-stream and stream paths:

```python
agent_policy=request.agent_policy,
```

Modify `newbee_notebook/application/services/chat_service.py` method signatures for `chat` and `chat_stream`:

```python
agent_policy: str = "default",
```

Pass it to the runtime session manager call:

```python
agent_policy=agent_policy,
```

- [ ] **Step 6: Thread `agent_policy` through SessionManager**

Modify `newbee_notebook/core/session/session_manager.py`:

```python
async def _build_loop(
    self,
    *,
    mode: ModeType,
    allowed_document_ids: list[str] | None,
    context: dict | None,
    agent_policy: str | None = None,
    ...
):
    ...
    loop_kwargs = dict(
        ...
        agent_policy=agent_policy,
    )
```

Add `agent_policy` to `chat_stream` and `chat` signatures and pass it from `chat` to `chat_stream`:

```python
agent_policy: str | None = None,
```

- [ ] **Step 7: Add session allow-all cache support**

Modify `newbee_notebook/core/permission/session_cache.py`:

```python
ALLOW_ALL = "*"


class SessionAllowCache:
    ...
    def contains(self, session_id: str, capability_signature: str) -> bool:
        signatures = self._allows.get(str(session_id or ""), set())
        return ALLOW_ALL in signatures or str(capability_signature or "") in signatures

    def add_all(self, session_id: str) -> None:
        normalized_session = str(session_id or "").strip()
        if not normalized_session:
            return
        self._allows[normalized_session].add(ALLOW_ALL)
```

Modify `newbee_notebook/core/permission/recorder.py`:

```python
        if normalized_choice is PermissionChoice.ALWAYS_SESSION:
            self._session_cache.add_all(request.session_id)
            return PermissionResponse.allow(reason="always_session")
        if normalized_choice is PermissionChoice.ALWAYS_PERSIST:
            self._session_cache.add_all(request.session_id)
            try:
                await self._allow_store.write(request.capability_signature)
```

- [ ] **Step 8: Run targeted tests**

Run:

```bash
pytest newbee_notebook/tests/unit/core/session/test_session_manager.py newbee_notebook/tests/unit/core/permission/test_gateway.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add newbee_notebook/api/models/requests.py newbee_notebook/api/routers/chat.py newbee_notebook/application/services/chat_service.py newbee_notebook/core/session/session_manager.py newbee_notebook/core/permission/session_cache.py newbee_notebook/core/permission/recorder.py newbee_notebook/tests/unit/core/session/test_session_manager.py newbee_notebook/tests/unit/core/permission/test_gateway.py
git commit -m "feat(chat): pass agent policy into runtime"
```

---

### Task 3: Confirm Response Applies Policy Scope

**Files:**
- Modify: `newbee_notebook/api/routers/chat.py`
- Modify: `newbee_notebook/api/models/confirm_models.py`
- Test: `newbee_notebook/tests/contract/api/test_chat_confirm.py`

- [ ] **Step 1: Write failing confirm scope test**

Add to `newbee_notebook/tests/contract/api/test_chat_confirm.py`:

```python
def test_confirm_always_session_returns_effective_policy(client):
    response = client.post(
        "/api/v1/chat/session-1/confirm",
        json={"request_id": "req-1", "response": "always_session"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert response.json()["effective_policy"]["policy"] == "yolo"
    assert response.json()["effective_policy"]["source"] == "session"
```

Replace the helper in `newbee_notebook/tests/contract/api/test_chat_confirm.py` with this version so the router has all dependencies it needs:

```python
from dataclasses import dataclass

from newbee_notebook.api.dependencies import (
    get_chat_service,
    get_policy_preference_service,
    get_session_service,
)


@dataclass(frozen=True)
class _FakeEffectivePolicy:
    notebook_id: str
    session_id: str | None
    policy: str
    source: str


class _FakePolicyPreferenceService:
    async def update_session(self, *, notebook_id: str, session_id: str, policy: str):
        return _FakeEffectivePolicy(notebook_id, session_id, policy, "session")

    async def update_notebook(self, *, notebook_id: str, session_id: str | None, policy: str):
        return _FakeEffectivePolicy(notebook_id, session_id, policy, "notebook")


class _FakeSession:
    session_id = "session-1"
    notebook_id = "nb-1"


class _FakeSessionService:
    async def get_or_raise(self, session_id: str):
        assert session_id == "session-1"
        return _FakeSession()


def _build_client(chat_service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(chat_router.router, prefix="/api/v1")

    async def _override_chat():
        return chat_service

    async def _override_session():
        return _FakeSessionService()

    async def _override_policy():
        return _FakePolicyPreferenceService()

    app.dependency_overrides[get_chat_service] = _override_chat
    app.dependency_overrides[get_session_service] = _override_session
    app.dependency_overrides[get_policy_preference_service] = _override_policy
    return TestClient(app)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest newbee_notebook/tests/contract/api/test_chat_confirm.py -q`

Expected: FAIL because confirm response currently only returns `{status}`.

- [ ] **Step 3: Extend confirm response model**

Modify `newbee_notebook/api/routers/chat.py`:

```python
class ConfirmActionResponse(BaseModel):
    status: str
    effective_policy: dict | None = None
```

Inject policy service and session service into `confirm_action`:

```python
policy_service: PolicyPreferenceService = Depends(get_policy_preference_service),
session_service: SessionService = Depends(get_session_service),
```

After `resolved` is true:

```python
effective_policy = None
if request.response in {"always_session", "always_persist"}:
    session = await session_service.get_or_raise(session_id)
    if request.response == "always_session":
        policy = await policy_service.update_session(
            notebook_id=session.notebook_id,
            session_id=session_id,
            policy="yolo",
        )
    else:
        policy = await policy_service.update_notebook(
            notebook_id=session.notebook_id,
            session_id=session_id,
            policy="yolo",
        )
    effective_policy = policy.__dict__
return ConfirmActionResponse(status="resolved", effective_policy=effective_policy)
```

- [ ] **Step 4: Run confirm tests**

Run: `pytest newbee_notebook/tests/contract/api/test_chat_confirm.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add newbee_notebook/api/routers/chat.py newbee_notebook/tests/contract/api/test_chat_confirm.py
git commit -m "feat(permission): return policy scope from confirm action"
```

---

### Task 4: Frontend API Types and Clients

**Files:**
- Modify: `frontend/src/lib/api/types.ts`
- Modify: `frontend/src/lib/api/chat.ts`
- Create: `frontend/src/lib/api/policy.ts`
- Test: `frontend/src/lib/api/policy.test.ts`

- [ ] **Step 1: Add policy API client test**

Create `frontend/src/lib/api/policy.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getEffectivePolicy, updatePolicyPreference } from "@/lib/api/policy";

const fetchMock = vi.fn();

describe("policy api", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("reads effective policy", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({
        notebook_id: "nb-1",
        session_id: "session-1",
        policy: "default",
        source: "default",
      }),
    });

    const result = await getEffectivePolicy("nb-1", "session-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/policy/notebooks/nb-1/effective?session_id=session-1",
      expect.any(Object)
    );
    expect(result.policy).toBe("default");
  });

  it("updates session policy", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({
        notebook_id: "nb-1",
        session_id: "session-1",
        policy: "yolo",
        source: "session",
      }),
    });

    const result = await updatePolicyPreference("nb-1", {
      scope: "session",
      session_id: "session-1",
      policy: "yolo",
    });

    expect(result.source).toBe("session");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend; pnpm vitest run src/lib/api/policy.test.ts`

Expected: FAIL because `policy.ts` does not exist.

- [ ] **Step 3: Add frontend types**

Modify `frontend/src/lib/api/types.ts`:

```ts
export type AgentPolicy = "default" | "yolo";
export type PolicyScope = "session" | "notebook";
export type PolicySource = "default" | "session" | "notebook";
export type PermissionResponseChoice = "once" | "always_session" | "always_persist" | "reject";

export type EffectivePolicy = {
  notebook_id: string;
  session_id: string | null;
  policy: AgentPolicy;
  source: PolicySource;
};

export type PolicyPreferenceUpdate = {
  scope: PolicyScope;
  policy: AgentPolicy;
  session_id?: string | null;
};
```

Extend `ChatRequest`:

```ts
agent_policy?: AgentPolicy;
```

Extend `SseEventConfirmation`:

```ts
capability_signature?: string;
risk_level?: string;
skill_name?: string | null;
content_hash?: string;
response_options?: PermissionResponseChoice[];
```

- [ ] **Step 4: Update chat confirm client**

Modify `frontend/src/lib/api/chat.ts`:

```ts
import type { PermissionResponseChoice } from "@/lib/api/types";

type ConfirmActionRequest = {
  request_id: string;
  response: PermissionResponseChoice;
  suggestion?: string;
};

type ConfirmActionResponse = {
  status: "resolved";
  effective_policy?: {
    notebook_id: string;
    session_id: string | null;
    policy: "default" | "yolo";
    source: "default" | "session" | "notebook";
  } | null;
};
```

- [ ] **Step 5: Add policy API client**

Create `frontend/src/lib/api/policy.ts`:

```ts
import { apiFetch } from "@/lib/api/client";
import type { EffectivePolicy, PolicyPreferenceUpdate } from "@/lib/api/types";

export function getEffectivePolicy(notebookId: string, sessionId?: string | null) {
  const search = new URLSearchParams();
  if (sessionId) search.set("session_id", sessionId);
  const query = search.toString();
  return apiFetch<EffectivePolicy>(
    `/policy/notebooks/${notebookId}/effective${query ? `?${query}` : ""}`
  );
}

export function updatePolicyPreference(
  notebookId: string,
  update: PolicyPreferenceUpdate
) {
  return apiFetch<EffectivePolicy>(`/policy/notebooks/${notebookId}`, {
    method: "PUT",
    body: update,
  });
}
```

- [ ] **Step 6: Run tests**

Run: `cd frontend; pnpm vitest run src/lib/api/policy.test.ts`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api/types.ts frontend/src/lib/api/chat.ts frontend/src/lib/api/policy.ts frontend/src/lib/api/policy.test.ts
git commit -m "feat(frontend): add policy API client types"
```

---

### Task 5: Policy Selector UI

**Files:**
- Create: `frontend/src/components/chat/policy-selector.tsx`
- Create: `frontend/src/components/chat/policy-selector.test.tsx`
- Modify: `frontend/src/lib/i18n/strings.ts`
- Modify: `frontend/src/styles/chat.css`

- [ ] **Step 1: Write component tests**

Create `frontend/src/components/chat/policy-selector.test.tsx`:

```tsx
import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PolicySelector } from "@/components/chat/policy-selector";
import { renderWithLang } from "@/test/test-utils";

describe("PolicySelector", () => {
  it("renders current default policy and opens menu", () => {
    renderWithLang(
      <PolicySelector
        policy={{ notebook_id: "nb-1", session_id: "session-1", policy: "default", source: "default" }}
        disabled={false}
        onChange={() => {}}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Agent permission policy" }));

    expect(screen.getByRole("menuitem", { name: "Default permission" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Full access permission" })).toBeInTheDocument();
  });

  it("requests session full access when choosing full access from default", () => {
    const onChange = vi.fn();
    renderWithLang(
      <PolicySelector
        policy={{ notebook_id: "nb-1", session_id: "session-1", policy: "default", source: "default" }}
        disabled={false}
        onChange={onChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Agent permission policy" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Full access permission" }));

    expect(onChange).toHaveBeenCalledWith({
      scope: "session",
      session_id: "session-1",
      policy: "yolo",
    });
  });

  it("clears notebook policy when visible source is notebook", () => {
    const onChange = vi.fn();
    renderWithLang(
      <PolicySelector
        policy={{ notebook_id: "nb-1", session_id: "session-1", policy: "yolo", source: "notebook" }}
        disabled={false}
        onChange={onChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Agent permission policy" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Default permission" }));

    expect(onChange).toHaveBeenCalledWith({
      scope: "notebook",
      session_id: "session-1",
      policy: "default",
    });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend; pnpm vitest run src/components/chat/policy-selector.test.tsx`

Expected: FAIL because `PolicySelector` does not exist.

- [ ] **Step 3: Add strings**

Modify `frontend/src/lib/i18n/strings.ts`:

```ts
policyPermission: {
  policyButtonLabel: { zh: "Agent 权限策略", en: "Agent permission policy" },
  defaultPolicy: { zh: "默认权限", en: "Default permission" },
  fullAccessPolicy: { zh: "完全访问权限", en: "Full access permission" },
  sessionScope: { zh: "当前会话", en: "Current session" },
  notebookScope: { zh: "当前 Notebook", en: "Current notebook" },
  sandboxHint: { zh: "仍在沙箱中执行", en: "Still runs in sandbox" },
}
```

- [ ] **Step 4: Add PolicySelector component**

Create `frontend/src/components/chat/policy-selector.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";

import type { EffectivePolicy, PolicyPreferenceUpdate } from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type PolicySelectorProps = {
  policy: EffectivePolicy;
  disabled?: boolean;
  onChange: (update: PolicyPreferenceUpdate) => void;
};

function ShieldIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 1.8 13 3.7v3.8c0 3.1-2 5.7-5 6.7-3-1-5-3.6-5-6.7V3.7L8 1.8Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <path d="M6.2 8.1 7.4 9.3 10.1 6.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function PolicySelector({ policy, disabled = false, onChange }: PolicySelectorProps) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const isFullAccess = policy.policy === "yolo";
  const label = isFullAccess
    ? t(uiStrings.policyPermission.fullAccessPolicy)
    : t(uiStrings.policyPermission.defaultPolicy);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (target && rootRef.current?.contains(target)) return;
      setOpen(false);
    };
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  const chooseDefault = () => {
    const scope = policy.source === "notebook" ? "notebook" : "session";
    onChange({ scope, session_id: policy.session_id, policy: "default" });
    setOpen(false);
  };

  const chooseFullAccess = () => {
    onChange({ scope: "session", session_id: policy.session_id, policy: "yolo" });
    setOpen(false);
  };

  return (
    <div className="policy-selector" ref={rootRef}>
      <button
        type="button"
        className={`policy-selector-trigger${isFullAccess ? " is-yolo" : ""}`}
        aria-label={t(uiStrings.policyPermission.policyButtonLabel)}
        aria-expanded={open}
        disabled={disabled}
        onClick={() => {
          if (!disabled) setOpen((value) => !value);
        }}
      >
        <ShieldIcon />
        <span className="policy-selector-label">{label}</span>
        <span className="policy-selector-chevron" aria-hidden="true">⌄</span>
      </button>
      {open ? (
        <div className="policy-selector-menu" role="menu">
          <button type="button" role="menuitem" className="policy-selector-item" onClick={chooseDefault}>
            <span>{t(uiStrings.policyPermission.defaultPolicy)}</span>
            {!isFullAccess ? <span aria-hidden="true">✓</span> : null}
          </button>
          <button type="button" role="menuitem" className="policy-selector-item" onClick={chooseFullAccess}>
            <span>{t(uiStrings.policyPermission.fullAccessPolicy)}</span>
            {isFullAccess ? <span aria-hidden="true">✓</span> : null}
          </button>
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 5: Add CSS**

Modify `frontend/src/styles/chat.css`:

```css
.policy-selector {
  position: relative;
  display: inline-flex;
}

.policy-selector-trigger {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 176px;
  height: 28px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: hsl(var(--accent));
  color: hsl(var(--muted-foreground));
  padding: 0 9px;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
}

.policy-selector-trigger.is-yolo {
  background: hsl(var(--bee-yellow-light));
  color: hsl(var(--bee-amber));
  border-color: hsl(var(--bee-amber) / 0.24);
}

.policy-selector-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.policy-selector-menu {
  position: absolute;
  left: 0;
  bottom: calc(100% + 6px);
  z-index: 45;
  min-width: 196px;
  border: 1px solid hsl(var(--border));
  border-radius: 10px;
  background: hsl(var(--card));
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.16);
  padding: 6px;
}

.policy-selector-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: hsl(var(--foreground));
  padding: 8px 10px;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.policy-selector-item:hover,
.policy-selector-item:focus-visible {
  outline: none;
  background: hsl(var(--accent));
}
```

- [ ] **Step 6: Run component tests**

Run: `cd frontend; pnpm vitest run src/components/chat/policy-selector.test.tsx`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/chat/policy-selector.tsx frontend/src/components/chat/policy-selector.test.tsx frontend/src/lib/i18n/strings.ts frontend/src/styles/chat.css
git commit -m "feat(frontend): add chat policy selector"
```

---

### Task 6: Permission Request Card

**Files:**
- Modify: `frontend/src/components/chat/confirmation-card.tsx`
- Modify: `frontend/src/components/chat/confirmation-card.test.tsx`
- Modify: `frontend/src/stores/chat-store.ts`
- Modify: `frontend/src/lib/i18n/strings.ts`
- Modify: `frontend/src/styles/chat.css`

- [ ] **Step 1: Update tests for four choices**

Replace the primary test in `frontend/src/components/chat/confirmation-card.test.tsx` with:

```tsx
it("renders permission request details and emits response choices", () => {
  const onResolve = vi.fn();

  renderWithLang(
    <ConfirmationCard
      confirmation={{
        ...createPendingConfirmation(),
        responseOptions: ["once", "always_session", "always_persist", "reject"],
      }}
      onResolve={onResolve}
    />
  );

  expect(screen.getByText("Update note metadata.")).toBeInTheDocument();
  expect(screen.getByText("update_note")).toBeInTheDocument();
  expect(screen.getByText("note-1")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Allow once" }));
  fireEvent.click(screen.getByRole("button", { name: "Always allow in this session" }));
  fireEvent.click(screen.getByRole("button", { name: "Always allow in this notebook" }));
  fireEvent.click(screen.getByRole("button", { name: "Reject" }));

  expect(onResolve).toHaveBeenNthCalledWith(1, "once");
  expect(onResolve).toHaveBeenNthCalledWith(2, "always_session");
  expect(onResolve).toHaveBeenNthCalledWith(3, "always_persist");
  expect(onResolve).toHaveBeenNthCalledWith(4, "reject");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend; pnpm vitest run src/components/chat/confirmation-card.test.tsx`

Expected: FAIL because `ConfirmationCard` still expects `onConfirm/onReject`.

- [ ] **Step 3: Extend store types**

Modify `frontend/src/stores/chat-store.ts`:

```ts
import type { PermissionResponseChoice } from "@/lib/api/types";

export type PendingConfirmationStatus =
  | "pending"
  | "resolving"
  | "confirmed"
  | "rejected"
  | "timeout"
  | "error"
  | "collapsed";

export type PendingConfirmation = {
  requestId: string;
  toolName: string;
  actionType: string;
  targetType: string;
  argsSummary: Record<string, unknown>;
  description: string;
  status: PendingConfirmationStatus;
  expiresAt: number;
  capabilitySignature?: string;
  riskLevel?: string;
  skillName?: string | null;
  contentHash?: string;
  responseOptions?: PermissionResponseChoice[];
  errorMessage?: string;
  resolvedFrom?: "confirmed" | "rejected" | "timeout";
};
```

- [ ] **Step 4: Add strings**

Modify `frontend/src/lib/i18n/strings.ts` under `confirmation`:

```ts
permissionTitle: { zh: "权限请求", en: "Permission request" },
allowOnce: { zh: "允许本次", en: "Allow once" },
allowSession: { zh: "本会话始终允许", en: "Always allow in this session" },
allowNotebook: { zh: "永久允许", en: "Always allow in this notebook" },
tool: { zh: "工具", en: "Tool" },
sandboxHint: { zh: "仍在沙箱中执行", en: "Still runs in sandbox" },
submitFailed: { zh: "权限选择提交失败，请重试。", en: "Failed to submit permission choice. Try again." },
```

- [ ] **Step 5: Update card component**

Modify `frontend/src/components/chat/confirmation-card.tsx` so props are:

```ts
type ConfirmationCardProps = {
  confirmation: PendingConfirmation;
  onResolve: (response: PermissionResponseChoice) => void;
};
```

Render buttons from:

```ts
const options = confirmation.responseOptions?.length
  ? confirmation.responseOptions
  : ["once", "always_session", "always_persist", "reject"];
```

Map labels:

```ts
const responseLabels: Record<PermissionResponseChoice, LocalizedString> = {
  once: uiStrings.confirmation.allowOnce,
  always_session: uiStrings.confirmation.allowSession,
  always_persist: uiStrings.confirmation.allowNotebook,
  reject: uiStrings.confirmation.reject,
};
```

Call:

```tsx
onClick={() => onResolve(option)}
```

- [ ] **Step 6: Add card CSS**

Modify `frontend/src/styles/chat.css`:

```css
.confirmation-card {
  margin-top: 8px;
  border: 1px solid hsl(var(--border));
  border-radius: 10px;
  background: hsl(var(--card));
  padding: 12px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.confirmation-card-header strong {
  font-size: 13px;
}

.confirmation-card-description {
  margin: 8px 0 0;
  color: hsl(var(--foreground));
  font-size: 13px;
  line-height: 1.5;
}

.confirmation-card-actions {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.confirmation-card-actions .btn {
  min-width: 0;
  white-space: normal;
  line-height: 1.25;
}

@media (max-width: 520px) {
  .confirmation-card-actions {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 7: Run card tests**

Run: `cd frontend; pnpm vitest run src/components/chat/confirmation-card.test.tsx`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/chat/confirmation-card.tsx frontend/src/components/chat/confirmation-card.test.tsx frontend/src/stores/chat-store.ts frontend/src/lib/i18n/strings.ts frontend/src/styles/chat.css
git commit -m "feat(frontend): upgrade confirmation card to permission request"
```

---

### Task 7: useChatSession Policy Integration

**Files:**
- Modify: `frontend/src/lib/hooks/useChatSession.ts`
- Modify: `frontend/src/lib/hooks/useChatSession.test.tsx`
- Modify: `frontend/src/components/chat/chat-panel.tsx`
- Modify: `frontend/src/components/chat/chat-input.tsx`
- Modify: `frontend/src/components/chat/message-item.tsx`
- Modify: `frontend/src/components/notebooks/notebook-workspace.tsx`

- [ ] **Step 1: Extend hook mocks and tests**

Modify `frontend/src/lib/hooks/useChatSession.test.tsx` mock setup:

```ts
const getEffectivePolicy = vi.fn();
const updatePolicyPreference = vi.fn();
const confirmChatAction = vi.fn();

vi.mock("@/lib/api/policy", () => ({
  getEffectivePolicy: (...args: unknown[]) => getEffectivePolicy(...args),
  updatePolicyPreference: (...args: unknown[]) => updatePolicyPreference(...args),
}));

vi.mock("@/lib/api/chat", () => ({
  chatOnce: (...args: unknown[]) => chatOnce(...args),
  confirmChatAction: (...args: unknown[]) => confirmChatAction(...args),
}));
```

Add beforeEach defaults:

```ts
getEffectivePolicy.mockResolvedValue({
  notebook_id: "nb-1",
  session_id: "session-1",
  policy: "default",
  source: "default",
});
updatePolicyPreference.mockImplementation(async (_notebookId: string, update: { policy: string; scope: string; session_id?: string }) => ({
  notebook_id: "nb-1",
  session_id: update.session_id ?? "session-1",
  policy: update.policy,
  source: update.policy === "yolo" ? update.scope : "default",
}));
confirmChatAction.mockResolvedValue({ status: "resolved" });
```

Add test:

```ts
it("sends current agent policy with chat stream requests", async () => {
  getEffectivePolicy.mockResolvedValueOnce({
    notebook_id: "nb-1",
    session_id: "session-1",
    policy: "yolo",
    source: "session",
  });
  const { wrapper } = createWrapper();
  const { result } = renderHook(() => useChatSession("nb-1"), { wrapper });

  await waitFor(() => expect(result.current.policy.policy).toBe("yolo"));

  await act(async () => {
    await result.current.sendMessage("Run checks", "agent");
  });

  expect(startStream).toHaveBeenCalledWith(
    "nb-1",
    expect.objectContaining({ agent_policy: "yolo" }),
    expect.any(Object)
  );
});
```

Add test:

```ts
it("resolves always_session and updates session policy", async () => {
  const { wrapper } = createWrapper();
  const { result } = renderHook(() => useChatSession("nb-1"), { wrapper });

  await waitFor(() => expect(result.current.currentSessionId).toBe("session-1"));
  await act(async () => {
    await result.current.sendMessage("Update note", "agent");
  });
  await act(async () => {
    await result.current.resolveConfirmation("req-1", "always_session");
  });

  expect(confirmChatAction).toHaveBeenCalledWith("session-1", {
    request_id: "req-1",
    response: "always_session",
  });
  expect(result.current.policy.policy).toBe("yolo");
  expect(result.current.policy.source).toBe("session");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend; pnpm vitest run src/lib/hooks/useChatSession.test.tsx`

Expected: FAIL because `policy` and response-based `resolveConfirmation` are not implemented.

- [ ] **Step 3: Update hook state and send flow**

Modify `frontend/src/lib/hooks/useChatSession.ts`:

```ts
const DEFAULT_POLICY: EffectivePolicy = {
  notebook_id: notebookId,
  session_id: null,
  policy: "default",
  source: "default",
};
const [policy, setPolicy] = useState<EffectivePolicy>(DEFAULT_POLICY);
```

Load effective policy when `currentSessionId` changes:

```ts
useEffect(() => {
  let cancelled = false;
  void getEffectivePolicy(notebookId, currentSessionId).then((nextPolicy) => {
    if (!cancelled) setPolicy(nextPolicy);
  });
  return () => {
    cancelled = true;
  };
}, [notebookId, currentSessionId]);
```

When sending chat:

```ts
agent_policy: policy.policy,
```

- [ ] **Step 4: Update SSE mapping**

In `trackPendingConfirmation`, map expanded fields:

```ts
capabilitySignature: event.capability_signature,
riskLevel: event.risk_level,
skillName: event.skill_name,
contentHash: event.content_hash,
responseOptions: event.response_options,
```

- [ ] **Step 5: Update resolve function**

Change signature:

```ts
const resolveConfirmation = useCallback(
  async (requestId: string, response: PermissionResponseChoice) => {
```

Call API:

```ts
const result = await confirmChatAction(sessionId, {
  request_id: requestId,
  response,
});
if (result.effective_policy) {
  setPolicy(result.effective_policy);
}
```

For compatibility with older backend responses, add this fallback immediately after the successful confirm call:

```ts
if (!result.effective_policy && (response === "always_session" || response === "always_persist")) {
  const scope = response === "always_session" ? "session" : "notebook";
  const nextPolicy = await updatePolicyPreference(notebookId, {
    scope,
    session_id: sessionId,
    policy: "yolo",
  });
  setPolicy(nextPolicy);
}
```

- [ ] **Step 6: Wire components**

Update prop types:

```ts
onResolveConfirmation?: (requestId: string, response: PermissionResponseChoice) => void;
```

Pass `policy` and `onPolicyChange` from `NotebookWorkspace` → `ChatPanel` → `ChatInput`.

In `ChatInput`, render:

```tsx
<PolicySelector
  policy={policy}
  disabled={isStreaming}
  onChange={onPolicyChange}
/>
```

In `MessageItem`, call:

```tsx
onResolve={() => onResolveConfirmation?.(message.pendingConfirmation!.requestId, response)}
```

- [ ] **Step 7: Run hook tests**

Run: `cd frontend; pnpm vitest run src/lib/hooks/useChatSession.test.tsx`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/hooks/useChatSession.ts frontend/src/lib/hooks/useChatSession.test.tsx frontend/src/components/chat/chat-panel.tsx frontend/src/components/chat/chat-input.tsx frontend/src/components/chat/message-item.tsx frontend/src/components/notebooks/notebook-workspace.tsx
git commit -m "feat(frontend): wire policy state into chat flow"
```

---

### Task 8: Verification and Browser Smoke

**Files:**
- Modify after verification only when a concrete mismatch is observed: frontend CSS/component files.

- [ ] **Step 1: Run backend targeted tests**

Run:

```bash
pytest newbee_notebook/tests/contract/api/test_policy_preferences.py newbee_notebook/tests/contract/api/test_chat_confirm.py newbee_notebook/tests/unit/core/session/test_session_manager.py newbee_notebook/tests/unit/core/permission/test_gateway.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend targeted tests**

Run:

```bash
cd frontend
pnpm vitest run src/lib/api/policy.test.ts src/components/chat/policy-selector.test.tsx src/components/chat/confirmation-card.test.tsx src/lib/hooks/useChatSession.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run frontend typecheck**

Run:

```bash
cd frontend
pnpm typecheck
```

Expected: PASS.

- [ ] **Step 4: Run backend smoke**

Start FastAPI using the project’s normal backend command. Then verify:

```bash
curl http://localhost:8000/api/v1/policy/notebooks/nb-smoke/effective
```

Expected response contains:

```json
{"notebook_id":"nb-smoke","session_id":null,"policy":"default","source":"default"}
```

- [ ] **Step 5: Run frontend dev server and inspect**

Start frontend:

```bash
cd frontend
pnpm dev
```

Open `http://localhost:3000` and inspect:

- Policy selector appears in chat toolbar.
- Default permission is compact and does not crowd source selector.
- Full access state uses amber styling.
- Menu closes on outside click.
- Permission card buttons do not overflow on desktop.
- Narrow viewport stacks permission buttons vertically.

- [ ] **Step 6: Commit verification fixes**

When verification finds CSS or behavior mismatches, commit those concrete fixes:

```bash
git add frontend/src/styles/chat.css frontend/src/components/chat
git commit -m "fix(frontend): polish policy permission interactions"
```

When verification finds no mismatches, do not create an empty commit.

---

## Self-Review

Spec coverage:

- Default vs full access policy selector: covered by Tasks 4, 5, 7.
- No Auto Review policy: covered by selector with two menu items only.
- Permission Request Card replacing hard-coded confirmation: covered by Task 6.
- `once` / `always_session` / `always_persist` / `reject`: covered by Tasks 3, 6, 7.
- Session-scoped full access: covered by Tasks 1, 2, 3, 7.
- Notebook-scoped persistent full access: covered by Tasks 1, 3, 7.
- Manual switch back to default: covered by Tasks 1, 5, 7.
- Sandbox remains backend-only: preserved by no frontend bash/sandbox panel tasks.
- Backend contract needed for real behavior: covered by Tasks 1, 2, 3.
- Tests and smoke verification: covered by Task 8.

Placeholder scan:

- No `TODO`, `TBD`, or incomplete placeholder steps are intentionally left in this plan.

Type consistency:

- Frontend policy values use `default | yolo`.
- Frontend response choices use `once | always_session | always_persist | reject`.
- Backend policy API uses the same values.
