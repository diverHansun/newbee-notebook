# Video Studio Batch-6 Design

## Background

This document records the approved design decisions for the Studio Video feature in batch-6. The implementation target is a complete first release: backend video pipeline, Studio UI, `/video` agent integration, Bilibili QR login, notebook/document association, and end-to-end verification in a real browser session.

## Scope

- Backend-first delivery on a dedicated feature branch.
- Bilibili is the only supported platform in batch-6.
- Video summaries are persisted independently from notebooks, but can be associated with the current notebook and document set.
- The Studio Video panel and `/video` slash command both use the same `VideoService`.
- End-to-end verification uses live FastAPI and Next.js processes plus Playwright MCP, not a standalone scripted E2E runner.

## Unified API Contract

### Summary Flow

- `POST /api/v1/videos/summarize`
- Request body:

```json
{
  "url_or_bvid": "BVxxxxxxxxxx",
  "notebook_id": "optional-notebook-id"
}
```

- Response type: `text/event-stream`
- Event order:
  - `start`
  - `info`
  - `subtitle`
  - `asr`
  - `summarize`
  - `done`
  - `error`

### Summary CRUD and Read APIs

- `GET /api/v1/videos`
- `GET /api/v1/videos/{summary_id}`
- `DELETE /api/v1/videos/{summary_id}`
- `GET /api/v1/videos/info`
- `GET /api/v1/videos/search`
- `GET /api/v1/videos/hot`
- `GET /api/v1/videos/rank`
- `POST /api/v1/videos/{summary_id}/notebook`
- `DELETE /api/v1/videos/{summary_id}/notebook`
- `POST /api/v1/videos/{summary_id}/documents`
- `DELETE /api/v1/videos/{summary_id}/documents/{document_id}`

### Bilibili Auth

- `GET /api/v1/bilibili/auth/qr`
- `GET /api/v1/bilibili/auth/status`
- `POST /api/v1/bilibili/auth/logout`

The QR login endpoint returns `qr_generated`, `scanned`, `done`, `timeout`, and `error` events. The `qr_generated` payload includes both `qr_url` and `image_base64`.

## Data Model

### Core Entity

`VideoSummary` is the single source of truth for persisted video summaries.

Recommended API/entity fields:

- `summary_id`
- `notebook_id`
- `platform`
- `video_id`
- `source_url`
- `title`
- `cover_url`
- `duration_seconds`
- `uploader_name`
- `uploader_id`
- `stats`
- `transcript_source`
- `transcript_path`
- `summary_content`
- `status`
- `error_message`
- `document_ids`
- `created_at`
- `updated_at`

### Persistence Decisions

- Summary Markdown is stored inline in Postgres.
- Raw transcript text is stored in object storage and referenced by `transcript_path`.
- `transcript_source` replaces the ambiguous `summary_type` naming from the draft docs.
- `document_ids` uses `UUID[]` plus a GIN index instead of a separate relation table in batch-6.
- Bilibili credentials are stored outside business tables through a dedicated auth helper in the runtime data area.

## Backend Architecture

### Layers

```text
domain/entities/video_summary.py
domain/repositories/video_summary_repository.py
infrastructure/bilibili/{client,payloads,exceptions,auth,asr}.py
infrastructure/persistence/repositories/video_summary_repo_impl.py
application/services/video_service.py
skills/video/{provider,tools}.py
api/models/video_models.py
api/routers/{videos,bilibili_auth}.py
```

### Responsibilities

- `BilibiliClient`: platform-specific reads, BV parsing, subtitle/audio/metadata access, payload normalization, third-party exception mapping.
- `BilibiliAuthManager`: QR login lifecycle, credential persistence, status query, logout.
- `AsrPipeline`: audio download, segmentation, GLM-ASR transcription, progress updates.
- `VideoService`: business orchestration, dedupe rules, CRUD, notebook/document association, transcript persistence, summary generation.
- `VideoSkillProvider`: slash-command runtime manifest and tool definitions for `/video`.
- `videos.py`: REST/SSE boundary only. No business orchestration in the router.

### Runtime Rules

- Existing `completed` summary for the same `platform + video_id`: reuse and emit `done(reused=true)`.
- Existing `failed` summary: reset and retry.
- Existing `processing` summary: return conflict and do not start a second pipeline.
- SSE is abstracted behind `progress_callback`, not hard-coded into service code.

## Frontend Architecture

### Studio Views

- Extend `StudioView` with `videos` and `video-detail`.
- Add `activeVideoId`, `openVideoDetail`, and `backToVideoList` to the shared Studio store.

### Components

```text
components/studio/video-list.tsx
components/studio/video-detail.tsx
components/studio/video-input-area.tsx
components/studio/video-list-item.tsx
components/studio/video-info-header.tsx
components/studio/video-action-bar.tsx
components/studio/bilibili-login-dialog.tsx
```

### State Boundaries

Use React Query for:

- summary lists
- summary detail
- login status
- mutations

Use local component state for:

- URL input
- SSE step state
- login dialog visibility
- list filter mode
- inline errors

### Frontend Reuse Decisions

- Reuse `MarkdownViewer` for summary detail rendering.
- Reuse `ConfirmDialog` for delete flows.
- Add a shared SSE parser helper for summary and QR login streams.
- Add `/video` to the slash command hint and invalidate video queries after `/video` tool execution completes.

## Verification Strategy

### Automated

- Backend unit tests for repository, client, ASR, service, router, and skill provider.
- Frontend Vitest/RTL coverage for Video components, hooks, store changes, and slash-command integration.

### Manual but Repeatable

- Start FastAPI locally.
- Start Next.js locally.
- Drive real browser flows through Playwright MCP:
  - summarize a public video
  - summarize an ASR fallback video
  - load list/detail
  - associate/disassociate notebook
  - delete summary
  - trigger `/video` from chat and confirm Video panel refresh
  - verify Bilibili login flow or its clear failure state

## Delivery Order

1. Branch and workspace setup
2. Design and implementation docs
3. Backend schema/domain/repository
4. Bilibili infrastructure and auth
5. Video service
6. Video routers and skill provider
7. Frontend data layer
8. Frontend Studio UI
9. `/video` chat integration
10. End-to-end verification and merge preparation
