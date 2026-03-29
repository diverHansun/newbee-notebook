# Notebook Session Limit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Raise the backend per-notebook session creation limit from 20 to 50 while keeping the session list endpoint default pagination at 20.

**Architecture:** Update the domain-level session limit constant, let the existing service-layer enforcement and API error payloads inherit the new value, and refresh any tests or route docstrings that explicitly encode the old ceiling. Do not change repository pagination defaults or request query defaults for listing sessions.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pytest

---

### Task 1: Lock In The New Limit Contract In Tests

**Files:**
- Modify: `newbee_notebook/tests/unit/test_chat_router_sse.py`
- Create or Modify: `newbee_notebook/tests/unit/application/services/test_session_service.py`

**Step 1: Write or update the failing chat-router assertions**

Update the limit-exceeded tests so they expect `max_count == 50` instead of `20`, while preserving the same `400 / E3001` contract shape.

**Step 2: Run the router tests to verify red**

Run: `uv run pytest newbee_notebook/tests/unit/test_chat_router_sse.py -q`

Expected: FAIL because the backend still reports a max session count of 20.

**Step 3: Add or update a service-level limit test**

Add a focused `SessionService.create()` test that verifies:
- creation succeeds when notebook count is below 50
- `SessionLimitExceededError.max_count == 50` when `count_by_notebook()` returns 50

**Step 4: Run the service test to verify red**

Run: `uv run pytest newbee_notebook/tests/unit/application/services/test_session_service.py -q`

Expected: FAIL because the service still uses the old domain limit.

**Step 5: Commit checkpoint**

```bash
git add newbee_notebook/tests/unit/test_chat_router_sse.py newbee_notebook/tests/unit/application/services/test_session_service.py
git commit -m "test(session): encode 50-session notebook limit"
```

### Task 2: Update Domain And Service Enforcement

**Files:**
- Modify: `newbee_notebook/domain/entities/notebook.py`
- Modify: `newbee_notebook/application/services/session_service.py`

**Step 1: Change the domain constant**

Update `MAX_SESSIONS_PER_NOTEBOOK` from `20` to `50`, and align the entity docstring comment so it no longer says “Up to 20 Sessions”.

**Step 2: Refresh service-facing documentation**

Update `SessionService` comments/docstrings that explicitly describe the old 20-session ceiling.

**Step 3: Run the focused tests to verify green**

Run:
- `uv run pytest newbee_notebook/tests/unit/application/services/test_session_service.py -q`
- `uv run pytest newbee_notebook/tests/unit/test_chat_router_sse.py -q`

Expected: PASS.

**Step 4: Commit checkpoint**

```bash
git add newbee_notebook/domain/entities/notebook.py newbee_notebook/application/services/session_service.py
git commit -m "feat(session): raise notebook session cap to 50"
```

### Task 3: Align API Contract Wording Without Changing Pagination

**Files:**
- Modify: `newbee_notebook/api/routers/sessions.py`
- Modify: `newbee_notebook/api/routers/chat.py`

**Step 1: Update sessions router descriptions**

Change the route docstring text that says “up to 20 sessions” and “max 20 per notebook” to 50.

**Step 2: Verify chat router needs no behavioral change**

Keep `_session_limit_detail()` and `SessionLimitExceededError` payload format unchanged. Only confirm it inherits the new `max_count` value automatically.

**Step 3: Confirm session list pagination default stays at 20**

Do not change:
- `list_sessions(limit: Query(20, ...))`
- any repository/service list defaults used for pagination

**Step 4: Run route-level verification**

Run: `uv run pytest newbee_notebook/tests/unit/test_chat_router_sse.py newbee_notebook/tests/unit/api/test_sessions_router.py -q`

Expected: PASS, with session-list endpoint semantics unchanged.

**Step 5: Commit checkpoint**

```bash
git add newbee_notebook/api/routers/sessions.py newbee_notebook/api/routers/chat.py
git commit -m "docs(api): align session limit wording with 50-session cap"
```

### Task 4: Run Final Backend Verification

**Files:**
- No code changes expected

**Step 1: Run targeted backend regression**

Run:
- `uv run pytest newbee_notebook/tests/unit/application/services/test_session_service.py -q`
- `uv run pytest newbee_notebook/tests/unit/test_chat_router_sse.py -q`
- `uv run pytest newbee_notebook/tests/unit/api/test_sessions_router.py -q`

Expected: PASS.

**Step 2: Run broader unit verification if the targeted suite is green**

Run: `uv run pytest newbee_notebook/tests/unit -q`

Expected: PASS.

**Step 3: Confirm worktree cleanliness before integration**

Run: `git status --short`

Expected: Only the intended backend/session-limit files are modified. Do not stage unrelated frontend work already present in this branch.

**Step 4: Final commit if any checkpoint commits were skipped**

```bash
git add <intended-files-only>
git commit -m "feat(session): raise notebook session cap to 50"
```
