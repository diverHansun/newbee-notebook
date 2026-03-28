# Bilibili Credential Storage Migration

## Current State

- Bilibili session credentials (sessdata, bili_jct, buvid3, etc.) are stored as plaintext JSON in `configs/bilibili/credential.json`
- File is written by `BilibiliAuthManager.save_credential()` after QR code login
- File is read by `BilibiliAuthManager.get_credential()` on each API request
- `configs/bilibili/` has been added to `.gitignore` to prevent accidental commit

## Problem

- Credentials are stored in plaintext on disk with no encryption
- File-based storage does not scale to multi-instance deployment
- No expiration tracking or automatic refresh mechanism

## Proposed Migration

Move credential storage from file to database (`app_settings` table) with encryption.

### Design

1. **Storage**: Reuse the existing `app_settings` key-value table with keys prefixed `bilibili.`
2. **Encryption**: Encrypt sensitive fields (sessdata, bili_jct) at rest using Fernet symmetric encryption; derive the key from a machine-specific secret or env var (`CREDENTIAL_ENCRYPTION_KEY`)
3. **API surface**: Keep `BilibiliAuthManager.get_credential()` / `save_credential()` signatures unchanged; swap the file backend for a DB backend internally
4. **Migration**: On startup, if `configs/bilibili/credential.json` exists and DB has no `bilibili.*` keys, auto-migrate the file contents into the DB and remove the file

### Affected Files

| File | Change |
|------|--------|
| `newbee_notebook/infrastructure/bilibili/auth.py` | Replace file read/write with DB read/write + encryption |
| `newbee_notebook/api/dependencies.py` | Pass DB session to auth manager |
| `newbee_notebook/core/common/config_db.py` | Add `get_bilibili_credential_async()` / `save_bilibili_credential_async()` |
| `newbee_notebook/api/routers/bilibili_auth.py` | Adapt to async credential save |

### Out of Scope

- Token auto-refresh (B站 sessdata has a fixed TTL managed by Bilibili, no refresh flow available)
- Multi-user credential isolation (project is single-user)
