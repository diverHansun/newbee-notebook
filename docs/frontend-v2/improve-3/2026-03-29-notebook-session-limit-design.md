# Notebook Session Limit Design

**Date:** 2026-03-29

## Goal

Raise the per-notebook session creation limit from `20` to `50` in the backend while keeping the session list pagination default unchanged at `20`.

## Current State

- The creation limit is enforced by the domain constant `MAX_SESSIONS_PER_NOTEBOOK` in `newbee_notebook/domain/entities/notebook.py`.
- `SessionService.create()` in `newbee_notebook/application/services/session_service.py` checks `count_by_notebook()` and raises `SessionLimitExceededError` when the current count reaches the domain limit.
- API responses in `newbee_notebook/api/routers/sessions.py` and `newbee_notebook/api/routers/chat.py` expose this limit through `max_count` and human-readable error text.
- The session list endpoint uses `limit=20` as a pagination default. This is a separate concern from the notebook creation ceiling and should not change in this patch.

## Decision

Adopt the smallest safe backend patch:

1. Change the notebook session ceiling from `20` to `50`.
2. Keep `GET /notebooks/{id}/sessions` default pagination at `20`.
3. Keep the existing error shape and status code behavior unchanged.
4. Update tests and API docstrings so the runtime contract stays internally consistent.

## Why This Approach

This patch addresses the product need without widening the API surface or introducing runtime configuration. It avoids unnecessary database changes because the limit is not stored in schema or enforced by SQL constraints. It also avoids frontend pagination side effects by leaving the list endpoint behavior unchanged.

## Affected Areas

- Domain rule:
  - `newbee_notebook/domain/entities/notebook.py`
- Session creation enforcement:
  - `newbee_notebook/application/services/session_service.py`
- API descriptions and error detail plumbing:
  - `newbee_notebook/api/routers/sessions.py`
  - `newbee_notebook/api/routers/chat.py`
- Tests covering limit behavior:
  - `newbee_notebook/tests/unit/test_chat_router_sse.py`
  - Any session-service or router tests that assert `20` explicitly

## Non-Goals

- No database migration
- No app-settings driven configurability
- No change to session list pagination defaults
- No frontend behavior change beyond receiving `max_count=50` when the limit is exceeded

## Risks And Mitigations

- Risk: Mixed documentation and runtime behavior if only the constant is changed.
  - Mitigation: Update API docstrings and tests in the same patch.
- Risk: Confusing the list endpoint `limit=20` with the notebook session ceiling.
  - Mitigation: Keep pagination defaults unchanged and call out the distinction in code review and test coverage.

## Acceptance Criteria

- A notebook can create up to `50` sessions.
- Creating the `51st` session returns the existing session-limit error payload with `max_count=50`.
- `GET /notebooks/{id}/sessions` still defaults to `limit=20`.
- Backend unit tests covering session-limit behavior pass.
