# Video Batch-6 Implementation Plan

## Purpose

This file is the batch-6 execution companion for the existing backend/frontend design docs. It records the unified contract decisions, the delivery sequence, the main technical risks, and the acceptance checklist used during implementation.

The detailed task-by-task implementation plan lives at:

- `docs/plans/2026-03-27-video-studio-implementation.md`

The design summary for this execution round lives at:

- `docs/plans/2026-03-27-video-studio-design.md`

## Unified Decisions

### API and SSE

- Video summarize uses `POST /api/v1/videos/summarize` and returns SSE directly.
- Bilibili QR login uses `GET /api/v1/bilibili/auth/qr` and returns SSE directly.
- Summary progress events are `start`, `info`, `subtitle`, `asr`, `summarize`, `done`, and `error`.
- QR login events are `qr_generated`, `scanned`, `done`, `timeout`, and `error`.

### Persistence

- `video_summaries` stores summary metadata and Markdown content.
- Transcript content is stored in object storage and referenced by `transcript_path`.
- Notebook association is optional through `notebook_id`.
- Document association is stored as `UUID[]` in `document_ids`.

### Runtime

- `/video` is explicit slash-command activation only.
- Studio panel summarize and `/video` tool calls both go through `VideoService`.
- Existing completed summaries are reused.
- Existing processing summaries are rejected instead of duplicated.

## Delivery Sequence

1. Branch/worktree setup
2. Design and implementation documents
3. Backend schema and repository
4. Bilibili infrastructure and auth
5. Video service
6. Video API and runtime skill
7. Frontend data layer
8. Frontend Studio views
9. Chat `/video` refresh integration
10. Live end-to-end verification

## Risks

- Third-party Bilibili payload drift
- Videos that require login for subtitle or audio access
- Long-running ASR summaries inside a request/stream lifecycle
- Duplicated logic between summary SSE and QR SSE if the parser/helper layer is not shared
- Studio panel regressions if Video UI is added directly inside the existing large panel component

## Acceptance Checklist

- Backend unit coverage exists for repository, client, ASR pipeline, service, routers, and skill tools.
- Frontend Vitest coverage exists for store, hooks, Video views, and `/video` slash hint behavior.
- FastAPI starts locally with the new routers enabled.
- Next.js starts locally with the Video panel mounted in Studio.
- Playwright MCP verifies:
  - public video summarize
  - ASR fallback summarize
  - list to detail navigation
  - notebook association and removal
  - summary deletion
  - `/video` agent-triggered refresh
  - Bilibili login flow or clear failure UX
