# Tasks — Batch-3: Notes & Marks + Note Skill

## Metadata
- Created: 2026-03-18
- Source Plan:
  - `docs/backend-v2/batch-3/note-bookmark/`
  - `docs/backend-v2/batch-3/note-related-skills/`
  - `docs/backend-v2/batch-3/frontend/`

## Progress Summary
- Total: 48 tasks
- Completed: 0
- In Progress: 0
- Remaining: 48

---

## Phase 1: 数据库迁移

### Task 1: 创建 marks / notes 相关表的迁移脚本

**Files:**
- Create: `newbee_notebook/scripts/db/migrations/batch3_notes_marks.sql`

- [ ] T001 Create SQL migration file with tables: `marks`, `notes`, `note_document_tags`, `note_mark_refs`, and all required indexes and cascade rules

  ```sql
  -- marks: document-level bookmarks (char_offset-based)
  CREATE TABLE marks (
      mark_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      document_id  UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
      anchor_text  TEXT NOT NULL,
      char_offset  INTEGER NOT NULL CHECK (char_offset >= 0),
      context_text TEXT,
      created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
  );
  CREATE INDEX idx_marks_document_id ON marks(document_id);

  -- notes: global, free-floating knowledge entries
  CREATE TABLE notes (
      note_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      title       TEXT NOT NULL DEFAULT '',
      content     TEXT NOT NULL DEFAULT '',
      created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  -- note_document_tags: note ↔ document many-to-many
  CREATE TABLE note_document_tags (
      note_id     UUID NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE,
      document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
      tagged_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (note_id, document_id)
  );
  CREATE INDEX idx_note_document_tags_document ON note_document_tags(document_id);

  -- note_mark_refs: [[mark:id]] references inside note content
  CREATE TABLE note_mark_refs (
      note_id  UUID NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE,
      mark_id  UUID NOT NULL REFERENCES marks(mark_id) ON DELETE CASCADE,
      PRIMARY KEY (note_id, mark_id)
  );
  CREATE INDEX idx_note_mark_refs_mark ON note_mark_refs(mark_id);
  ```

  - AC: Script runs cleanly against a fresh DB; all foreign keys and indexes created.

- [ ] T002 Apply migration to development database and verify all 4 tables exist

  Run: `psql $DATABASE_URL -f newbee_notebook/scripts/db/migrations/batch3_notes_marks.sql`
  Expected: `CREATE TABLE` × 4, `CREATE INDEX` × 4, no errors.

---

## Phase 2: 后端领域层 (Domain Layer)

### Task 2: Mark 领域实体

**Files:**
- Create: `newbee_notebook/domain/entities/mark.py`

- [ ] T003 Define `Mark` dataclass entity following the existing Entity base pattern

  ```python
  from dataclasses import dataclass, field
  from datetime import datetime
  from newbee_notebook.domain.entities.base import Entity

  @dataclass
  class Mark(Entity):
      mark_id:     str
      document_id: str
      anchor_text: str
      char_offset: int
      context_text: str | None = None
      created_at:  datetime = field(default_factory=datetime.utcnow)
      updated_at:  datetime = field(default_factory=datetime.utcnow)
  ```

### Task 3: Note 领域实体

**Files:**
- Create: `newbee_notebook/domain/entities/note.py`

- [ ] T004 Define `Note` dataclass entity

  ```python
  @dataclass
  class Note(Entity):
      note_id:      str
      title:        str
      content:      str                 # raw Markdown text
      document_ids: list[str] = field(default_factory=list)
      mark_ids:     list[str] = field(default_factory=list)
      created_at:   datetime = field(default_factory=datetime.utcnow)
      updated_at:   datetime = field(default_factory=datetime.utcnow)
  ```

### Task 4: Repository 抽象接口

**Files:**
- Create: `newbee_notebook/domain/repositories/mark_repository.py`
- Create: `newbee_notebook/domain/repositories/note_repository.py`

- [ ] T005 Define `MarkRepository` abstract interface

  ```python
  from typing import Protocol
  from newbee_notebook.domain.entities.mark import Mark

  class MarkRepository(Protocol):
      async def save(self, mark: Mark) -> Mark: ...
      async def find_by_id(self, mark_id: str) -> Mark | None: ...
      async def find_by_document(self, document_id: str) -> list[Mark]: ...
      async def delete(self, mark_id: str) -> None: ...
  ```

- [ ] T006 Define `NoteRepository` abstract interface

  ```python
  class NoteRepository(Protocol):
      async def save(self, note: Note) -> Note: ...
      async def find_by_id(self, note_id: str) -> Note | None: ...
      async def find_by_notebook(self, notebook_id: str, document_id: str | None = None) -> list[Note]: ...
      async def update_content(self, note_id: str, title: str, content: str) -> Note: ...
      async def add_document_tag(self, note_id: str, document_id: str) -> None: ...
      async def remove_document_tag(self, note_id: str, document_id: str) -> None: ...
      async def sync_mark_refs(self, note_id: str, mark_ids: list[str]) -> None: ...
      async def delete(self, note_id: str) -> None: ...
  ```

---

## Phase 3: 后端基础设施层 (Repository Implementations)

### Task 5: PostgresMarkRepository

**Files:**
- Create: `newbee_notebook/infrastructure/persistence/repositories/mark_repo_impl.py`

- [ ] T007 Implement `PostgresMarkRepository` with async asyncpg/SQLAlchemy queries, matching the existing `*_repo_impl.py` pattern in the same directory

  Key methods: `save`, `find_by_id`, `find_by_document`, `delete`.
  `find_by_document` returns results ordered by `char_offset ASC`.

### Task 6: PostgresNoteRepository

**Files:**
- Create: `newbee_notebook/infrastructure/persistence/repositories/note_repo_impl.py`

- [ ] T008 Implement `PostgresNoteRepository`

  `find_by_notebook` joins `note_document_tags` to filter by notebook's documents; when `document_id` is provided adds `WHERE note_document_tags.document_id = ?`.
  `sync_mark_refs` deletes all existing `note_mark_refs` for the note then re-inserts from provided list (full replace, not diff).

---

## Phase 4: 后端应用服务层 (TDD)

### Task 7: MarkService — TDD

**Files:**
- Create: `newbee_notebook/application/services/mark_service.py`
- Create: `newbee_notebook/tests/application/services/test_mark_service.py`

- [ ] T009 Write failing tests for MarkService

  ```python
  # test_mark_service.py
  import pytest
  from unittest.mock import AsyncMock
  from newbee_notebook.application.services.mark_service import MarkService, MarkNotFoundError

  @pytest.fixture
  def repo():
      return AsyncMock()

  @pytest.fixture
  def service(repo):
      return MarkService(repository=repo)

  async def test_create_mark_returns_entity(service, repo):
      repo.save.return_value = ...  # populate with expected Mark
      mark = await service.create_mark(document_id="d1", anchor_text="text", char_offset=42)
      assert mark.document_id == "d1"
      assert mark.char_offset == 42
      repo.save.assert_called_once()

  async def test_list_marks_by_document(service, repo):
      repo.find_by_document.return_value = []
      result = await service.list_marks(document_id="d1")
      assert result == []

  async def test_delete_nonexistent_mark_raises(service, repo):
      repo.find_by_id.return_value = None
      with pytest.raises(MarkNotFoundError):
          await service.delete_mark("nonexistent")
  ```

  Run: `pytest newbee_notebook/tests/application/services/test_mark_service.py -v`
  Expected: FAIL (MarkService not yet defined)

- [ ] T010 Implement `MarkService`

  ```python
  class MarkService:
      def __init__(self, repository: MarkRepository) -> None: ...
      async def create_mark(self, document_id: str, anchor_text: str, char_offset: int, context_text: str | None = None) -> Mark: ...
      async def list_marks(self, document_id: str) -> list[Mark]: ...
      async def get_mark(self, mark_id: str) -> Mark: ...  # raises MarkNotFoundError
      async def delete_mark(self, mark_id: str) -> None: ...  # raises MarkNotFoundError
  ```

- [ ] T011 Run tests — verify all pass

  Run: `pytest newbee_notebook/tests/application/services/test_mark_service.py -v`
  Expected: PASS × 3+

- [ ] T012 Commit

  `git commit -m "feat(mark): add Mark entity, repository, and MarkService"`

### Task 8: NoteService — TDD

**Files:**
- Create: `newbee_notebook/application/services/note_service.py`
- Create: `newbee_notebook/tests/application/services/test_note_service.py`

- [ ] T013 Write failing tests for NoteService CRUD

  ```python
  async def test_create_note_returns_entity(service, repo):
      repo.save.return_value = ...
      note = await service.create_note(title="Test", content="# Hello")
      assert note.title == "Test"

  async def test_update_note_content(service, repo):
      existing = Note(note_id="n1", title="Old", content="old", ...)
      repo.find_by_id.return_value = existing
      repo.update_content.return_value = Note(..., title="New", content="new", ...)
      result = await service.update_note(note_id="n1", title="New", content="new")
      assert result.title == "New"

  async def test_update_nonexistent_note_raises(service, repo):
      repo.find_by_id.return_value = None
      with pytest.raises(NoteNotFoundError):
          await service.update_note(note_id="bad", title="x", content="y")

  async def test_delete_note(service, repo):
      repo.find_by_id.return_value = Note(note_id="n1", ...)
      await service.delete_note("n1")
      repo.delete.assert_called_once_with("n1")
  ```

  Run: `pytest newbee_notebook/tests/application/services/test_note_service.py -v`
  Expected: FAIL

- [ ] T014 Write failing tests for NoteService document/mark associations

  ```python
  async def test_tag_document_calls_repo(service, repo):
      repo.find_by_id.return_value = Note(note_id="n1", ...)
      await service.tag_document(note_id="n1", document_id="d1")
      repo.add_document_tag.assert_called_once_with("n1", "d1")

  async def test_sync_mark_refs_extracts_ids_from_content(service, repo):
      content = "See [[mark:abc]] and [[mark:def]] here"
      repo.find_by_id.return_value = Note(note_id="n1", content=content, ...)
      await service.sync_mark_refs("n1")
      repo.sync_mark_refs.assert_called_once_with("n1", ["abc", "def"])
  ```

  Run: `pytest newbee_notebook/tests/application/services/test_note_service.py -v`
  Expected: FAIL

- [ ] T015 Implement `NoteService`

  ```python
  class NoteService:
      def __init__(self, note_repo: NoteRepository, mark_repo: MarkRepository) -> None: ...
      async def create_note(self, title: str, content: str) -> Note: ...
      async def get_note(self, note_id: str) -> Note: ...  # raises NoteNotFoundError
      async def update_note(self, note_id: str, title: str, content: str) -> Note: ...
      async def delete_note(self, note_id: str) -> None: ...
      async def list_notes(self, notebook_id: str, document_id: str | None = None) -> list[Note]: ...
      async def tag_document(self, note_id: str, document_id: str) -> None: ...
      async def untag_document(self, note_id: str, document_id: str) -> None: ...
      async def sync_mark_refs(self, note_id: str) -> None: ...
      # Parses [[mark:id]] from note content, calls repo.sync_mark_refs with extracted IDs
  ```

- [ ] T016 Run all NoteService tests — verify pass

  Run: `pytest newbee_notebook/tests/application/services/test_note_service.py -v`
  Expected: PASS × 6+

- [ ] T017 Commit

  `git commit -m "feat(note): add Note entity, repository, NoteService"`

---

## Phase 5: 后端 API 层

### Task 9: API 请求/响应模型

**Files:**
- Create: `newbee_notebook/api/models/mark_models.py`
- Create: `newbee_notebook/api/models/note_models.py`

- [ ] T018 Define Pydantic request/response models for Mark API

  `MarkResponse`: mark_id, document_id, anchor_text, char_offset, context_text, created_at, updated_at
  `CreateMarkRequest`: document_id, anchor_text, char_offset, context_text (optional)
  `MarkListResponse`: marks: list[MarkResponse], total: int

- [ ] T019 Define Pydantic request/response models for Note API

  `NoteResponse`: note_id, title, content, document_ids, mark_ids, created_at, updated_at
  `CreateNoteRequest`: title (default ""), content (default "")
  `UpdateNoteRequest`: title (optional), content (optional)
  `NoteListResponse`: notes: list[NoteResponse], total: int
  `TagDocumentRequest`: document_id

### Task 10: Marks REST 路由

**Files:**
- Create: `newbee_notebook/api/routers/marks.py`

- [ ] T020 Implement marks router with the following endpoints

  ```
  POST   /api/v1/marks                      → create mark
  GET    /api/v1/marks?document_id=X        → list marks by document
  DELETE /api/v1/marks/{mark_id}            → delete mark
  ```

  Follow the router pattern in `newbee_notebook/api/routers/notebooks.py`.

### Task 11: Notes REST 路由

**Files:**
- Create: `newbee_notebook/api/routers/notes.py`

- [ ] T021 Implement notes router

  ```
  POST   /api/v1/notes                                    → create note
  GET    /api/v1/notes?notebook_id=X[&document_id=Y]     → list notes
  GET    /api/v1/notes/{note_id}                          → get note
  PUT    /api/v1/notes/{note_id}                          → update note (content+title)
  DELETE /api/v1/notes/{note_id}                          → delete note
  POST   /api/v1/notes/{note_id}/documents                → tag document
  DELETE /api/v1/notes/{note_id}/documents/{document_id}  → untag document
  ```

  On `PUT` (update content), call `note_service.sync_mark_refs(note_id)` after updating.

### Task 12: 依赖注入注册

**Files:**
- Modify: `newbee_notebook/api/dependencies.py` (or equivalent DI config file)
- Modify: `main.py` or app factory — include new routers

- [ ] T022 Register MarkRepository, NoteRepository implementations in DI container
- [ ] T023 Register MarkService, NoteService in DI container
- [ ] T024 Include `marks.router` and `notes.router` in FastAPI app with prefix `/api/v1`

- [ ] T025 Smoke test: start server, call `POST /api/v1/marks` with valid payload

  Expected: 201 response with mark_id field.

- [ ] T026 Commit

  `git commit -m "feat(api): add marks and notes REST endpoints"`

---

## Phase 6: Skill 基础设施 (Contract-first)

### Task 13: Skill 合约定义

**Files:**
- Create: `newbee_notebook/core/skills/__init__.py`
- Create: `newbee_notebook/core/skills/contracts.py`

- [ ] T027 Define `SkillContext`, `SkillManifest`, `SkillProvider` in contracts.py

  ```python
  from dataclasses import dataclass, field
  from typing import Protocol
  from newbee_notebook.core.tools.contracts import ToolDefinition

  @dataclass(frozen=True)
  class SkillContext:
      notebook_id: str
      activated_command: str           # e.g. "/note"
      selected_document_ids: list[str] = field(default_factory=list)

  @dataclass(frozen=True)
  class SkillManifest:
      name: str
      slash_command: str
      description: str
      tools: list[ToolDefinition]
      system_prompt_addition: str = ""
      confirmation_required: frozenset[str] = field(default_factory=frozenset)

  class SkillProvider(Protocol):
      @property
      def skill_name(self) -> str: ...
      @property
      def slash_commands(self) -> list[str]: ...
      def build_manifest(self, context: SkillContext) -> SkillManifest: ...
  ```

### Task 14: SkillRegistry

**Files:**
- Create: `newbee_notebook/core/skills/registry.py`
- Create: `newbee_notebook/tests/core/skills/test_skill_registry.py`

- [ ] T028 Write failing tests for SkillRegistry

  ```python
  async def test_match_command_returns_provider(registry, mock_provider):
      # mock_provider.slash_commands = ["/note"]
      registry.register(mock_provider)
      result = registry.match_command("/note do something")
      assert result == mock_provider

  async def test_match_command_returns_none_for_non_slash(registry):
      result = registry.match_command("regular message")
      assert result is None

  async def test_match_command_case_insensitive(registry, mock_provider):
      registry.register(mock_provider)
      assert registry.match_command("/NOTE do something") is not None
  ```

  Run: `pytest newbee_notebook/tests/core/skills/test_skill_registry.py -v`
  Expected: FAIL

- [ ] T029 Implement `SkillRegistry`

  ```python
  class SkillRegistry:
      def __init__(self) -> None:
          self._providers: list[SkillProvider] = []

      def register(self, provider: SkillProvider) -> None:
          self._providers.append(provider)

      def match_command(self, message: str) -> SkillProvider | None:
          stripped = message.strip()
          for provider in self._providers:
              for cmd in provider.slash_commands:
                  if stripped.lower().startswith(cmd.lower()):
                      return provider
          return None

      def extract_command(self, message: str) -> tuple[str, str]:
          """Returns (slash_command, cleaned_message)."""
          ...
  ```

- [ ] T030 Run SkillRegistry tests — verify pass

  Run: `pytest newbee_notebook/tests/core/skills/test_skill_registry.py -v`
  Expected: PASS × 3+

### Task 15: ConfirmationRequestEvent + ConfirmationGateway

**Files:**
- Modify: `newbee_notebook/core/engine/stream_events.py`
- Create: `newbee_notebook/core/engine/confirmation.py`

- [ ] T031 Add `ConfirmationRequestEvent` to stream_events.py

  ```python
  @dataclass(frozen=True)
  class ConfirmationRequestEvent:
      request_id: str
      tool_name: str
      args_summary: dict   # subset of args safe to display to user
      description: str     # human-readable description of the action
  ```

- [ ] T032 Implement `ConfirmationGateway`

  ```python
  import asyncio
  from dataclasses import dataclass, field

  @dataclass
  class PendingConfirmation:
      event: asyncio.Event = field(default_factory=asyncio.Event)
      approved: bool = False

  class ConfirmationGateway:
      def __init__(self) -> None:
          self._pending: dict[str, PendingConfirmation] = {}

      def create(self, request_id: str) -> None:
          self._pending[request_id] = PendingConfirmation()

      async def wait(self, request_id: str, timeout: float = 180.0) -> bool:
          pending = self._pending.get(request_id)
          if pending is None:
              return False
          try:
              await asyncio.wait_for(pending.event.wait(), timeout=timeout)
              return pending.approved
          except asyncio.TimeoutError:
              return False
          finally:
              self._pending.pop(request_id, None)

      def resolve(self, request_id: str, approved: bool) -> bool:
          """Returns False if request_id not found (already expired or resolved)."""
          pending = self._pending.get(request_id)
          if pending is None:
              return False
          pending.approved = approved
          pending.event.set()
          return True
  ```

### Task 16: AgentLoop 确认机制

**Files:**
- Modify: `newbee_notebook/core/engine/agent_loop.py`

- [ ] T033 Add `confirmation_required` and `confirmation_gateway` optional params to AgentLoop `__init__`

  ```python
  def __init__(
      self,
      *,
      llm_client: Any,
      tools: list[ToolDefinition],
      mode_config: ModeConfig,
      confirmation_required: frozenset[str] | None = None,
      confirmation_gateway: ConfirmationGateway | None = None,
      ...
  ):
      ...
      self._confirmation_required = confirmation_required or frozenset()
      self._confirmation_gateway = confirmation_gateway
  ```

- [ ] T034 Add confirmation pause logic in `AgentLoop.stream()` before tool execution (around line 408)

  ```python
  # Before: result = await tool.execute(effective_arguments)
  if tool.name in self._confirmation_required and self._confirmation_gateway:
      request_id = str(uuid4())
      yield ConfirmationRequestEvent(
          request_id=request_id,
          tool_name=tool.name,
          args_summary={k: v for k, v in effective_arguments.items() if k != "content"},
          description=f"Agent 请求执行 {tool.name}",
      )
      self._confirmation_gateway.create(request_id)
      approved = await self._confirmation_gateway.wait(request_id, timeout=180.0)
      if not approved:
          # Inject rejection into tool history so agent knows
          tool_result_for_history = {"role": "tool", "content": "用户已拒绝此操作。"}
          chat_history.append(tool_result_for_history)
          continue
  ```

### Task 17: SessionManager + ChatService 集成

**Files:**
- Modify: `newbee_notebook/core/session/session_manager.py`
- Modify: `newbee_notebook/application/services/chat_service.py`

- [ ] T035 Add `external_tools`, `system_prompt_addition`, `confirmation_required`, `confirmation_gateway` params to `SessionManager._build_loop()` and `SessionManager.chat_stream()`

- [ ] T036 Modify `ChatService.chat_stream()` to detect slash prefix before calling SessionManager

  ```python
  # In ChatService.chat_stream(), before delegating to SessionManager:
  skill_provider = self._skill_registry.match_command(message)
  if skill_provider:
      slash_command, cleaned_message = self._skill_registry.extract_command(message)
      context = SkillContext(
          notebook_id=notebook_id,
          activated_command=slash_command,
          selected_document_ids=source_document_ids or [],
      )
      manifest = skill_provider.build_manifest(context)
      # Force agent mode, pass skill tools and confirmation config
      mode = "agent"
      external_tools = manifest.tools
      system_prompt_addition = manifest.system_prompt_addition
      confirmation_required = manifest.confirmation_required
      message = cleaned_message
  ```

### Task 18: /confirm API 端点

**Files:**
- Modify: `newbee_notebook/api/routers/chat.py`
- Create: `newbee_notebook/api/models/confirm_models.py`

- [ ] T037 Add `ConfirmActionRequest` model: `request_id: str`, `approved: bool`

- [ ] T038 Add `POST /api/v1/chat/{session_id}/confirm` endpoint

  Calls `confirmation_gateway.resolve(request_id, approved)`.
  Returns 200 if resolved, 404 if request_id not found (expired or invalid).

- [ ] T039 Commit

  `git commit -m "feat(skill): add SkillRegistry, ConfirmationGateway, AgentLoop confirmation support"`

---

## Phase 7: Note Skill

### Task 19: Note Skill 工具函数 — TDD

**Files:**
- Create: `newbee_notebook/skills/note/tools.py`
- Create: `newbee_notebook/tests/skills/note/test_note_tools.py`

- [ ] T040 Write failing tests for note skill tools execute functions

  ```python
  async def test_list_notes_tool_returns_json(mock_note_service):
      tool = build_list_notes_tool(mock_note_service, notebook_id="nb1")
      mock_note_service.list_notes.return_value = []
      result = await tool.execute({})
      assert result.error is None
      assert json.loads(result.content) == []

  async def test_create_note_tool_success(mock_note_service):
      mock_note_service.create_note.return_value = Note(note_id="n1", title="T", content="C", ...)
      tool = build_create_note_tool(mock_note_service, notebook_id="nb1")
      result = await tool.execute({"title": "T", "content": "C"})
      assert result.error is None
      assert "n1" in result.content

  async def test_update_note_tool_not_found(mock_note_service):
      mock_note_service.update_note.side_effect = NoteNotFoundError("n99")
      tool = build_update_note_tool(mock_note_service)
      result = await tool.execute({"note_id": "n99", "title": "x", "content": "y"})
      assert result.error is not None
  ```

  Run: `pytest newbee_notebook/tests/skills/note/test_note_tools.py -v`
  Expected: FAIL

- [ ] T041 Implement 8 note skill tool factory functions in `tools.py`

  Tools: `build_list_notes_tool`, `build_read_note_tool`, `build_create_note_tool`,
  `build_update_note_tool`, `build_delete_note_tool`, `build_list_marks_tool`,
  `build_associate_note_document_tool`, `build_disassociate_note_document_tool`

  Each function takes the service(s) and `notebook_id` as closure args, returns a `ToolDefinition`.
  See parameter schemas in `docs/backend-v2/batch-3/note-related-skills/03-tool-definitions.md`.

- [ ] T042 Run note tools tests — verify pass

  Run: `pytest newbee_notebook/tests/skills/note/test_note_tools.py -v`
  Expected: PASS × 6+

### Task 20: NoteSkillProvider + 注册

**Files:**
- Create: `newbee_notebook/skills/note/provider.py`
- Create: `newbee_notebook/skills/note/__init__.py`
- Modify: app startup / DI config — register NoteSkillProvider into SkillRegistry

- [ ] T043 Implement `NoteSkillProvider`

  ```python
  class NoteSkillProvider:
      def __init__(self, note_service: NoteService, mark_service: MarkService) -> None: ...

      @property
      def skill_name(self) -> str:
          return "note"

      @property
      def slash_commands(self) -> list[str]:
          return ["/note"]

      def build_manifest(self, context: SkillContext) -> SkillManifest:
          return SkillManifest(
              name="note",
              slash_command="/note",
              description="管理笔记",
              system_prompt_addition="...",  # from design doc
              tools=self._build_tools(context),
              confirmation_required=frozenset({"update_note", "delete_note", "disassociate_note_document"}),
          )
  ```

- [ ] T044 Register `NoteSkillProvider` in app startup

  `skill_registry.register(NoteSkillProvider(note_service, mark_service))`

- [ ] T045 Smoke test: send chat message `/note 列出所有笔记` in agent mode

  Expected: AgentLoop receives note skill tools; agent calls `list_notes` tool; response returns note list (empty is fine).

- [ ] T046 Commit

  `git commit -m "feat(note-skill): add NoteSkillProvider and 8 note agent tools"`

---

## Phase 8: 前端基础 (Frontend Foundation)

### Task 21: TypeScript 类型定义

**Files:**
- Create: `frontend/src/types/mark.ts`
- Create: `frontend/src/types/note.ts`

- [ ] T047 Define `Mark` and related types in mark.ts

  ```typescript
  export interface Mark {
    mark_id: string;
    document_id: string;
    anchor_text: string;
    char_offset: number;
    context_text: string | null;
    created_at: string;
    updated_at: string;
  }
  export interface CreateMarkRequest {
    document_id: string;
    anchor_text: string;
    char_offset: number;
    context_text?: string;
  }
  ```

- [ ] T048 Define `Note` and related types in note.ts

  ```typescript
  export interface Note {
    note_id: string;
    title: string;
    content: string;
    document_ids: string[];
    mark_ids: string[];
    created_at: string;
    updated_at: string;
  }
  export interface CreateNoteRequest { title: string; content: string; }
  export interface UpdateNoteRequest { title?: string; content?: string; }
  ```

### Task 22: i18n 文案

**Files:**
- Modify: `frontend/src/lib/i18n/` (add note/mark/slash-command strings following the existing pattern)

- [ ] T049 Add i18n strings for notes, marks, studio panel, and slash command selector

  Keys to add — see `docs/backend-v2/batch-3/frontend/04-i18n-and-types.md` for complete list.
  Both `zh` and `en` values required for every key.

### Task 23: TanStack Query Hooks

**Files:**
- Create: `frontend/src/lib/hooks/use-marks.ts`
- Create: `frontend/src/lib/hooks/use-notes.ts`

- [ ] T050 Implement mark hooks: `useMarks(documentId)`, `useCreateMark()`, `useDeleteMark()`

  `useMarks`: `GET /api/v1/marks?document_id={id}`, QueryKey `["marks", documentId]`
  `useCreateMark`: POST, invalidates `["marks", documentId]` on success
  `useDeleteMark`: DELETE, invalidates `["marks", documentId]` on success

- [ ] T051 Implement note hooks: `useNotes(notebookId, documentId?)`, `useNote(noteId)`, `useCreateNote()`, `useUpdateNote()`, `useDeleteNote()`, `useTagDocument()`, `useUntagDocument()`

  Follow the QueryKey invalidation strategy in `docs/backend-v2/batch-3/frontend/04-i18n-and-types.md`.

---

## Phase 9: 前端 Markdown Viewer 书签集成

### Task 24: SelectionMenu 书签按钮

**Files:**
- Modify: `frontend/src/components/reader/selection-menu.tsx`

- [ ] T052 Add `onMark` callback prop to `SelectionMenuProps` and render a Bookmark button alongside existing Explain/Conclude buttons

  ```typescript
  type SelectionMenuProps = {
    onExplain: ...;
    onConclude: ...;
    onMark: (payload: { documentId: string; selectedText: string }) => void;
  };
  ```

  The Bookmark button is visually distinct from Explain/Conclude (different icon, no highlight effect — just a small bookmark icon). It does NOT trigger text highlighting in the reader.

### Task 25: char_offset 计算工具

**Files:**
- Create: `frontend/src/lib/reader/mark-offset.ts`
- Create: `frontend/src/lib/reader/mark-offset.test.ts`

- [ ] T053 Write unit tests for `computeCharOffset`

  ```typescript
  // mark-offset.test.ts
  it("finds offset of first occurrence in chunk", () => {
    const chunkContent = "Hello world foo bar";
    const anchor = "foo bar";
    const chunkStart = 100;
    expect(computeCharOffset(chunkContent, anchor, chunkStart)).toBe(112); // 100 + 12
  });

  it("returns null when anchor not found", () => {
    expect(computeCharOffset("Hello", "xyz", 0)).toBeNull();
  });
  ```

  Run: `pnpm test mark-offset`
  Expected: FAIL

- [ ] T054 Implement `computeCharOffset(chunkContent: string, anchorText: string, chunkStart: number): number | null`

  Searches for first occurrence of `anchorText` in `chunkContent`, returns `chunkStart + index` or `null`.

- [ ] T055 Run tests — verify pass

  Run: `pnpm test mark-offset`
  Expected: PASS × 2+

### Task 26: 书签 margin icon 渲染

**Files:**
- Create: `frontend/src/lib/reader/apply-mark-highlights.ts`
- Modify: `frontend/src/components/reader/markdown-viewer.tsx`

- [ ] T056 Implement `applyMarkHighlights(containerEl, marks, chunkStartChar, onMarkClick)`

  For each mark whose `char_offset` falls within the chunk's range:
  1. Find the paragraph/block element containing the mark text (walk DOM text nodes)
  2. Add `data-mark-id` attribute and `mark-margin-icon` CSS class to the closest block element
  3. A CSS `::before` pseudo-element (or injected `<span>`) renders the bookmark icon in the left margin
  4. Click → calls `onMarkClick(mark_id)`

- [ ] T057 In MarkdownViewer, after each chunk renders (`useEffect` on chunk content + marks):
  1. Read `data-chunk-start` from chunk container div
  2. Filter marks whose `char_offset` falls in `[chunkStart, chunkStart + chunkLength)`
  3. Call `applyMarkHighlights(chunkDiv, chunkMarks, chunkStart, onMarkClick)`

- [ ] T058 In DocumentReader, add `onMark` handler to SelectionMenu:
  - Compute `char_offset` via `computeCharOffset`
  - Call `createMarkMutation.mutate({document_id, anchor_text, char_offset})`
  - On success: invalidate marks query → triggers highlight re-render

---

## Phase 10: 前端 Studio Panel — Notes & Marks

### Task 27: Studio Home 图表卡片 + Zustand store

**Files:**
- Modify: `frontend/src/components/studio/studio-panel.tsx`
- Modify: `frontend/src/stores/` (studio store — add `studioView` field)

- [ ] T059 Extend studio Zustand store with `studioView: "home" | "notes" | "note-detail"` and `activeNoteId: string | null`

- [ ] T060 Replace "Coming Soon" placeholder in `studio-panel.tsx` with `StudioHome` component showing a 2-column card grid; add "Notes & Marks" card (enabled)

  ```tsx
  <FeatureCard
    title={t(uiStrings.studio.notesMarks.cardTitle)}
    icon={<NotesIcon />}
    available={true}
    onClick={() => setStudioView("notes")}
  />
  ```

### Task 28: NoteListView

**Files:**
- Create: `frontend/src/components/studio/notes/note-list-view.tsx`

- [ ] T061 Implement `NoteListView` component

  - Header: `[← Studio]` back button + `[Filter: 全部文档 ▾]` dropdown
  - Note cards: title, document count badge, relative timestamp, delete button (trash icon)
  - Empty state: guide text pointing to `/note` slash command
  - Click note card → `setStudioView("note-detail")` + `setActiveNoteId(id)`
  - Delete button → confirmation dialog → `useDeleteNote().mutate(noteId)` → list refresh

### Task 29: NoteEditor

**Files:**
- Create: `frontend/src/components/studio/notes/note-editor.tsx`

- [ ] T062 Implement `NoteEditor` component

  - Header: `[← Notes]` back button + `[Delete]` button
  - Title input field (controlled)
  - Document tags row: existing tags as pills with × remove, `[+ Add Document]` picker
  - Markdown textarea (controlled)
  - Auto-save indicator: "Saving..." / "Saved" (debounce 5s or Ctrl+S)
  - Calls `useUpdateNote().mutate(...)` after debounce; calls `useTagDocument()` / `useUntagDocument()` on tag changes

### Task 30: [[mark:id]] 行内选择器

**Files:**
- Create: `frontend/src/components/studio/notes/mark-inline-picker.tsx`

- [ ] T063 Implement `MarkInlinePicker` popover component

  Triggered when user types `[[` in the note textarea:
  - Anchored popover below current cursor line
  - Lists marks from associated documents (filtered by already-typed search term)
  - Keyboard: ↑↓ navigate, Enter select, Escape dismiss
  - On select: inserts `[[mark:{mark_id}]]` at cursor, closes popover

- [ ] T064 Wire `MarkInlinePicker` into `NoteEditor` textarea `onChange` handler

  Detect `[[` sequence → show picker; on pick → splice `[[mark:id]]` into textarea value.

### Task 31: MarksSection

**Files:**
- Create: `frontend/src/components/studio/notes/marks-section.tsx`

- [ ] T065 Implement `MarksSection` collapsible component (shown at bottom of NoteEditor)

  - Collapsible toggle header: "Available Marks (N)"
  - `[Filter by document ▾]` dropdown
  - Mark list: each item shows anchor_text preview + `[⏎ Insert]` button
  - Insert button → calls `onInsert(mark_id)` → NoteEditor splices `[[mark:id]]` at cursor

### Task 32: Mark 引用 Pill 渲染

**Files:**
- Create: `frontend/src/lib/notes/render-mark-refs.ts`
- Modify: `frontend/src/components/studio/notes/note-list-view.tsx`

- [ ] T066 Implement `renderMarkRefs(content: string, marks: Mark[]): string`

  Replaces `[[mark:{id}]]` tokens in rendered note HTML with a styled `<span>` pill:
  ```html
  <span class="mark-ref-pill" data-mark-id="{id}">
    "{anchor_text preview...}"
  </span>
  ```
  Missing mark IDs render as `<span class="mark-ref-missing">[[mark:{id}]]</span>`.

- [ ] T067 Apply `renderMarkRefs` in note card preview (NoteListView) and note detail view

---

## Phase 11: 前端 Skill 交互

### Task 33: SlashCommandSelector 组件

**Files:**
- Create: `frontend/src/components/chat/slash-command-selector.tsx`

- [ ] T068 Implement `SlashCommandSelector` component

  Appears above the chat input when user types `/`:
  - Lists registered slash commands: `/note`, `/mindmap` (coming soon), etc.
  - Filters as user continues typing (`/no` → shows `/note`)
  - "即将推出" badge for `available: false` commands
  - Click or Enter → fills command into input, moves cursor after command

- [ ] T069 Integrate `SlashCommandSelector` into the chat input component

  Detect `/` as first character → show selector; on select → update input value.
  Escape → dismiss selector.

### Task 34: ConfirmationCard 组件

**Files:**
- Create: `frontend/src/components/chat/confirmation-card.tsx`

- [ ] T070 Implement `ConfirmationCard` inline message component

  Renders when SSE emits `ConfirmationRequestEvent`:
  - Shows tool_name, args_summary, description
  - Two buttons: `[确认]` and `[取消]`
  - On click → `POST /api/v1/chat/{session_id}/confirm` with `{request_id, approved}`
  - After response: card transitions to "已确认" / "已取消" state (read-only)
  - 3-minute countdown timer shown; on timeout card shows "操作已超时"

- [ ] T071 Integrate `ConfirmationCard` into chat message stream rendering

  When SSE event type is `confirmation_request`, insert a `ConfirmationCard` into the message list at the current agent turn position.

---

## Phase 12: 集成收尾

### Task 35: 文档删除级联警告

**Files:**
- Modify: `frontend/src/components/sources/` (document remove/delete confirmation dialog)

- [ ] T072 Add cascade warning to document delete confirmation dialog

  When a document has associated marks (check via `useMarks(documentId)`), append to the confirmation message:
  > "该文档有 N 个书签，删除后书签将一并删除。"

### Task 36: 端到端冒烟测试

- [ ] T073 Manual E2E: open a document → select text → click Bookmark → verify mark appears as margin icon

- [ ] T074 Manual E2E: open Studio → Notes & Marks → create note → type `[[` → verify mark picker appears → insert mark ref → save → verify pill renders

- [ ] T075 Manual E2E: type `/note 列出所有笔记` in chat → verify slash command selector shows `/note` → send → verify agent responds with note list

- [ ] T076 Manual E2E: type `/note 删除笔记 {note_id}` → verify ConfirmationCard appears → click Confirm → verify note deleted → click Cancel on a second attempt → verify note not deleted

### Task 37: 最终提交

- [ ] T077 Run all backend tests

  Run: `pytest newbee_notebook/tests/ -v`
  Expected: all pass, no failures.

- [ ] T078 Run frontend type check and lint

  Run: `pnpm typecheck && pnpm lint`
  Expected: no errors.

- [ ] T079 Final commit

  `git commit -m "feat(batch-3): complete Notes, Marks, NoteSkill, and frontend integration"`
