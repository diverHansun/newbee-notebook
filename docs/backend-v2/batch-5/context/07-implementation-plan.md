# Context Compaction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement token-based main-track context compaction with persisted summary messages, boundary filtering, and additive API metadata so long-running sessions retain key semantics without leaking internal compaction messages into normal runtime behavior.

**Architecture:** Add a synchronous preflight `CompactionService` that runs inside `SessionManager` under the existing session lock before chat history is built. Persist each compaction as an internal `assistant` + `SUMMARY` message, advance `Session.compaction_boundary_id`, reload only boundary-visible main-track messages into `SessionMemory`, and expose additive `message_type` metadata through the backend API. Minimal frontend hiding of summary rows is intentionally left out of this backend plan and should be handled as a separate compatibility slice after the API contract is stable.

**Tech Stack:** Python 3, asyncio, SQLAlchemy async ORM, PostgreSQL init/migration SQL, tiktoken, pytest, React, TypeScript, Vitest.

---

### Task 0: Create The Dedicated Worktree And Branch

**Files:**
- Create: `.worktrees/batch-5-context/`

**Step 1: Create the isolated worktree from `stage/backend-v2`**

Run:

```bash
git worktree add .worktrees/batch-5-context -b codex/batch5-context-compaction stage/backend-v2
```

Expected: Git creates the new worktree and switches it to `codex/batch5-context-compaction`.

**Step 2: Enter the worktree and confirm the branch**

Run:

```bash
git -C .worktrees/batch-5-context status --short --branch
```

Expected: `## codex/batch5-context-compaction`

**Step 3: Use the new worktree for every remaining task**

Run:

```bash
git -C .worktrees/batch-5-context rev-parse --show-toplevel
```

Expected: the printed path ends with `.worktrees/batch-5-context`

**Step 4: Commit**

No commit yet. This task is only setup.

### Task 1: Lock In The Schema And Domain Contracts

**Files:**
- Create: `newbee_notebook/scripts/db/migrations/batch5_context_compaction.sql`
- Create: `newbee_notebook/tests/unit/core/context/test_context_compaction_contracts.py`
- Modify: `newbee_notebook/domain/value_objects/mode_type.py`
- Modify: `newbee_notebook/domain/entities/message.py`
- Modify: `newbee_notebook/domain/entities/session.py`
- Modify: `newbee_notebook/domain/repositories/message_repository.py`
- Modify: `newbee_notebook/domain/repositories/session_repository.py`
- Modify: `newbee_notebook/core/context/session_memory.py`
- Modify: `newbee_notebook/infrastructure/persistence/models.py`
- Modify: `newbee_notebook/infrastructure/persistence/repositories/message_repo_impl.py`
- Modify: `newbee_notebook/infrastructure/persistence/repositories/session_repo_impl.py`
- Modify: `newbee_notebook/infrastructure/persistence/database.py`
- Modify: `newbee_notebook/scripts/db/init-postgres.sql`

**Step 1: Write the failing contract tests**

Add tests that assert:

```python
assert Session().compaction_boundary_id is None
assert Message(message_type=MessageType.SUMMARY).message_type is MessageType.SUMMARY
assert StoredMessage(role="assistant", content="x", mode="agent", message_type="summary").message_type == "summary"
assert "compaction_boundary_id" in SessionModel.__table__.columns
assert "message_type" in MessageModel.__table__.columns
assert migration_path.exists()
```

Do not add SQL text substring assertions for batch-5 fields.

**Step 2: Run the targeted tests and confirm they fail for the missing contracts**

Run:

```bash
.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/context/test_context_compaction_contracts.py -v
```

Expected: FAIL because the new entity defaults, `StoredMessage.message_type`, ORM fields, and migration file do not exist yet.

**Step 3: Implement the additive schema and domain changes**

Implement these exact contract changes:

```python
class MessageType(str, Enum):
    NORMAL = "normal"
    SUMMARY = "summary"
```

```python
@dataclass
class Message(Entity):
    ...
    message_type: MessageType = MessageType.NORMAL
```

```python
@dataclass
class Session(Entity):
    ...
    compaction_boundary_id: int | None = None
```

Repository additions:

```python
async def list_after_boundary(session_id: str, boundary_message_id: int | None, track_modes: list[ModeType] | None = None) -> list[Message]: ...
async def update_compaction_boundary(session_id: str, compaction_boundary_id: int | None) -> None: ...
```

Implementation rules:
- Remove `context_summary`, `needs_compression`, the `round_count` property, and `update_context_summary` from the runtime domain/API surface.
- Keep existing database `context_summary` columns in old deployments untouched if already present; do not add destructive drop statements in runtime migration code.
- Add `StoredMessage.message_type` in this task, not later.
- Do not increment `session.message_count` for `SUMMARY` messages.

**Step 4: Re-run the targeted tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/context/test_context_compaction_contracts.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/domain/value_objects/mode_type.py newbee_notebook/domain/entities/message.py newbee_notebook/domain/entities/session.py newbee_notebook/domain/repositories/message_repository.py newbee_notebook/domain/repositories/session_repository.py newbee_notebook/core/context/session_memory.py newbee_notebook/infrastructure/persistence/models.py newbee_notebook/infrastructure/persistence/repositories/message_repo_impl.py newbee_notebook/infrastructure/persistence/repositories/session_repo_impl.py newbee_notebook/infrastructure/persistence/database.py newbee_notebook/scripts/db/init-postgres.sql newbee_notebook/scripts/db/migrations/batch5_context_compaction.sql newbee_notebook/tests/unit/core/context/test_context_compaction_contracts.py
git commit -m "feat(context): add compaction schema contracts"
```

### Task 2: Replace Word-Based Token Logic With Tiktoken-Based Budgeting

**Files:**
- Create: `newbee_notebook/tests/unit/core/context/test_token_counter.py`
- Create: `newbee_notebook/tests/unit/core/context/test_compressor.py`
- Modify: `newbee_notebook/core/context/token_counter.py`
- Modify: `newbee_notebook/core/context/compressor.py`
- Modify: `newbee_notebook/core/context/budget.py`
- Modify: `newbee_notebook/tests/unit/core/context/test_context_builder.py`

**Note:** `tiktoken==0.12.0` is already pinned in `pyproject.toml`, so this task should use the existing dependency rather than adding a new one.

**Step 1: Write the failing token and budget tests**

Add tests that cover:

```python
assert counter.count("中英 mixed text") == len(encoding.encode("中英 mixed text"))
assert counter.count("") == 0
assert counter.count_messages([{"role": "user", "content": "hello"}]) > counter.count("hello")
assert budget.compaction_threshold == int(budget.total * 0.95)
assert compressor.truncate(long_text, max_tokens=8)
```

Also update `test_context_builder.py` only as needed to keep its fake/stub counter deterministic while passing the new `StoredMessage.message_type` field through helper constructors.

**Step 2: Run the new context tests and confirm they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/context/test_token_counter.py newbee_notebook/tests/unit/core/context/test_compressor.py newbee_notebook/tests/unit/core/context/test_context_builder.py -v
```

Expected: FAIL because the current implementation still splits on whitespace.

**Step 3: Implement token-safe counting and truncation**

Implementation rules:
- Use `tiktoken.get_encoding("cl100k_base")`.
- Count message lists with fixed per-message overhead plus content tokens.
- Truncate by encoded token ids and decode back to text.
- Add `summary` to `ContextBudget`.
- Add `compaction_threshold` to `ContextBudget`.
- Keep `ContextBudget` injectable so `SessionManager` no longer hardcodes budget constants inline.

**Step 4: Re-run the context tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/context/test_token_counter.py newbee_notebook/tests/unit/core/context/test_compressor.py newbee_notebook/tests/unit/core/context/test_context_builder.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/context/token_counter.py newbee_notebook/core/context/compressor.py newbee_notebook/core/context/budget.py newbee_notebook/tests/unit/core/context/test_token_counter.py newbee_notebook/tests/unit/core/context/test_compressor.py newbee_notebook/tests/unit/core/context/test_context_builder.py
git commit -m "feat(context): adopt token-based budgeting"
```

### Task 3: Implement The Compaction Service And Prompt

**Files:**
- Create: `newbee_notebook/core/context/compaction_prompt.py`
- Create: `newbee_notebook/core/context/compaction_service.py`
- Create: `newbee_notebook/tests/unit/core/context/test_compaction_service.py`
- Modify: `newbee_notebook/core/context/__init__.py`

**Step 1: Write the failing compaction service tests**

Add tests for:

```python
assert await service.compact_if_needed(session, track_modes=[ModeType.AGENT, ModeType.ASK]) is False
assert created_summary.message_type is MessageType.SUMMARY
assert updated_boundary == created_summary.message_id
assert old_summary_still_exists is True
assert persisted_summary_token_count <= budget.summary
assert await service.compact_if_needed(session, track_modes=[...]) is False  # when llm raises
```

**Step 2: Run the new service tests and confirm they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/context/test_compaction_service.py -v
```

Expected: FAIL because the service and prompt do not exist yet.

**Step 3: Implement the service**

Implementation rules:
- `compact_if_needed()` loads main-track messages via `list_after_boundary()`.
- Empty message sets return `False`.
- Below-threshold sessions return `False` and do not touch the repositories.
- The LLM request uses `tools=None`, `tool_choice=None`, `disable_thinking=True`, and `max_tokens=budget.summary`.
- Call `LLMClient.chat(..., disable_thinking=True)` directly; this is already supported by the runtime client and only becomes provider-specific `extra_body` for providers that need it.
- The summary prompt must preserve decisions, facts, unresolved questions, and user preferences.
- LLM failures return `False` without mutating session state.
- LLM failures also record a `logger.warning` entry with the session id and boundary state.
- Overlong summaries are truncated through `Compressor`.

**Step 4: Re-run the service tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/context/test_compaction_service.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/context/compaction_prompt.py newbee_notebook/core/context/compaction_service.py newbee_notebook/core/context/__init__.py newbee_notebook/tests/unit/core/context/test_compaction_service.py
git commit -m "feat(context): add compaction service"
```

### Task 4: Rewire Session Memory And SessionManager Around The Boundary

**Files:**
- Modify: `newbee_notebook/core/context/context_builder.py`
- Modify: `newbee_notebook/core/session/session_manager.py`
- Modify: `newbee_notebook/core/llm/config.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Test: `newbee_notebook/tests/unit/core/session/test_session_manager.py`

**Step 1: Write the failing session-manager integration tests**

Add tests that assert:

```python
assert compaction_service.compact_if_needed.await_count == 1
assert message_repo.list_after_boundary.await_count == 1
assert message_repo.list_by_session.await_count == 1  # side track only
assert chat_history[1] == {"role": "assistant", "content": "compacted summary"}
assert budget.total == expected_context_window
```

Also assert the lock encloses compaction + reload + history build, not only `AgentLoop.stream()`.

**Step 2: Run the session/context tests and confirm they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/session/test_session_manager.py -v
```

Expected: FAIL because `SessionManager` still reloads main history with `list_by_session(limit=50)`, constructs budgets inline, and holds the lock too late in the flow.

**Step 3: Implement the runtime integration**

Implementation rules:
- `SessionManager.chat_stream()` acquires the session lock before compaction, memory reload, history build, loop creation, and streaming.
- Main-track reload uses `message_repo.list_after_boundary(session_id, session.compaction_boundary_id, track_modes=MAIN_TRACK_MODES)`.
- Side-track reload remains capped at 12 messages and is never compacted.
- `ContextBuilder` stays a pure assembler and remains unaware of compaction decisions.
- `ContextBudget` is constructed in dependency injection from a new helper that resolves the active model context window from `LLMRuntimeConfig.provider` + `LLMRuntimeConfig.model`, reusing the existing Qwen and Zhipu window mappings/fallbacks and adding an OpenAI fallback map where needed.
- Do not derive `budget.total` from `LLMRuntimeConfig.max_tokens`; that field is the generation cap, not the model context window.
- `list_after_boundary(..., boundary=None)` is intentionally unbounded for the main track because compaction correctness depends on the full visible chain. For this batch we accept the full load and rely on `ContextBuilder` token fitting after reload.

**Step 4: Re-run the session/context tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/session/test_session_manager.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/context/context_builder.py newbee_notebook/core/session/session_manager.py newbee_notebook/core/llm/config.py newbee_notebook/api/dependencies.py newbee_notebook/tests/unit/core/session/test_session_manager.py
git commit -m "feat(session): load boundary-filtered context"
```

### Task 5: Expose `message_type` Through The Backend API

**Files:**
- Create: `newbee_notebook/tests/unit/test_sessions_router.py`
- Modify: `newbee_notebook/api/models/responses.py`
- Modify: `newbee_notebook/api/routers/sessions.py`

**Step 1: Write the failing API tests**

Expectation:

```python
assert response.data[0].message_type == "summary"
```

**Step 2: Run the targeted tests and confirm they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/test_sessions_router.py -v
```

Expected: FAIL because the backend does not expose `message_type`.

**Step 3: Implement the additive API contract**

Implementation rules:
- `GET /sessions/{session_id}/messages` still returns summary rows by default.
- `MessageResponse` adds an additive `message_type` field.
- This task stops at the backend/API boundary. UI hiding of summary rows should be handled by a separate minimal frontend compatibility plan after the backend contract is stable.

**Step 4: Re-run the targeted tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/test_sessions_router.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/api/models/responses.py newbee_notebook/api/routers/sessions.py newbee_notebook/tests/unit/test_sessions_router.py
git commit -m "feat(api): expose compacted message metadata"
```

### Task 6: Run The Verification Matrix And Prepare The Merge

**Files:**
- Modify: `docs/backend-v2/batch-5/context/README.md`

**Step 1: Add the batch-5 rollout note to the local README**

Document:
- the new `SUMMARY` internal message contract
- the non-destructive migration behavior for old `context_summary` columns
- the fact that side-track messages are excluded from compaction

**Step 2: Run the full targeted verification suite**

Run:

```bash
.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/context/test_context_compaction_contracts.py newbee_notebook/tests/unit/core/context/test_token_counter.py newbee_notebook/tests/unit/core/context/test_compressor.py newbee_notebook/tests/unit/core/context/test_compaction_service.py newbee_notebook/tests/unit/core/context/test_session_memory.py newbee_notebook/tests/unit/core/session/test_session_manager.py newbee_notebook/tests/unit/test_sessions_router.py -v
```

Expected: all PASS

**Step 3: Run the manual functional smoke test**

Checklist:
- create a long-running session
- trigger compaction once
- confirm old main-track rows are hidden from runtime context
- confirm `GET /sessions/{id}/messages` still returns the `SUMMARY` row

**Step 4: Rebase or merge-base check before merging**

Run:

```bash
git fetch origin
git rebase origin/stage/backend-v2
```

Expected: branch is replayed cleanly on the latest `origin/stage/backend-v2`, or conflicts are resolved before merge.

**Step 5: Merge the temporary branch back into `stage/backend-v2`**

Run:

```bash
git checkout stage/backend-v2
git merge --no-ff codex/batch5-context-compaction
```

Expected: merge succeeds after tests are green

**Step 6: Commit**

If README changed in this task:

```bash
git add docs/backend-v2/batch-5/context/README.md
git commit -m "docs(context): record batch5 rollout notes"
```
