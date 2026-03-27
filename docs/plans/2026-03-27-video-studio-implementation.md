# Video Studio Batch-6 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the complete batch-6 Studio Video feature for Bilibili, including backend summary pipeline, Studio UI, `/video` runtime skill integration, QR login, and live browser verification.

**Architecture:** Backend-first vertical slice. The implementation adds a formal `VideoSummary` domain model, Bilibili infrastructure adapters, a shared `VideoService`, dedicated REST/SSE routers, and a focused frontend module mounted inside the existing Studio panel. Summary progress and QR login both stream through reusable SSE consumers, while agent and Studio entry points converge on the same backend service.

**Tech Stack:** FastAPI, SQLAlchemy, Postgres, object storage backend, Zustand, TanStack React Query, Next.js 15, React 19, Vitest, Playwright MCP, bilibili-api-python, PyAV, uv.

---

### Task 1: Add persistence schema and core video domain types

**Files:**
- Create: `newbee_notebook/domain/entities/video_summary.py`
- Create: `newbee_notebook/domain/repositories/video_summary_repository.py`
- Create: `newbee_notebook/infrastructure/persistence/repositories/video_summary_repo_impl.py`
- Modify: `newbee_notebook/infrastructure/persistence/models.py`
- Create: `newbee_notebook/scripts/db/migrations/batch6_videos.sql`
- Test: `newbee_notebook/tests/unit/application/services/test_video_summary_repo_impl.py`

**Step 1: Write the failing test**

```python
async def test_video_repo_round_trip(async_session):
    repo = VideoSummaryRepositoryImpl(async_session)
    created = await repo.create(
        VideoSummary(
            notebook_id=None,
            platform="bilibili",
            video_id="BV1xx411c7mD",
            source_url="https://www.bilibili.com/video/BV1xx411c7mD",
            title="Demo",
        )
    )
    fetched = await repo.get(created.summary_id)
    assert fetched is not None
    assert fetched.video_id == "BV1xx411c7mD"
```

**Step 2: Run test to verify it fails**

Run: `..\\.venv\\Scripts\\python.exe -m pytest newbee_notebook/tests/unit/application/services/test_video_summary_repo_impl.py -v`
Expected: FAIL because the entity, repository, model, or table do not exist yet.

**Step 3: Write minimal implementation**

```python
@dataclass
class VideoSummary(Entity):
    summary_id: str = field(default_factory=generate_uuid)
    notebook_id: str | None = None
    platform: str = "bilibili"
    video_id: str = ""
    source_url: str = ""
    title: str = ""
    cover_url: str | None = None
    duration_seconds: int = 0
    uploader_name: str = ""
    uploader_id: str = ""
    stats: dict | None = None
    transcript_source: str = ""
    transcript_path: str | None = None
    summary_content: str = ""
    status: str = "processing"
    error_message: str | None = None
    document_ids: list[str] = field(default_factory=list)
```

**Step 4: Run test to verify it passes**

Run: `..\\.venv\\Scripts\\python.exe -m pytest newbee_notebook/tests/unit/application/services/test_video_summary_repo_impl.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/domain/entities/video_summary.py newbee_notebook/domain/repositories/video_summary_repository.py newbee_notebook/infrastructure/persistence/models.py newbee_notebook/infrastructure/persistence/repositories/video_summary_repo_impl.py newbee_notebook/scripts/db/migrations/batch6_videos.sql newbee_notebook/tests/unit/application/services/test_video_summary_repo_impl.py
git commit -m "feat: add video summary persistence model"
```

### Task 2: Add Bilibili payload normalization, exception mapping, and auth manager

**Files:**
- Create: `newbee_notebook/infrastructure/bilibili/__init__.py`
- Create: `newbee_notebook/infrastructure/bilibili/exceptions.py`
- Create: `newbee_notebook/infrastructure/bilibili/payloads.py`
- Create: `newbee_notebook/infrastructure/bilibili/auth.py`
- Test: `newbee_notebook/tests/unit/infrastructure/bilibili/test_payloads.py`
- Test: `newbee_notebook/tests/unit/infrastructure/bilibili/test_auth.py`

**Step 1: Write the failing tests**

```python
def test_normalize_video_info_maps_owner_and_stats():
    payload = normalize_video_info({"bvid": "BV1", "owner": {"name": "UP"}, "stat": {"view": 12}})
    assert payload["video_id"] == "BV1"
    assert payload["uploader_name"] == "UP"
    assert payload["stats"]["view"] == 12

def test_auth_manager_reads_saved_credential(tmp_path):
    manager = BilibiliAuthManager(base_dir=tmp_path)
    manager.save_credential({"sessdata": "abc", "bili_jct": "def"})
    assert manager.load_credential()["sessdata"] == "abc"
```

**Step 2: Run tests to verify they fail**

Run: `..\\.venv\\Scripts\\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/bilibili/test_payloads.py newbee_notebook/tests/unit/infrastructure/bilibili/test_auth.py -v`
Expected: FAIL because the infrastructure module does not exist yet.

**Step 3: Write minimal implementation**

```python
class BilibiliAuthManager:
    def __init__(self, base_dir: Path) -> None:
        self._path = base_dir / "bilibili" / "credential.json"

    def save_credential(self, payload: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def load_credential(self) -> dict[str, str] | None:
        if not self._path.exists():
            return None
        return json.loads(self._path.read_text(encoding="utf-8"))
```

**Step 4: Run tests to verify they pass**

Run: `..\\.venv\\Scripts\\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/bilibili/test_payloads.py newbee_notebook/tests/unit/infrastructure/bilibili/test_auth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/infrastructure/bilibili/__init__.py newbee_notebook/infrastructure/bilibili/exceptions.py newbee_notebook/infrastructure/bilibili/payloads.py newbee_notebook/infrastructure/bilibili/auth.py newbee_notebook/tests/unit/infrastructure/bilibili/test_payloads.py newbee_notebook/tests/unit/infrastructure/bilibili/test_auth.py
git commit -m "feat: add bilibili normalization and auth manager"
```

### Task 3: Add Bilibili client and ASR pipeline adapters

**Files:**
- Create: `newbee_notebook/infrastructure/bilibili/client.py`
- Create: `newbee_notebook/infrastructure/bilibili/asr.py`
- Test: `newbee_notebook/tests/unit/infrastructure/bilibili/test_client.py`
- Test: `newbee_notebook/tests/unit/infrastructure/bilibili/test_asr.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_extract_bvid_accepts_bilibili_url():
    assert extract_bvid("https://www.bilibili.com/video/BV1xx411c7mD") == "BV1xx411c7mD"

@pytest.mark.asyncio
async def test_asr_pipeline_concatenates_results_in_order():
    pipeline = AsrPipeline(...)
    result = await pipeline._merge_results(["one", "two", "three"])
    assert result == "one two three"
```

**Step 2: Run tests to verify they fail**

Run: `..\\.venv\\Scripts\\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/bilibili/test_client.py newbee_notebook/tests/unit/infrastructure/bilibili/test_asr.py -v`
Expected: FAIL because the client and pipeline adapters do not exist yet.

**Step 3: Write minimal implementation**

```python
_BVID_RE = re.compile(r"\\bBV[0-9A-Za-z]{10}\\b")

def extract_bvid(value: str) -> str:
    match = _BVID_RE.search(value)
    if not match:
        raise InvalidBvidError(value)
    return match.group(0)
```

**Step 4: Run tests to verify they pass**

Run: `..\\.venv\\Scripts\\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/bilibili/test_client.py newbee_notebook/tests/unit/infrastructure/bilibili/test_asr.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/infrastructure/bilibili/client.py newbee_notebook/infrastructure/bilibili/asr.py newbee_notebook/tests/unit/infrastructure/bilibili/test_client.py newbee_notebook/tests/unit/infrastructure/bilibili/test_asr.py
git commit -m "feat: add bilibili client and asr adapters"
```

### Task 4: Implement VideoService with transcript persistence and dedupe rules

**Files:**
- Create: `newbee_notebook/application/services/video_service.py`
- Modify: `newbee_notebook/infrastructure/storage/object_keys.py`
- Test: `newbee_notebook/tests/unit/application/services/test_video_service.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_summarize_reuses_completed_summary(video_service, existing_summary):
    summary = await video_service.summarize("BV1xx411c7mD")
    assert summary.summary_id == existing_summary.summary_id

@pytest.mark.asyncio
async def test_summarize_calls_asr_when_subtitle_missing(video_service, fake_progress):
    summary = await video_service.summarize("BV1xx411c7mD", progress_callback=fake_progress)
    assert summary.transcript_source == "asr"
```

**Step 2: Run tests to verify they fail**

Run: `..\\.venv\\Scripts\\python.exe -m pytest newbee_notebook/tests/unit/application/services/test_video_service.py -v`
Expected: FAIL because `VideoService` and its dependencies are not implemented yet.

**Step 3: Write minimal implementation**

```python
class VideoService:
    async def summarize(self, url_or_bvid: str, notebook_id: str | None = None, progress_callback=None) -> VideoSummary:
        bvid = self._bili_client.extract_bvid(url_or_bvid)
        existing = await self._video_repo.get_by_platform_and_video_id("bilibili", bvid)
        if existing and existing.status == "completed":
            if progress_callback:
                await progress_callback("done", {"summary_id": existing.summary_id, "reused": True})
            return existing
        ...
```

**Step 4: Run tests to verify they pass**

Run: `..\\.venv\\Scripts\\python.exe -m pytest newbee_notebook/tests/unit/application/services/test_video_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/application/services/video_service.py newbee_notebook/infrastructure/storage/object_keys.py newbee_notebook/tests/unit/application/services/test_video_service.py
git commit -m "feat: add video service pipeline"
```

### Task 5: Add routers, request models, dependency wiring, and runtime skill provider

**Files:**
- Create: `newbee_notebook/api/models/video_models.py`
- Create: `newbee_notebook/api/routers/videos.py`
- Create: `newbee_notebook/api/routers/bilibili_auth.py`
- Create: `newbee_notebook/skills/video/__init__.py`
- Create: `newbee_notebook/skills/video/provider.py`
- Create: `newbee_notebook/skills/video/tools.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Modify: `newbee_notebook/api/main.py`
- Test: `newbee_notebook/tests/unit/test_videos_router.py`
- Test: `newbee_notebook/tests/unit/test_bilibili_auth_router.py`
- Test: `newbee_notebook/tests/unit/skills/video/test_tools.py`
- Test: `newbee_notebook/tests/unit/test_chat_runtime_routing.py`

**Step 1: Write the failing tests**

```python
def test_video_route_registered(client):
    response = client.get("/api/v1/videos")
    assert response.status_code != 404

def test_skill_registry_supports_video_command():
    registry = SkillRegistry()
    registry.register(_FakeProvider(skill_name="video", slash_commands=["/video"]))
    assert registry.match_command("/video summarize BV1xx411c7mD") is not None
```

**Step 2: Run tests to verify they fail**

Run: `..\\.venv\\Scripts\\python.exe -m pytest newbee_notebook/tests/unit/test_videos_router.py newbee_notebook/tests/unit/test_bilibili_auth_router.py newbee_notebook/tests/unit/skills/video/test_tools.py newbee_notebook/tests/unit/test_chat_runtime_routing.py -v`
Expected: FAIL because the routers, models, and skill provider are absent.

**Step 3: Write minimal implementation**

```python
class VideoSkillProvider:
    @property
    def slash_commands(self) -> list[str]:
        return ["/video"]
```

**Step 4: Run tests to verify they pass**

Run: `..\\.venv\\Scripts\\python.exe -m pytest newbee_notebook/tests/unit/test_videos_router.py newbee_notebook/tests/unit/test_bilibili_auth_router.py newbee_notebook/tests/unit/skills/video/test_tools.py newbee_notebook/tests/unit/test_chat_runtime_routing.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/api/models/video_models.py newbee_notebook/api/routers/videos.py newbee_notebook/api/routers/bilibili_auth.py newbee_notebook/skills/video/__init__.py newbee_notebook/skills/video/provider.py newbee_notebook/skills/video/tools.py newbee_notebook/api/dependencies.py newbee_notebook/api/main.py newbee_notebook/tests/unit/test_videos_router.py newbee_notebook/tests/unit/test_bilibili_auth_router.py newbee_notebook/tests/unit/skills/video/test_tools.py newbee_notebook/tests/unit/test_chat_runtime_routing.py
git commit -m "feat: expose video apis and runtime skill"
```

### Task 6: Add frontend data types, API clients, hooks, and store extensions

**Files:**
- Modify: `frontend/src/lib/api/types.ts`
- Create: `frontend/src/lib/api/videos.ts`
- Create: `frontend/src/lib/api/bilibili-auth.ts`
- Create: `frontend/src/lib/api/sse.ts`
- Create: `frontend/src/lib/hooks/use-videos.ts`
- Create: `frontend/src/lib/hooks/use-bilibili-auth.ts`
- Modify: `frontend/src/stores/studio-store.ts`
- Test: `frontend/src/stores/studio-store.test.ts`
- Test: `frontend/src/lib/hooks/use-videos.test.tsx`

**Step 1: Write the failing tests**

```tsx
it("opens video detail and returns to the video list", () => {
  const store = useStudioStore.getState()
  store.openVideoDetail("video-1")
  expect(useStudioStore.getState().studioView).toBe("video-detail")
  store.backToVideoList()
  expect(useStudioStore.getState().studioView).toBe("videos")
})
```

**Step 2: Run tests to verify they fail**

Run: `pnpm test -- studio-store.test.ts use-videos.test.tsx`
Expected: FAIL because the store and hooks do not expose video state yet.

**Step 3: Write minimal implementation**

```ts
export type StudioView =
  | "home"
  | "notes"
  | "note-detail"
  | "diagrams"
  | "diagram-detail"
  | "videos"
  | "video-detail";
```

**Step 4: Run tests to verify they pass**

Run: `pnpm test -- studio-store.test.ts use-videos.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/lib/api/types.ts frontend/src/lib/api/videos.ts frontend/src/lib/api/bilibili-auth.ts frontend/src/lib/api/sse.ts frontend/src/lib/hooks/use-videos.ts frontend/src/lib/hooks/use-bilibili-auth.ts frontend/src/stores/studio-store.ts frontend/src/stores/studio-store.test.ts frontend/src/lib/hooks/use-videos.test.tsx
git commit -m "feat: add video frontend data layer"
```

### Task 7: Build Studio Video views and chat slash integration

**Files:**
- Create: `frontend/src/components/studio/video-list.tsx`
- Create: `frontend/src/components/studio/video-detail.tsx`
- Create: `frontend/src/components/studio/video-input-area.tsx`
- Create: `frontend/src/components/studio/video-list-item.tsx`
- Create: `frontend/src/components/studio/video-info-header.tsx`
- Create: `frontend/src/components/studio/video-action-bar.tsx`
- Create: `frontend/src/components/studio/bilibili-login-dialog.tsx`
- Modify: `frontend/src/components/studio/studio-panel.tsx`
- Modify: `frontend/src/components/chat/slash-command-hint.tsx`
- Modify: `frontend/src/lib/hooks/useChatSession.ts`
- Test: `frontend/src/components/studio/video-list.test.tsx`
- Test: `frontend/src/components/studio/video-detail.test.tsx`
- Test: `frontend/src/components/studio/video-input-area.test.tsx`
- Test: `frontend/src/components/chat/slash-command-hint.test.tsx`

**Step 1: Write the failing tests**

```tsx
it("shows /video in slash command hint", () => {
  render(<SlashCommandHint input="/vi" onSelect={() => {}} />)
  expect(screen.getByText("/video")).toBeInTheDocument()
})

it("renders summary progress from sse events", async () => {
  render(<VideoInputArea notebookId="nb-1" />)
  await user.click(screen.getByRole("button", { name: /summarize/i }))
  expect(screen.getByText(/analyzing video/i)).toBeInTheDocument()
})
```

**Step 2: Run tests to verify they fail**

Run: `pnpm test -- video-list.test.tsx video-detail.test.tsx video-input-area.test.tsx slash-command-hint.test.tsx`
Expected: FAIL because the new components and command entry do not exist yet.

**Step 3: Write minimal implementation**

```tsx
export function VideoListView({ notebookId }: { notebookId: string }) {
  return <div data-testid="video-list-view">{notebookId}</div>;
}
```

**Step 4: Run tests to verify they pass**

Run: `pnpm test -- video-list.test.tsx video-detail.test.tsx video-input-area.test.tsx slash-command-hint.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/studio/video-list.tsx frontend/src/components/studio/video-detail.tsx frontend/src/components/studio/video-input-area.tsx frontend/src/components/studio/video-list-item.tsx frontend/src/components/studio/video-info-header.tsx frontend/src/components/studio/video-action-bar.tsx frontend/src/components/studio/bilibili-login-dialog.tsx frontend/src/components/studio/studio-panel.tsx frontend/src/components/chat/slash-command-hint.tsx frontend/src/lib/hooks/useChatSession.ts frontend/src/components/studio/video-list.test.tsx frontend/src/components/studio/video-detail.test.tsx frontend/src/components/studio/video-input-area.test.tsx frontend/src/components/chat/slash-command-hint.test.tsx
git commit -m "feat: add studio video ui and chat integration"
```

### Task 8: Verify the full stack locally and record live browser evidence

**Files:**
- Modify: `docs/backend-v2/batch-6/video/implementation-plan.md`
- Modify: `docs/plans/2026-03-27-video-studio-design.md`

**Step 1: Run backend verification**

Run: `..\\.venv\\Scripts\\python.exe -m pytest newbee_notebook/tests/unit/application/services/test_video_service.py newbee_notebook/tests/unit/test_videos_router.py newbee_notebook/tests/unit/test_bilibili_auth_router.py -v`
Expected: PASS

**Step 2: Run frontend verification**

Run: `pnpm test -- video-list.test.tsx video-detail.test.tsx video-input-area.test.tsx studio-store.test.ts slash-command-hint.test.tsx`
Expected: PASS

**Step 3: Start the real backend**

Run: `..\\.venv\\Scripts\\python.exe -m uvicorn newbee_notebook.api.main:app --host 127.0.0.1 --port 8010`
Expected: FastAPI starts successfully

**Step 4: Start the real frontend**

Run: `pnpm dev -p 3001`
Expected: Next.js starts successfully

**Step 5: Drive browser flows with Playwright MCP**

Verify:
- summarize a public video
- open summary detail
- associate notebook
- delete summary
- run `/video` in chat and confirm panel refresh
- verify Bilibili login UI event flow

**Step 6: Commit**

```bash
git add docs/backend-v2/batch-6/video/implementation-plan.md docs/plans/2026-03-27-video-studio-design.md
git commit -m "docs: record video batch-6 verification notes"
```
