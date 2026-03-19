# Batch-3 Notes & Marks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete batch-3 backend/frontend slice for marks, notes, `/note` skill activation, and confirmation flow, with a minimal but real automated test baseline and Playwright-assisted manual verification.

**Architecture:** Start from the backend contracts that can block everything else: migration, entities, repositories, services, REST, skill runtime, and confirmation gateway. Once those runtime contracts are stable, attach the frontend in three thin slices: reader marks, Studio notes/marks, and chat slash/confirmation interactions. Keep batch-3 intentionally narrow: no diagram work, no rich note preview mode, no extra REST for `note_mark_refs`, and only minimal frontend unit tests.

**Tech Stack:** FastAPI, SQLAlchemy/async persistence, dataclass domain entities, existing batch-2 `AgentLoop` runtime, Zustand, TanStack Query, Next.js 15, React 19, TypeScript, Vitest, Playwright MCP for manual verification.

---

## Working Rules

- Execute this plan in a dedicated worktree: `.worktrees/batch-3` on branch `feat/backend-v2-batch-3`.
- Use TDD for service/runtime/frontend logic. Migration/DDL steps can use smoke verification instead of strict Red-Green.
- Use the already-aligned contracts from `docs/backend-v2/batch-3/` and do not reintroduce old names such as `comment`, `/chat/confirm`, `notes-marks`, or flat `/marks?document_id=...` APIs.
- Backend verification uses `.\.venv\Scripts\python.exe -m pytest ...` from repo root.
- Frontend verification uses `pnpm --dir frontend ...`.
- Frontend testing target for batch-3 is A-tier only: minimal Vitest coverage for pure logic and one or two key components/hooks; the main regression pass is manual verification with Playwright against the running backend/frontend.

## Execution Preconditions

1. Create the worktree before touching code:

```powershell
git worktree add .worktrees/batch-3 -b feat/backend-v2-batch-3
```

2. Verify baseline runtime before implementation:

```powershell
git status --short
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\test_chat_service_guards.py newbee_notebook\tests\unit\test_chat_router_sse.py -v
pnpm --dir frontend typecheck
```

3. Keep the existing backend Docker stack running and start frontend dev server only when frontend work begins:

```powershell
pnpm --dir frontend dev -p 3001
```

## Scope Lock

- In scope:
  - `marks`, `notes`, `note_document_tags`, `note_mark_refs`
  - nested marks/notes REST APIs
  - `SkillRegistry`, `SkillManifest`, `ConfirmationGateway`, `/note`
  - reader mark creation and rendering
  - Studio notes/marks list + note editor
  - chat slash selector and inline confirmation card
- Out of scope:
  - diagram/mindmap work
  - rich note preview renderer
  - collaborative editing
  - separate note-mark write endpoints
  - broad frontend test suite beyond minimal logic/component coverage

### Task 1: Add Schema and Persistence Models

**Files:**
- Create: `newbee_notebook/scripts/db/migrations/batch3_notes_marks.sql`
- Modify: `newbee_notebook/infrastructure/persistence/models.py`
- Test: `newbee_notebook/tests/unit/test_db_init_script.py`

**Step 1: Write the migration SQL**

```sql
CREATE TABLE marks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    anchor_text TEXT NOT NULL,
    char_offset INTEGER NOT NULL CHECK (char_offset >= 0),
    context_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Add the other three tables in the same file with the aligned contracts:
- `notes(id, title default '', content default '')`
- `note_document_tags(id, note_id, document_id, UNIQUE(note_id, document_id))`
- `note_mark_refs(id, note_id, mark_id, UNIQUE(note_id, mark_id))`

**Step 2: Mirror the schema in SQLAlchemy models**

Add `MarkModel`, `NoteModel`, `NoteDocumentTagModel`, and `NoteMarkRefModel` in `models.py`, following the existing declarative style and using `id` as the DB primary key while keeping relationship fields simple.

**Step 3: Run schema smoke verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\test_db_init_script.py -v
```

Expected: PASS, with no metadata/DDL regressions.

**Step 4: Apply the migration in the dev database**

Run the project’s standard migration/apply flow for SQL scripts and verify the 4 new tables exist. Record any environment-specific command adjustments in the commit notes if the apply path differs locally.

**Step 5: Commit**

```powershell
git add newbee_notebook/scripts/db/migrations/batch3_notes_marks.sql newbee_notebook/infrastructure/persistence/models.py
git commit -m "feat(batch3-db): add notes and marks schema"
```

### Task 2: Implement Mark Domain, Repository, and Service

**Files:**
- Create: `newbee_notebook/domain/entities/mark.py`
- Create: `newbee_notebook/domain/repositories/mark_repository.py`
- Create: `newbee_notebook/infrastructure/persistence/repositories/mark_repo_impl.py`
- Create: `newbee_notebook/application/services/mark_service.py`
- Create: `newbee_notebook/tests/unit/test_mark_service.py`

**Step 1: Write the failing service tests**

```python
async def test_create_mark_returns_saved_entity(service, repo):
    repo.save.return_value = Mark(mark_id="m1", document_id="d1", anchor_text="abc", char_offset=12)
    result = await service.create_mark("d1", "abc", 12)
    assert result.mark_id == "m1"

async def test_delete_mark_raises_for_missing_mark(service, repo):
    repo.find_by_id.return_value = None
    with pytest.raises(MarkNotFoundError):
        await service.delete_mark("missing")
```

**Step 2: Run the tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\test_mark_service.py -v
```

Expected: FAIL because `MarkService`/`Mark` are not complete yet.

**Step 3: Write the minimal implementation**

Implement:
- `Mark` dataclass with `mark_id`, `document_id`, `anchor_text`, `char_offset`, `context_text`
- `MarkRepository` protocol
- `PostgresMarkRepository.save/find_by_id/find_by_document/delete`
- `MarkService.create_mark/list_marks/get_mark/delete_mark`

Repository mapping rule:

```python
Mark(
    mark_id=str(row.id),
    document_id=str(row.document_id),
    anchor_text=row.anchor_text,
    char_offset=row.char_offset,
    context_text=row.context_text,
)
```

**Step 4: Run the focused tests again**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\test_mark_service.py -v
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add newbee_notebook/domain/entities/mark.py newbee_notebook/domain/repositories/mark_repository.py newbee_notebook/infrastructure/persistence/repositories/mark_repo_impl.py newbee_notebook/application/services/mark_service.py newbee_notebook/tests/unit/test_mark_service.py
git commit -m "feat(batch3-mark): add mark domain and service"
```

### Task 3: Implement Note Domain, Repository, and Service

**Files:**
- Create: `newbee_notebook/domain/entities/note.py`
- Create: `newbee_notebook/domain/repositories/note_repository.py`
- Create: `newbee_notebook/infrastructure/persistence/repositories/note_repo_impl.py`
- Create: `newbee_notebook/application/services/note_service.py`
- Create: `newbee_notebook/tests/unit/test_note_service.py`

**Step 1: Write failing note service tests**

```python
async def test_update_note_syncs_mark_refs(service, note_repo, mark_repo):
    note_repo.find_by_id.return_value = Note(note_id="n1", title="", content="See [[mark:m1]]")
    note_repo.update_content.return_value = Note(note_id="n1", title="T", content="See [[mark:m1]]")
    await service.update_note("n1", title="T", content="See [[mark:m1]]")
    note_repo.sync_mark_refs.assert_called_once_with("n1", ["m1"])

async def test_list_notes_scopes_to_notebook(service, note_repo, mark_repo):
    note_repo.find_by_notebook.return_value = []
    result = await service.list_notes("nb1")
    assert result == []
```

**Step 2: Run the tests to confirm failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\test_note_service.py -v
```

Expected: FAIL.

**Step 3: Implement minimal note backend**

Implement:
- `Note` dataclass
- `NoteRepository` protocol
- `PostgresNoteRepository.find_by_notebook/update_content/add_document_tag/remove_document_tag/sync_mark_refs/delete`
- `NoteService` with regex-based extraction for `[[mark:<id>]]`

Reference extraction:

```python
MARK_REF_PATTERN = re.compile(r"\[\[mark:([A-Za-z0-9-]+)\]\]")
mark_ids = list(dict.fromkeys(MARK_REF_PATTERN.findall(content)))
```

**Step 4: Re-run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\test_note_service.py -v
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add newbee_notebook/domain/entities/note.py newbee_notebook/domain/repositories/note_repository.py newbee_notebook/infrastructure/persistence/repositories/note_repo_impl.py newbee_notebook/application/services/note_service.py newbee_notebook/tests/unit/test_note_service.py
git commit -m "feat(batch3-note): add note domain and service"
```

### Task 4: Add Notes and Marks REST APIs

**Files:**
- Create: `newbee_notebook/api/models/mark_models.py`
- Create: `newbee_notebook/api/models/note_models.py`
- Create: `newbee_notebook/api/routers/marks.py`
- Create: `newbee_notebook/api/routers/notes.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Modify: `main.py`
- Test: `newbee_notebook/tests/unit/test_marks_router.py`
- Test: `newbee_notebook/tests/unit/test_notes_router.py`

**Step 1: Write failing router tests**

Cover at least:
- `POST /api/v1/documents/{document_id}/marks`
- `GET /api/v1/documents/{document_id}/marks`
- `GET /api/v1/notebooks/{notebook_id}/notes`
- `PATCH /api/v1/notes/{note_id}`

Example:

```python
def test_create_mark_returns_201(client, override_mark_service):
    response = client.post("/api/v1/documents/doc-1/marks", json={"anchor_text": "abc", "char_offset": 1})
    assert response.status_code == 201
    assert response.json()["mark_id"]
```

**Step 2: Run the router tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\test_marks_router.py newbee_notebook\tests\unit\test_notes_router.py -v
```

Expected: FAIL.

**Step 3: Implement the APIs and DI wiring**

Expose only the aligned routes:
- `POST/GET /api/v1/documents/{document_id}/marks`
- `GET /api/v1/notebooks/{notebook_id}/marks`
- `DELETE /api/v1/marks/{mark_id}`
- `POST /api/v1/notes`
- `GET /api/v1/notebooks/{notebook_id}/notes`
- `GET /api/v1/notes/{note_id}`
- `PATCH /api/v1/notes/{note_id}`
- `DELETE /api/v1/notes/{note_id}`
- `POST/DELETE /api/v1/notes/{note_id}/documents`

**Step 4: Re-run the API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\test_marks_router.py newbee_notebook\tests\unit\test_notes_router.py -v
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add newbee_notebook/api/models/mark_models.py newbee_notebook/api/models/note_models.py newbee_notebook/api/routers/marks.py newbee_notebook/api/routers/notes.py newbee_notebook/api/dependencies.py main.py newbee_notebook/tests/unit/test_marks_router.py newbee_notebook/tests/unit/test_notes_router.py
git commit -m "feat(batch3-api): add notes and marks endpoints"
```

### Task 5: Add Skill Contracts and Registry

**Files:**
- Create: `newbee_notebook/core/skills/__init__.py`
- Create: `newbee_notebook/core/skills/contracts.py`
- Create: `newbee_notebook/core/skills/registry.py`
- Create: `newbee_notebook/tests/unit/core/skills/test_skill_registry.py`

**Step 1: Write failing SkillRegistry tests**

```python
def test_match_command_returns_provider_and_cleaned_message(registry, provider):
    registry.register(provider)
    provider, activated_command, cleaned = registry.match_command("/note hello")
    assert activated_command == "/note"
    assert cleaned == "hello"

def test_match_command_is_case_sensitive(registry, provider):
    registry.register(provider)
    assert registry.match_command("/NOTE hello") is None
```

**Step 2: Run the tests and confirm failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\core\skills\test_skill_registry.py -v
```

Expected: FAIL.

**Step 3: Implement contracts and registry**

Important contracts:

```python
@dataclass(frozen=True)
class SkillContext:
    notebook_id: str
    activated_command: str
    selected_document_ids: list[str] = field(default_factory=list)
```

`match_command()` must return `(provider, activated_command, cleaned_message)` and remain case-sensitive.

**Step 4: Re-run the tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\core\skills\test_skill_registry.py -v
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add newbee_notebook/core/skills/__init__.py newbee_notebook/core/skills/contracts.py newbee_notebook/core/skills/registry.py newbee_notebook/tests/unit/core/skills/test_skill_registry.py
git commit -m "feat(batch3-skill): add skill contracts and registry"
```

### Task 6: Add Confirmation Runtime and Chat Integration

**Files:**
- Create: `newbee_notebook/core/engine/confirmation.py`
- Modify: `newbee_notebook/core/engine/stream_events.py`
- Modify: `newbee_notebook/core/engine/agent_loop.py`
- Modify: `newbee_notebook/core/session/session_manager.py`
- Modify: `newbee_notebook/application/services/chat_service.py`
- Modify: `newbee_notebook/api/routers/chat.py`
- Create: `newbee_notebook/api/models/confirm_models.py`
- Test: `newbee_notebook/tests/unit/core/engine/test_agent_loop_confirmation.py`
- Test: `newbee_notebook/tests/unit/core/session/test_session_manager.py`
- Test: `newbee_notebook/tests/unit/test_chat_router_sse.py`
- Test: `newbee_notebook/tests/unit/test_chat_service_guards.py`

**Step 1: Write the failing confirmation tests**

Cover:
- `ConfirmationRequestEvent` is yielded before protected tool execution
- `ConfirmationGateway.wait()` resolves/timeout paths
- `POST /api/v1/chat/{session_id}/confirm` returns 200 or 404
- `ChatService.chat_stream()` forces `agent` mode for `/note`

**Step 2: Run the focused runtime tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\core\engine\test_agent_loop.py newbee_notebook\tests\unit\core\session\test_session_manager.py newbee_notebook\tests\unit\test_chat_service_guards.py newbee_notebook\tests\unit\test_chat_router_sse.py -v
```

Expected: FAIL in new confirmation-specific cases.

**Step 3: Implement the runtime plumbing**

Key changes:
- add `ConfirmationRequestEvent(event="confirmation_request")`
- add `ConfirmationGateway.create/wait/resolve`
- thread `external_tools`, `system_prompt_addition`, `confirmation_required`, and `confirmation_gateway` through `SessionManager`
- in `ChatService.chat_stream()`, detect slash command, build `SkillContext`, force `agent` mode, and pass the manifest extras
- add `POST /api/v1/chat/{session_id}/confirm`

Safe summary shape:

```python
args_summary = {k: v for k, v in effective_arguments.items() if k not in {"content"}}
```

**Step 4: Re-run the runtime tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\core\engine\test_agent_loop.py newbee_notebook\tests\unit\core\session\test_session_manager.py newbee_notebook\tests\unit\test_chat_service_guards.py newbee_notebook\tests\unit\test_chat_router_sse.py -v
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add newbee_notebook/core/engine/confirmation.py newbee_notebook/core/engine/stream_events.py newbee_notebook/core/engine/agent_loop.py newbee_notebook/core/session/session_manager.py newbee_notebook/application/services/chat_service.py newbee_notebook/api/routers/chat.py newbee_notebook/api/models/confirm_models.py newbee_notebook/tests/unit/core/engine newbee_notebook/tests/unit/core/session/test_session_manager.py newbee_notebook/tests/unit/test_chat_service_guards.py newbee_notebook/tests/unit/test_chat_router_sse.py
git commit -m "feat(batch3-confirm): add confirmation runtime and chat integration"
```

### Task 7: Implement `/note` Skill Tools and Provider

**Files:**
- Create: `newbee_notebook/skills/note/__init__.py`
- Create: `newbee_notebook/skills/note/tools.py`
- Create: `newbee_notebook/skills/note/provider.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Test: `newbee_notebook/tests/unit/skills/note/test_tools.py`

**Step 1: Write failing tool tests**

```python
async def test_list_notes_tool_returns_json(mock_note_service):
    tool = build_list_notes_tool(mock_note_service, notebook_id="nb1")
    mock_note_service.list_notes.return_value = []
    result = await tool.execute({})
    assert json.loads(result.content) == []

async def test_update_note_tool_surfaces_error(mock_note_service):
    mock_note_service.update_note.side_effect = NoteNotFoundError("n404")
    tool = build_update_note_tool(mock_note_service)
    result = await tool.execute({"note_id": "n404", "title": "x"})
    assert result.error is not None
```

**Step 2: Run the skill tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\skills\note\test_tools.py -v
```

Expected: FAIL.

**Step 3: Implement minimal note skill surface**

Create only these tools:
- `list_notes`
- `read_note`
- `create_note`
- `update_note`
- `delete_note`
- `list_marks`
- `associate_note_document`
- `disassociate_note_document`

Provider manifest:

```python
SkillManifest(
    name="note",
    slash_command="/note",
    description="notes and marks skill",
    system_prompt_addition="当前已激活 /note ...",
    tools=self._build_tools(context),
    confirmation_required=frozenset({"update_note", "delete_note", "disassociate_note_document"}),
)
```

**Step 4: Re-run the tests and do one smoke run**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\skills\note\test_tools.py -v
```

Then do one manual backend smoke call for `/note` after wiring registration.

**Step 5: Commit**

```powershell
git add newbee_notebook/skills/note newbee_notebook/api/dependencies.py newbee_notebook/tests/unit/skills/note/test_tools.py
git commit -m "feat(batch3-note-skill): add note skill tools and provider"
```

### Task 8: Add Frontend Test Baseline, Types, API Clients, and Hooks

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/types/mark.ts`
- Create: `frontend/src/types/note.ts`
- Create: `frontend/src/lib/api/marks.ts`
- Create: `frontend/src/lib/api/notes.ts`
- Modify: `frontend/src/lib/api/chat.ts`
- Create: `frontend/src/lib/hooks/use-marks.ts`
- Create: `frontend/src/lib/hooks/use-notes.ts`
- Modify: `frontend/src/lib/i18n/strings.ts`
- Test: `frontend/src/lib/reader/mark-offset.test.ts`

**Step 1: Add the minimal frontend test tooling**

Install:

```powershell
pnpm --dir frontend add -D vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

Add script:

```json
"test": "vitest run"
```

**Step 2: Create failing pure-logic test**

Create `mark-offset.test.ts`:

```typescript
it("returns null when anchor is not found", () => {
  expect(computeCharOffset("abc", "zzz", 0)).toBeNull();
});
```

Run:

```powershell
pnpm --dir frontend test
```

Expected: FAIL because helper/config are missing.

**Step 3: Implement the baseline**

Add:
- Vitest config and setup
- aligned TS types using `context_text`, `argsSummary`
- notes/marks API clients
- TanStack hooks with query keys
- `confirmAction()` hitting `/chat/${sessionId}/confirm`

**Step 4: Re-run frontend baseline checks**

Run:

```powershell
pnpm --dir frontend test
pnpm --dir frontend typecheck
```

Expected: PASS for the new minimal baseline.

**Step 5: Commit**

```powershell
git add frontend/package.json frontend/vitest.config.ts frontend/src/test/setup.ts frontend/src/types frontend/src/lib/api frontend/src/lib/hooks frontend/src/lib/i18n/strings.ts frontend/src/lib/reader/mark-offset.test.ts
git commit -m "feat(batch3-frontend): add notes frontend baseline"
```

### Task 9: Integrate Reader Bookmark Creation and Mark Rendering

**Files:**
- Modify: `frontend/src/components/reader/selection-menu.tsx`
- Modify: `frontend/src/components/reader/document-reader.tsx`
- Modify: `frontend/src/components/reader/markdown-viewer.tsx`
- Create: `frontend/src/lib/reader/mark-offset.ts`
- Create: `frontend/src/lib/reader/apply-mark-highlights.ts`
- Modify: `frontend/src/stores/reader-store.ts`
- Test: `frontend/src/lib/reader/mark-offset.test.ts`

**Step 1: Extend the failing logic test**

Add:

```typescript
it("adds chunk start offset to the found index", () => {
  expect(computeCharOffset("hello world", "world", 50)).toBe(56);
});
```

**Step 2: Run the test to verify failure**

Run:

```powershell
pnpm --dir frontend test
```

Expected: FAIL if helper is not implemented.

**Step 3: Implement the reader slice**

Wire:
- `SelectionMenu.onMark`
- `DocumentReader` create mark mutation
- `MarkdownViewer` mark decoration per chunk
- `reader-store` or existing reader state for active mark navigation

Rendering rule:
- no inline text mutation
- add margin icon/highlight at the closest block containing the mark

**Step 4: Re-run logic tests and typecheck**

Run:

```powershell
pnpm --dir frontend test
pnpm --dir frontend typecheck
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add frontend/src/components/reader frontend/src/lib/reader frontend/src/stores/reader-store.ts
git commit -m "feat(batch3-reader): add bookmark creation and rendering"
```

### Task 10: Build Studio Notes & Marks UI

**Files:**
- Modify: `frontend/src/components/studio/studio-panel.tsx`
- Create: `frontend/src/stores/studio-store.ts`
- Create: `frontend/src/components/studio/notes/note-list-view.tsx`
- Create: `frontend/src/components/studio/notes/note-editor.tsx`
- Create: `frontend/src/components/studio/notes/marks-section.tsx`
- Create: `frontend/src/components/studio/notes/mark-inline-picker.tsx`
- Create: `frontend/src/lib/notes/render-mark-refs.ts`

**Step 1: Write one minimal component test**

Test target: `MarkInlinePicker` keyboard selection or `render-mark-refs` pure transform. Keep only one or two tests in batch-3.

Example:

```typescript
it("replaces [[mark:id]] with a pill span", () => {
  const html = renderMarkRefs("See [[mark:m1]]", [{ mark_id: "m1", anchor_text: "anchor", document_id: "d1", char_offset: 1, context_text: null, created_at: "", updated_at: "" }]);
  expect(html).toContain("mark-ref-pill");
});
```

**Step 2: Run the component/pure logic test**

Run:

```powershell
pnpm --dir frontend test
```

Expected: FAIL before implementation.

**Step 3: Implement the Studio slice**

Build:
- `studio-store` with `home | notes | note-detail`
- card-based `studio-panel`
- note list
- note editor
- associated document tags
- `[[` picker
- available marks insert section

Do not add rich preview mode; keep editor as `textarea`.

**Step 4: Re-run tests and typecheck**

Run:

```powershell
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend lint
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add frontend/src/components/studio frontend/src/stores/studio-store.ts frontend/src/lib/notes
git commit -m "feat(batch3-studio): add notes and marks studio views"
```

### Task 11: Add Chat Slash Selector and Confirmation Card

**Files:**
- Modify: `frontend/src/components/chat/chat-input.tsx`
- Modify: `frontend/src/components/chat/chat-panel.tsx`
- Modify: `frontend/src/components/chat/message-item.tsx`
- Create: `frontend/src/components/chat/slash-command-selector.tsx`
- Create: `frontend/src/components/chat/confirmation-card.tsx`
- Modify: `frontend/src/lib/hooks/useChatSession.ts`
- Modify: `frontend/src/lib/hooks/useChatStream.ts`
- Modify: `frontend/src/stores/chat-store.ts`

**Step 1: Write one focused UI test**

Choose one:
- slash selector filtering
- confirmation card state transition rendering

Example:

```typescript
it("shows /note and filters by typed prefix", async () => {
  render(<SlashCommandSelector input="/n" onSelect={vi.fn()} onDismiss={vi.fn()} />);
  expect(screen.getByText("/note")).toBeInTheDocument();
});
```

**Step 2: Run the test to verify failure**

Run:

```powershell
pnpm --dir frontend test
```

Expected: FAIL.

**Step 3: Implement chat UI plumbing**

Add:
- slash selector in `chat-input.tsx`
- `pendingConfirmation` shape with `argsSummary`
- `confirmation_request` event handling in `useChatSession`
- inline `ConfirmationCard`
- confirm API call and optimistic state update

**Step 4: Re-run tests and static checks**

Run:

```powershell
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend lint
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add frontend/src/components/chat frontend/src/lib/hooks/useChatSession.ts frontend/src/lib/hooks/useChatStream.ts frontend/src/stores/chat-store.ts
git commit -m "feat(batch3-chat): add slash and confirmation UI"
```

### Task 12: Verify End-to-End with Playwright and Finalize

**Files:**
- Modify: any files fixed during verification

**Step 1: Run focused backend checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\test_mark_service.py newbee_notebook\tests\unit\test_note_service.py newbee_notebook\tests\unit\test_marks_router.py newbee_notebook\tests\unit\test_notes_router.py newbee_notebook\tests\unit\test_chat_service_guards.py newbee_notebook\tests\unit\test_chat_router_sse.py newbee_notebook\tests\unit\core\engine\test_agent_loop.py newbee_notebook\tests\unit\core\session\test_session_manager.py newbee_notebook\tests\unit\core\skills\test_skill_registry.py newbee_notebook\tests\unit\skills\note\test_tools.py -v
```

Expected: PASS.

**Step 2: Run frontend checks**

Run:

```powershell
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend lint
```

Expected: PASS.

**Step 3: Manual verification with running services**

Use Playwright MCP against:
- backend Docker services already running
- frontend dev server on `http://localhost:3001`

Manual checklist:
- open a converted document, select text, create a mark
- verify mark re-renders in reader margin
- open Studio, create note, insert `[[mark:id]]`, save
- send `/note 列出所有笔记`
- send one destructive `/note` action and verify confirmation card

**Step 4: Fix any verification fallout and re-run targeted checks**

Only re-run the failing subset plus one final smoke path in browser.

**Step 5: Final commit**

```powershell
git add .
git commit -m "feat(batch3): complete notes, marks, and note skill"
```

## Handoff Notes

- If any task forces diagram-related code or Mermaid dependencies, stop. That belongs to batch-4.
- If frontend test setup starts growing beyond Vitest + one or two key component tests, stop and re-scope. Batch-3 only needs the minimal complete loop.
- If `AgentLoop` confirmation touches generic streaming behavior, extend existing unit tests rather than inventing a parallel runtime harness.

Plan complete and saved to `docs/backend-v2/batch-3/implement/codex-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
