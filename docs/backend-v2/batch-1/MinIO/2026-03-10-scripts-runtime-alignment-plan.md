# Scripts Runtime Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align database and operational scripts with the MinIO-backed runtime so fresh installs and rebuild tooling match current production behavior.

**Architecture:** Keep migration and cleanup scripts that still serve production or recovery flows, but remove filesystem-as-source-of-truth assumptions from runtime rebuild scripts. Rebuild scripts should enumerate rebuildable documents from the database, materialize markdown content from runtime storage, and write only to the target index store. Database bootstrap scripts must match ORM/runtime tables exactly.

**Tech Stack:** Python, pytest, PostgreSQL init SQL, MinIO storage backend, SQLAlchemy repository layer, LlamaIndex pgvector/Elasticsearch stores

---

### Task 1: Capture Regressions With Tests

**Files:**
- Create: `newbee_notebook/tests/unit/test_db_init_script.py`
- Modify: `newbee_notebook/tests/unit/test_embedding_provider_and_rebuild.py`

**Step 1: Write failing tests**

- Assert `newbee_notebook/scripts/db/init-postgres.sql` declares `sessions` and `notebook_document_refs`.
- Assert rebuild scripts no longer depend on `documents_dir`, rebuild from database-provided documents, and close store resources.

**Step 2: Run tests to verify they fail**

Run:

```bash
pytest newbee_notebook/tests/unit/test_db_init_script.py newbee_notebook/tests/unit/test_embedding_provider_and_rebuild.py -q
```

Expected: failures because the init SQL is missing tables and rebuild scripts still expect filesystem input.

**Step 3: Write minimal implementation**

- Add the missing SQL table definitions.
- Update rebuild script APIs and orchestration to use runtime document enumeration and node loading.

**Step 4: Run tests to verify they pass**

Run the same pytest command and expect all green.

### Task 2: Repair Database Bootstrap Drift

**Files:**
- Modify: `newbee_notebook/scripts/db/init-postgres.sql`
- Modify: `newbee_notebook/scripts/db/README.md`

**Step 1: Add missing runtime tables**

- Add `sessions`.
- Add `notebook_document_refs`.
- Keep indexes/constraints aligned with ORM models.

**Step 2: Fix README claims**

- Document the real created tables.
- Clarify first-run semantics and manual execution.

**Step 3: Re-run SQL regression tests**

```bash
pytest newbee_notebook/tests/unit/test_db_init_script.py -q
```

Expected: pass.

### Task 3: Rewrite Index Rebuild Scripts For DB + MinIO

**Files:**
- Create: `newbee_notebook/scripts/rebuild_common.py`
- Modify: `newbee_notebook/scripts/rebuild_es.py`
- Modify: `newbee_notebook/scripts/rebuild_pgvector.py`
- Test: `newbee_notebook/tests/unit/test_embedding_provider_and_rebuild.py`

**Step 1: Add shared runtime helpers**

- Enumerate rebuildable documents from DB with statuses `converted` and `completed`.
- Load document nodes from `content_path` using runtime storage-backed markdown loading.

**Step 2: Update Elasticsearch rebuild**

- Remove `documents_dir` source-of-truth semantics.
- Keep `--clear-only`.
- Rebuild using DB documents and close Elasticsearch resources.

**Step 3: Update pgvector rebuild**

- Keep provider selection.
- Remove `documents_dir` source-of-truth semantics.
- Rebuild using DB documents and close pgvector resources.

**Step 4: Run focused tests**

```bash
pytest newbee_notebook/tests/unit/test_embedding_provider_and_rebuild.py -q
```

Expected: pass.

### Task 4: Align Cleanup Script Wording With MinIO Runtime

**Files:**
- Modify: `newbee_notebook/scripts/clean_orphan_documents.py`

**Step 1: Update CLI copy**

- Change filesystem-centric help/output to storage-centric wording when runtime backend is not local.

**Step 2: Run targeted regression**

```bash
pytest newbee_notebook/tests/unit/test_detect_orphans_storage.py -q
```

Expected: existing tests remain green.

### Task 5: Verify End-to-End Script Health

**Files:**
- Verify only

**Step 1: Run focused regression suite**

```bash
pytest newbee_notebook/tests/unit/test_db_init_script.py newbee_notebook/tests/unit/test_embedding_provider_and_rebuild.py newbee_notebook/tests/unit/test_detect_orphans_storage.py -q
```

**Step 2: Run broader scripts/storage regression**

```bash
pytest newbee_notebook/tests/unit/test_migrate_to_minio_script.py newbee_notebook/tests/unit/test_storage_write_through.py newbee_notebook/tests/unit/test_document_tasks_storage_reads.py -q
```

**Step 3: Summarize remaining risks**

- Archived historical docs may still mention local-path workflows as past state; these references should remain clearly labeled as historical context.
- Manual operator docs outside batch-1 scope may still need a separate cleanup pass if they are still intended to guide current production.
