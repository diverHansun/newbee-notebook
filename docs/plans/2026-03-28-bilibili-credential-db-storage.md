# Bilibili Credential DB Storage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move Bilibili login credential persistence from `configs/bilibili/credential.json` into the existing `app_settings` table without changing the external auth API behavior.

**Architecture:** Reuse the existing `app_settings` key-value table with a single `bilibili.credential` JSON blob. `BilibiliAuthManager` becomes request-scoped and database-backed, while preserving legacy file migration from `configs/bilibili/credential.json` for existing local environments.

**Tech Stack:** FastAPI, SQLAlchemy async session, existing `AppSettingsService`, `bilibili_api`, pytest.

---

### Task 1: Lock credential storage behavior with failing tests

**Files:**
- Modify: `newbee_notebook/tests/unit/core/common/test_config_db.py`
- Modify: `newbee_notebook/tests/unit/infrastructure/bilibili/test_auth.py`
- Modify: `newbee_notebook/tests/unit/test_bilibili_auth_router.py`

**Step 1: Write the failing tests**

Add tests for:
- `get_bilibili_credential_async()` reading a JSON blob from `app_settings`
- `save_bilibili_credential_async()` normalizing payload and storing one `bilibili.credential` value
- `BilibiliAuthManager` migrating a legacy `credential.json` file into DB on first read
- auth router status / logout still working with async manager methods

**Step 2: Run tests to verify they fail**

Run:
```bash
pytest newbee_notebook/tests/unit/core/common/test_config_db.py newbee_notebook/tests/unit/infrastructure/bilibili/test_auth.py newbee_notebook/tests/unit/test_bilibili_auth_router.py -q
```

Expected: failures for missing Bilibili DB credential helpers and mismatched async auth manager API.

**Step 3: Commit**

Do not commit yet. This task intentionally leaves the tree red.

### Task 2: Implement database-backed credential helpers

**Files:**
- Modify: `newbee_notebook/core/common/config_db.py`

**Step 1: Write minimal implementation**

Add:
- a constant key for `bilibili.credential`
- `async def get_bilibili_credential_async(session)`
- `async def save_bilibili_credential_async(session, payload)`
- `async def delete_bilibili_credential_async(session)`

Behavior:
- read/write through `AppSettingsService`
- normalize payload to the six credential fields only
- return `None` when no stored credential exists

**Step 2: Run targeted tests**

Run:
```bash
pytest newbee_notebook/tests/unit/core/common/test_config_db.py -q
```

Expected: PASS.

**Step 3: Commit**

```bash
git add newbee_notebook/core/common/config_db.py newbee_notebook/tests/unit/core/common/test_config_db.py
git commit -m "feat(bilibili): add db-backed credential helpers"
```

### Task 3: Swap auth manager from file storage to DB storage

**Files:**
- Modify: `newbee_notebook/infrastructure/bilibili/auth.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Modify: `newbee_notebook/api/routers/bilibili_auth.py`
- Modify: `newbee_notebook/tests/unit/infrastructure/bilibili/test_auth.py`
- Modify: `newbee_notebook/tests/unit/test_bilibili_auth_router.py`

**Step 1: Write minimal implementation**

Change `BilibiliAuthManager` to:
- accept `AsyncSession`
- load/save/delete credentials through the new `config_db` helpers
- lazily migrate legacy `configs/bilibili/credential.json` into DB if DB is empty
- delete the legacy file after a successful migration
- keep QR login flow unchanged except awaiting DB save

Change FastAPI dependencies/routes to:
- provide a request-scoped manager
- await `load_credential()`, `clear_credential()`, and `stream_qr_login()`
- build `BilibiliClient` from awaited credential reads

**Step 2: Run targeted tests**

Run:
```bash
pytest newbee_notebook/tests/unit/infrastructure/bilibili/test_auth.py newbee_notebook/tests/unit/test_bilibili_auth_router.py -q
```

Expected: PASS.

**Step 3: Commit**

```bash
git add newbee_notebook/infrastructure/bilibili/auth.py newbee_notebook/api/dependencies.py newbee_notebook/api/routers/bilibili_auth.py newbee_notebook/tests/unit/infrastructure/bilibili/test_auth.py newbee_notebook/tests/unit/test_bilibili_auth_router.py
git commit -m "refactor(bilibili): store auth credential in app settings"
```

### Task 4: Run integration-level verification and summarize schema impact

**Files:**
- Optional docs note only if needed

**Step 1: Run regression tests**

Run:
```bash
pytest newbee_notebook/tests/unit/core/common/test_config_db.py newbee_notebook/tests/unit/infrastructure/bilibili/test_auth.py newbee_notebook/tests/unit/test_bilibili_auth_router.py newbee_notebook/tests/unit/api/test_dependencies_asr.py newbee_notebook/tests/unit/application/services/test_video_service.py -q
```

Run:
```bash
uv pip check --python .venv/Scripts/python.exe
```

Expected: all tests pass and dependency check remains green.

**Step 2: Confirm schema decision**

Document in the final handoff that:
- no new table or column was required
- `app_settings` already supports this storage model
- `init-postgres.sql` and migration SQL therefore do not need schema changes for this feature

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(bilibili): finish credential db migration"
```
