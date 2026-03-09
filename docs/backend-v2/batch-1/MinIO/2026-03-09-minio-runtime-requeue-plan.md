# MinIO Runtime And Notebook Requeue Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make runtime document storage MinIO-only while keeping `LocalStorageBackend` for tests/scripts, and make failed Library documents re-queued correctly when re-added to a notebook.

**Architecture:** Runtime service code will stop branching on `LocalStorageBackend` and will instead resolve a dedicated runtime storage backend that must be MinIO. Upload/conversion helpers will still keep local working files for the existing processing pipeline, but MinIO becomes the only supported runtime storage/read path. Notebook association will mark failed documents as queued before dispatching work so the UI and task state stay consistent.

**Tech Stack:** FastAPI, Celery, SQLAlchemy async repositories, MinIO Python SDK, pytest

---

### Task 1: Add Failing Tests For Runtime Storage Boundary

**Files:**
- Modify: `newbee_notebook/tests/unit/infrastructure/storage/test_storage_backend_factory.py`
- Modify: `newbee_notebook/tests/unit/test_document_service_storage_reads.py`

**Step 1: Write the failing test**
- Add a test asserting runtime storage rejects `STORAGE_BACKEND=local`
- Add a test asserting runtime document reads call the runtime storage resolver rather than the generic backend factory

**Step 2: Run test to verify it fails**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests/unit/infrastructure/storage/test_storage_backend_factory.py newbee_notebook/tests/unit/test_document_service_storage_reads.py
```

**Step 3: Write minimal implementation**
- Add a dedicated runtime MinIO resolver
- Switch runtime read paths to it

**Step 4: Run test to verify it passes**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests/unit/infrastructure/storage/test_storage_backend_factory.py newbee_notebook/tests/unit/test_document_service_storage_reads.py
```

### Task 2: Add Failing Tests For Failed Document Requeue

**Files:**
- Modify: `newbee_notebook/tests/unit/test_notebook_document_service_actions.py`

**Step 1: Write the failing test**
- Add a test asserting `FAILED` documents without conversion output are moved to queued state before dispatch
- Add a test asserting `FAILED` documents with conversion output are prepared for re-index dispatch without leaving stale failure state

**Step 2: Run test to verify it fails**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests/unit/test_notebook_document_service_actions.py
```

**Step 3: Write minimal implementation**
- Update `NotebookDocumentService.add_documents()` to persist queued state before dispatching background tasks

**Step 4: Run test to verify it passes**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests/unit/test_notebook_document_service_actions.py
```

### Task 3: Implement Runtime MinIO-Only Storage Flow

**Files:**
- Modify: `newbee_notebook/infrastructure/storage/__init__.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Modify: `newbee_notebook/application/services/document_service.py`
- Modify: `newbee_notebook/infrastructure/storage/local_storage.py`
- Modify: `newbee_notebook/infrastructure/document_processing/store.py`
- Modify: `newbee_notebook/api/routers/documents.py`

**Step 1: Write minimal implementation**
- Add `get_runtime_storage_backend()`
- Update runtime upload/read/download/asset paths to use MinIO runtime storage
- Remove runtime `FileResponse` fallback for download/assets

**Step 2: Run focused tests**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests/unit/test_storage_write_through.py newbee_notebook/tests/unit/test_documents_router_storage_redirects.py newbee_notebook/tests/unit/test_document_service_storage_reads.py
```

### Task 4: Verify Notebook Requeue And Docker Runtime

**Files:**
- No code changes required if previous tasks pass

**Step 1: Recreate affected services**

Run:
```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --force-recreate --no-deps celery-worker mineru-api
```

**Step 2: Verify end-to-end**
- Requeue failed document with admin API
- Remove and re-add document in notebook UI
- Confirm worker logs and document status progress

**Step 3: Run final verification**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests/unit/infrastructure/storage/test_storage_backend_factory.py newbee_notebook/tests/unit/test_notebook_document_service_actions.py newbee_notebook/tests/unit/test_storage_write_through.py newbee_notebook/tests/unit/test_document_service_storage_reads.py newbee_notebook/tests/unit/test_documents_router_storage_redirects.py
```
