## Goal

Finish the next MinIO migration stage in two commits:

1. Phase 1: remove runtime API/service dependence on `data/documents`
2. Phase 2: move worker source/content reads to MinIO-backed temp files

`LocalStorageBackend` remains for unit tests and offline scripts only.

## Phase 1 Scope

- `DocumentService` runtime paths become MinIO-only
- hard delete removes MinIO objects by prefix instead of deleting local document trees
- remove unused local-path helpers from `DocumentService`
- refresh unit tests so converted/completed content is read only from storage backend

Out of scope:

- upload write-through helper
- worker conversion/indexing source reads

## Phase 2 Scope

- `document_tasks.py` stops resolving source/content from `data/documents`
- worker downloads original files and markdown files from runtime storage into temp files
- conversion and indexing continue to use local temp files only during task execution
- add focused unit tests for temp download flow

Out of scope:

- removing local working files produced during upload/conversion helpers
- changing offline migration scripts

## Risks

- large files should not be read fully into memory during worker download
- temp files must be cleaned after conversion/indexing
- legacy `documents/...` object keys still need to resolve correctly

## Verification

- targeted unit tests for `DocumentService`
- targeted unit tests for `document_tasks`
- broader regression on storage/document tests after both phases
