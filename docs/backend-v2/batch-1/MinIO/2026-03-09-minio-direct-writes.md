# MinIO Direct Writes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove upload/markdown write-through to `data/documents` so runtime persistence goes directly to MinIO, while worker-local temp files remain only for task execution.

**Architecture:** Keep the existing local-only helpers for unit tests and offline workflows, but change the runtime helpers `save_upload_file_with_storage()` and `save_markdown_with_storage()` to write directly to the runtime storage backend. Reuse the current filename decoding and markdown image-rewrite logic so persisted object keys and markdown content stay stable.

**Tech Stack:** Python, FastAPI `UploadFile`, MinIO storage backend abstraction, pytest

---

### Task 1: Upload Direct-To-Storage

**Files:**
- Modify: `newbee_notebook/infrastructure/storage/local_storage.py`
- Test: `newbee_notebook/tests/unit/test_storage_write_through.py`

**Step 1: Write the failing test**

Add a test that:
- calls `save_upload_file_with_storage()`
- asserts the backend receives `save_file()` with the upload bytes
- asserts no file is created under the provided `base_root`

**Step 2: Run test to verify it fails**

Run:
```bash
pytest newbee_notebook/tests/unit/test_storage_write_through.py -k upload -v
```

Expected: FAIL because the current code writes a local file and uses `save_from_path()`.

**Step 3: Write minimal implementation**

Change `save_upload_file_with_storage()` to:
- decode and validate filename/extension without creating a local file
- build the stable object key `{document_id}/original/{filename}`
- stream the upload directly via `backend.save_file()`
- compute size from the in-memory payload

Keep `save_upload_file()` unchanged for local-only callers.

**Step 4: Run test to verify it passes**

Run:
```bash
pytest newbee_notebook/tests/unit/test_storage_write_through.py -k upload -v
```

Expected: PASS

### Task 2: Markdown/Asset Direct-To-Storage

**Files:**
- Modify: `newbee_notebook/infrastructure/document_processing/store.py`
- Test: `newbee_notebook/tests/unit/test_storage_write_through.py`

**Step 1: Write the failing test**

Add a test that:
- calls `save_markdown_with_storage()`
- asserts markdown/image/meta are written with `save_file()`
- asserts rewritten markdown content is what gets uploaded
- asserts no files are created under the provided `base_root`

**Step 2: Run test to verify it fails**

Run:
```bash
pytest newbee_notebook/tests/unit/test_storage_write_through.py -k markdown -v
```

Expected: FAIL because the current code writes local files and uses `save_from_path()`.

**Step 3: Write minimal implementation**

Refactor `store.py` so the markdown normalization/image rewrite logic can be reused without local persistence, then have `save_markdown_with_storage()`:
- build rewritten markdown in memory
- upload `content.md`, image assets, and metadata assets directly with `save_file()`
- keep `save_markdown()` unchanged for local-only tests/offline flows

**Step 4: Run test to verify it passes**

Run:
```bash
pytest newbee_notebook/tests/unit/test_storage_write_through.py -k markdown -v
```

Expected: PASS

### Task 3: Regression Verification

**Files:**
- Verify: `newbee_notebook/application/services/document_service.py`
- Verify: `newbee_notebook/infrastructure/tasks/document_tasks.py`
- Verify: `newbee_notebook/tests/unit/test_document_tasks_storage_reads.py`
- Verify: `newbee_notebook/tests/unit/test_document_service_storage_reads.py`

**Step 1: Run focused regression**

Run:
```bash
pytest \
  newbee_notebook/tests/unit/test_storage_write_through.py \
  newbee_notebook/tests/unit/test_document_service_storage_reads.py \
  newbee_notebook/tests/unit/test_document_tasks_storage_reads.py \
  newbee_notebook/tests/unit/test_document_processing_store.py -v
```

Expected: PASS

**Step 2: Run broader batch-1 regression**

Run:
```bash
pytest \
  newbee_notebook/tests/unit/test_document_processing_processor.py \
  newbee_notebook/tests/unit/infrastructure/storage/test_storage_backend_factory.py \
  newbee_notebook/tests/unit/test_storage_write_through.py \
  newbee_notebook/tests/unit/test_document_service_storage_reads.py \
  newbee_notebook/tests/unit/test_document_service_content_guard.py \
  newbee_notebook/tests/unit/test_notebook_document_service_actions.py \
  newbee_notebook/tests/unit/test_documents_router_storage_redirects.py \
  newbee_notebook/tests/unit/test_migrate_to_minio_script.py \
  newbee_notebook/tests/unit/test_detect_orphans_storage.py \
  newbee_notebook/tests/unit/infrastructure/storage/test_local_storage_backend.py \
  newbee_notebook/tests/unit/test_document_tasks_pipeline_controls.py \
  newbee_notebook/tests/unit/test_document_tasks_storage_reads.py -v
```

Expected: PASS
