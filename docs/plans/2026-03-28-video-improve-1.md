# Video Improve-1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the improve-1 video enhancements by filling missing Bilibili client capabilities, enabling subtitle-fallback ASR, and wiring ASR configuration into the existing runtime settings flow.

**Architecture:** Keep the existing Studio and `/video` feature boundaries intact while strengthening the backend in layers. First complete `BilibiliClient` and payload normalization, then add provider-backed ASR behind the existing `VideoService` fallback path, and finally expose ASR selection through the same DB-backed model configuration system already used for LLM and Embedding.

**Tech Stack:** FastAPI, SQLAlchemy async, React/Next.js App Router, TanStack Query, `bilibili-api-python`, `aiohttp`, `av` (PyAV), pytest, vitest, Playwright.

---

### Task 1: Lock BilibiliClient Improve-1 Behavior With Tests

**Files:**
- Modify: `newbee_notebook/tests/unit/infrastructure/bilibili/test_client.py`
- Modify: `newbee_notebook/tests/unit/application/services/test_video_service.py`

**Step 1: Write failing tests**

Add unit tests for:
- `search_video()`
- `get_hot_videos()`
- `get_rank_videos()`
- `get_related_videos()`
- `get_video_ai_conclusion()`
- `get_audio_url()`
- `download_audio()`
- `VideoService.get_video_ai_conclusion()`

**Step 2: Run test to verify it fails**

Run: `D:\Projects\notebook-project\newbee-notebook\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/bilibili/test_client.py newbee_notebook/tests/unit/application/services/test_video_service.py -q`

Expected: failures for missing methods and proxy behavior.

**Step 3: Write minimal implementation**

Implement only what is necessary in the client/service/payload layer to satisfy the new tests.

**Step 4: Run test to verify it passes**

Run the same command and confirm the new cases pass.

**Step 5: Commit**

```bash
git add newbee_notebook/tests/unit/infrastructure/bilibili/test_client.py newbee_notebook/tests/unit/application/services/test_video_service.py newbee_notebook/infrastructure/bilibili/client.py newbee_notebook/infrastructure/bilibili/payloads.py newbee_notebook/application/services/video_service.py newbee_notebook/agent/skills/video.py
git commit -m "feat(video): complete bilibili client discovery APIs"
```

### Task 2: Implement BilibiliClient Missing Methods

**Files:**
- Modify: `newbee_notebook/infrastructure/bilibili/client.py`
- Modify: `newbee_notebook/infrastructure/bilibili/payloads.py`
- Modify: `newbee_notebook/application/services/video_service.py`
- Modify: `newbee_notebook/agent/skills/video.py`

**Step 1: Implement normalized discovery/content/audio methods**

Add:
- `search_video`
- `get_hot_videos`
- `get_rank_videos`
- `get_related_videos`
- `get_video_ai_conclusion`
- `get_audio_url`
- `download_audio`

Add normalization helpers for search results, hot/rank lists, and AI summary extraction.

**Step 2: Keep error mapping consistent**

Reuse `_map_api_error()` and client normalization style already used by `get_video_info()` and `get_video_subtitle()`.

**Step 3: Add proxy service methods**

Expose any missing client methods through `VideoService`.

**Step 4: Verify**

Run: `D:\Projects\notebook-project\newbee-notebook\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/bilibili/test_client.py newbee_notebook/tests/unit/application/services/test_video_service.py newbee_notebook/tests/unit/test_videos_router.py -q`

**Step 5: Commit**

```bash
git add newbee_notebook/infrastructure/bilibili/client.py newbee_notebook/infrastructure/bilibili/payloads.py newbee_notebook/application/services/video_service.py newbee_notebook/agent/skills/video.py
git commit -m "feat(video): complete bilibili client discovery APIs"
```

### Task 3: Add Audio Processing and Zhipu ASR Adapter

**Files:**
- Create: `newbee_notebook/infrastructure/bilibili/audio_processor.py`
- Create: `newbee_notebook/infrastructure/asr/__init__.py`
- Create: `newbee_notebook/infrastructure/asr/exceptions.py`
- Create: `newbee_notebook/infrastructure/asr/zhipu_transcriber.py`
- Modify: `newbee_notebook/infrastructure/bilibili/asr.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Modify: `newbee_notebook/application/services/video_service.py`
- Test: `newbee_notebook/tests/unit/infrastructure/asr/test_zhipu_transcriber.py`
- Test: `newbee_notebook/tests/unit/infrastructure/bilibili/test_audio_processor.py`

**Step 1: Write failing tests**

Cover:
- audio conversion/splitting contract
- Zhipu request formatting and response parsing
- ASR fallback success path in `VideoService`
- missing API key handling

**Step 2: Run tests to verify they fail**

Run: `D:\Projects\notebook-project\newbee-notebook\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/asr/test_zhipu_transcriber.py newbee_notebook/tests/unit/infrastructure/bilibili/test_audio_processor.py newbee_notebook/tests/unit/application/services/test_video_service.py -q`

**Step 3: Implement minimal code**

Build:
- PyAV-backed convert/split utility
- Zhipu transcriber adapter
- real `AsrPipeline` orchestration with cleanup
- dependency construction from runtime config

**Step 4: Verify**

Run the same command and confirm green.

**Step 5: Commit**

```bash
git add newbee_notebook/infrastructure/bilibili/audio_processor.py newbee_notebook/infrastructure/asr newbee_notebook/infrastructure/bilibili/asr.py newbee_notebook/api/dependencies.py newbee_notebook/application/services/video_service.py newbee_notebook/tests/unit/infrastructure/asr/test_zhipu_transcriber.py newbee_notebook/tests/unit/infrastructure/bilibili/test_audio_processor.py newbee_notebook/tests/unit/application/services/test_video_service.py pyproject.toml uv.lock
git commit -m "feat(video): add zhipu asr fallback pipeline"
```

### Task 4: Add ASR Runtime Configuration

**Files:**
- Modify: `newbee_notebook/core/common/config_db.py`
- Modify: `newbee_notebook/api/routers/config.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Test: `newbee_notebook/tests/unit/core/common/test_config_db.py`
- Test: `newbee_notebook/tests/unit/api/test_config_router.py`

**Step 1: Write failing tests**

Cover:
- `get_asr_config_async()`
- API key resolution
- `/config/models` includes `asr`
- `/config/models/available` includes `asr`
- `PUT /config/asr`
- `POST /config/asr/reset`

**Step 2: Run tests to verify they fail**

Run: `D:\Projects\notebook-project\newbee-notebook\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/common/test_config_db.py newbee_notebook/tests/unit/api/test_config_router.py -q`

**Step 3: Implement minimal code**

Add ASR defaults, config resolution, env projection, API models, endpoints, and dependency wiring.

**Step 4: Verify**

Run the same command and confirm green.

**Step 5: Commit**

```bash
git add newbee_notebook/core/common/config_db.py newbee_notebook/api/routers/config.py newbee_notebook/api/dependencies.py newbee_notebook/tests/unit/core/common/test_config_db.py newbee_notebook/tests/unit/api/test_config_router.py
git commit -m "feat(config): add runtime asr configuration"
```

### Task 5: Add Frontend ASR Settings Panel

**Files:**
- Modify: `frontend/src/lib/api/config.ts`
- Modify: `frontend/src/components/layout/model-config-panel.tsx`
- Modify: `frontend/src/lib/i18n/strings.ts`
- Test: `frontend/src/components/layout/model-config-panel.test.tsx`

**Step 1: Write failing tests**

Cover:
- load/display ASR config
- change provider/model
- reset ASR config
- show missing API key warning

**Step 2: Run test to verify it fails**

Run: `pnpm test src/components/layout/model-config-panel.test.tsx`

**Step 3: Write minimal implementation**

Extend existing model panel and config client types without introducing a new settings surface.

**Step 4: Verify**

Run:
- `pnpm test src/components/layout/model-config-panel.test.tsx`
- `pnpm typecheck`

**Step 5: Commit**

```bash
git add frontend/src/lib/api/config.ts frontend/src/components/layout/model-config-panel.tsx frontend/src/lib/i18n/strings.ts frontend/src/components/layout/model-config-panel.test.tsx
git commit -m "feat(frontend): expose asr model configuration"
```

### Task 6: Add Qwen ASR Adapter and Final Tool Restructure

**Files:**
- Create: `newbee_notebook/infrastructure/asr/qwen_transcriber.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Modify: `newbee_notebook/agent/skills/video.py`
- Modify: `newbee_notebook/application/services/video_service.py`
- Test: `newbee_notebook/tests/unit/infrastructure/asr/test_qwen_transcriber.py`
- Test: `newbee_notebook/tests/unit/agent/skills/test_video_skill.py`

**Step 1: Write failing tests**

Cover:
- Qwen adapter request/response parsing
- safe segmentation constraints
- merged tool behavior for `discover_videos` and `get_video_content`

**Step 2: Run tests to verify they fail**

Run: `D:\Projects\notebook-project\newbee-notebook\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/asr/test_qwen_transcriber.py newbee_notebook/tests/unit/agent/skills/test_video_skill.py -q`

**Step 3: Write minimal implementation**

Use a safe Qwen segmentation budget and keep AI conclusion agent-only.

**Step 4: Verify**

Run the same command and confirm green.

**Step 5: Commit**

```bash
git add newbee_notebook/infrastructure/asr/qwen_transcriber.py newbee_notebook/api/dependencies.py newbee_notebook/agent/skills/video.py newbee_notebook/application/services/video_service.py newbee_notebook/tests/unit/infrastructure/asr/test_qwen_transcriber.py newbee_notebook/tests/unit/agent/skills/test_video_skill.py
git commit -m "feat(video): add qwen asr and streamline video tools"
```

### Task 7: End-to-End Verification

**Files:**
- Verify only; no required file edits

**Step 1: Backend verification**

Run: `D:\Projects\notebook-project\newbee-notebook\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/application/services/test_video_service.py newbee_notebook/tests/unit/test_videos_router.py newbee_notebook/tests/unit/infrastructure/bilibili/test_client.py newbee_notebook/tests/unit/infrastructure/asr/test_zhipu_transcriber.py newbee_notebook/tests/unit/infrastructure/asr/test_qwen_transcriber.py newbee_notebook/tests/unit/core/common/test_config_db.py newbee_notebook/tests/unit/api/test_config_router.py -q`

**Step 2: Frontend verification**

Run:
- `pnpm test`
- `pnpm typecheck`
- `pnpm build`

**Step 3: Runtime verification**

Start backend and frontend in this worktree, then validate with Playwright:
- subtitle video still summarizes
- no-subtitle video uses ASR fallback
- ASR config switch updates behavior
- agent-related video endpoints don’t 500

**Step 4: Commit documentation updates**

If implementation details changed materially from improve-1 design docs, update the relevant docs before final integration.
