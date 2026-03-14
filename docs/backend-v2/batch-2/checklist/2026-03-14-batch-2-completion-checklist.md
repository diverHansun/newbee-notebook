## Batch-2 Completion Checklist

Scope: `backend-v2/batch-2`
Feature branch: `stage/backend-v2-batch-2-core`
Base branch: `stage/backend-v2`
Date: `2026-03-14`

### 1. Scope Freeze

- [x] Canonical main-panel mode is `agent`
- [x] `chat` kept only as API compatibility alias
- [x] `ask` migrated to new runtime
- [x] `explain` migrated to retrieval-required runtime
- [x] `conclude` migrated to retrieval-required runtime
- [x] Legacy `core/agent`, `core/memory`, old mode-selector runtime removed
- [x] MCP integrated for `agent` only
- [x] Frontend main panel updated to `Agent / Ask`

### 2. Runtime Architecture

- [x] OpenAI SDK-compatible `LLMClient` introduced
- [x] Provider-specific thinking disabled for tool-using runtime requests
- [x] Request-scoped runtime messages separated from persistent business messages
- [x] Dual-track context/session runtime introduced
- [x] Policy-driven engine loop introduced
- [x] Unified runtime tool contracts introduced
- [x] Unified `knowledge_base` tool introduced

### 3. Retrieval and Indexing

- [x] Embedding runtime config synced from DB/runtime config
- [x] Local `qwen3-embedding` path resolved against project root `models/`
- [x] Rebuild/index scripts aligned with runtime configuration source
- [x] Live reindex of `7a0f8660-a73b-4659-a710-d831be756a05` completed successfully
- [x] Current pgvector rows restored (`805`)
- [x] Current Elasticsearch docs restored (`805`)

### 4. MCP

- [x] MCP config moved to repository-level `configs/mcp.json`
- [x] Only `stdio + Streamable HTTP` supported
- [x] Tool names normalized as `server_tool`
- [x] Global and per-server enable switches support immediate disconnect
- [x] Real Firecrawl MCP connected and verified
- [x] MCP control panel added to frontend
- [x] MCP acceptance checklist documented

### 5. API and Frontend

- [x] `postman_collection.json` updated for batch-2 runtime/API changes
- [x] Main panel mode labels updated from `Chat` to `Agent`
- [x] `ask` and `agent` real notebook queries verified against document content
- [x] `explain` and `conclude` live notebook/document flow verified
- [x] Settings panel and MCP panel verified through frontend

### 6. Verification Evidence

- [x] Backend targeted unit/integration suites passed during implementation
- [x] Frontend `pnpm typecheck` passed on batch-2-core branch
- [x] Live API verification passed for:
  - `agent`
  - `ask`
  - `explain`
  - `conclude`
  - MCP settings/status endpoints
- [x] Playwright verification passed for:
  - `Agent / Ask` labels
  - `Ask` content response on real notebook
  - `Agent` content response on real notebook
  - MCP control panel status and toggles

### 7. Known Residual Risks

- [ ] Upstream LLM provider may return transient network errors
  - Current observed case: Zhipu temporary `500 / code 1234`
  - Status: retry succeeds, not treated as batch-2 blocker
- [ ] `chat` alias still exists at API layer for compatibility
  - Status: expected, not a separate runtime mode

### 8. Merge Readiness

- [x] Feature branch contains only intended batch-2-core commits
- [x] Worktree code is clean except untracked `docs/backend-v2/batch-2/implement/`
- [x] Batch-2 completion checklist written
- [x] Code review completed with no blocking findings
- [x] Merged into `stage/backend-v2`
- [x] Batch-2 marked complete on base branch history

