# Batch-2 MCP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an Anthropic/MCP-aligned client layer for `agent` mode using repo-level `configs/mcp.json`, supporting only `stdio` and `Streamable HTTP`, with runtime enable/disable switches and agent-only tool injection.

**Architecture:** Keep the existing runtime contracts (`ToolDefinition`, `ToolRegistry`, `SessionManager`) and replace the current placeholder MCP layer with a protocol-aligned async manager. Server definitions live in `configs/mcp.json`; AppSettings stores only total/server enable flags. MCP tools are exposed to `agent` only, using qualified names like `filesystem_read_file`, and disabled servers disconnect immediately.

**Tech Stack:** FastAPI, pytest, MCP Python SDK, OpenAI-compatible runtime, AppSettings DB, repo-level JSON config

---

## Scope

### In Scope
- Repo-level MCP config file path: `configs/mcp.json`
- `stdio + Streamable HTTP` transports only
- Environment variable expansion: `${VAR}` and `${VAR:-default}`
- `agent`-only MCP tool injection
- Runtime status API for MCP servers
- Immediate disconnect on total/server disable
- Backend tests and live backend smoke

### Out of Scope
- Legacy SSE transport
- Frontend JSON editor for MCP config
- MCP for `ask / explain / conclude`
- Skill integration
- Rich MCP resource/image handling beyond text content passthrough

---

### Task 1: Align Config Path and Data Model

**Files:**
- Modify: `newbee_notebook/core/mcp/config.py`
- Modify: `newbee_notebook/core/mcp/types.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Test: `newbee_notebook/tests/unit/core/mcp/test_config.py`
- Test: `newbee_notebook/tests/unit/core/mcp/test_client_manager.py`

**Step 1: Write the failing tests**

Add tests for:
- repo-level `configs/mcp.json` path usage in dependencies
- config parsing for `stdio` and `streamable-http`
- `${VAR}` / `${VAR:-default}` expansion
- invalid transport rejection
- qualified tool names use `server_tool`, not `server__tool`

**Step 2: Run tests to verify they fail**

Run:
```bash
pytest newbee_notebook/tests/unit/core/mcp/test_config.py newbee_notebook/tests/unit/core/mcp/test_client_manager.py -v
```

Expected:
- missing tests/modules or assertion failures for current `.mcp.json` path and old naming

**Step 3: Write minimal implementation**

Implement:
- config path helper returning `configs/mcp.json`
- transport normalization to `stdio` and `streamable-http`
- updated `MCPServerConfig`
- tool qualified-name builder: `{server_name}_{tool_name}`

**Step 4: Run tests to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/mcp/test_config.py newbee_notebook/tests/unit/core/mcp/test_client_manager.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/mcp/config.py newbee_notebook/core/mcp/types.py newbee_notebook/api/dependencies.py newbee_notebook/tests/unit/core/mcp/test_config.py newbee_notebook/tests/unit/core/mcp/test_client_manager.py
git commit -m "feat(mcp): align config path and naming with runtime"
```

---

### Task 2: Make MCP Manager Async and Agent-Only

**Files:**
- Modify: `newbee_notebook/core/mcp/client_manager.py`
- Modify: `newbee_notebook/core/tools/registry.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Test: `newbee_notebook/tests/unit/core/mcp/test_client_manager.py`
- Test: `newbee_notebook/tests/unit/core/tools/test_tool_registry.py`

**Step 1: Write the failing tests**

Add tests for:
- `ToolRegistry.get_tools()` becoming async
- MCP tools injected only for `agent`
- total/server disable immediately disconnects and removes tools
- cached tools do not reconnect repeatedly

**Step 2: Run tests to verify they fail**

Run:
```bash
pytest newbee_notebook/tests/unit/core/mcp/test_client_manager.py newbee_notebook/tests/unit/core/tools/test_tool_registry.py -v
```

Expected:
- failures due to current sync supplier behavior

**Step 3: Write minimal implementation**

Implement:
- async `ToolRegistry.get_tools(...)`
- async MCP manager lifecycle
- immediate disconnect on disable
- dependency updates for async registry fetch

**Step 4: Run tests to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/mcp/test_client_manager.py newbee_notebook/tests/unit/core/tools/test_tool_registry.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/mcp/client_manager.py newbee_notebook/core/tools/registry.py newbee_notebook/api/dependencies.py newbee_notebook/tests/unit/core/mcp/test_client_manager.py newbee_notebook/tests/unit/core/tools/test_tool_registry.py
git commit -m "refactor(mcp): add async manager lifecycle and agent-only injection"
```

---

### Task 3: Add MCP Status API

**Files:**
- Modify: `newbee_notebook/api/routers/config.py`
- Modify: `newbee_notebook/api/models/responses.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Test: `newbee_notebook/tests/unit/test_config_api_endpoints.py`

**Step 1: Write the failing tests**

Add tests for:
- `GET /api/v1/settings/mcp/servers`
- response shape includes:
  - `mcp_enabled`
  - `servers[]`
  - `name / transport / enabled / connection_status / tool_count / error_message`

**Step 2: Run tests to verify they fail**

Run:
```bash
pytest newbee_notebook/tests/unit/test_config_api_endpoints.py -k mcp -v
```

Expected: FAIL because endpoint/response do not exist

**Step 3: Write minimal implementation**

Implement:
- MCP status response models
- config/settings route for server statuses
- dependency plumbing to read manager statuses plus DB switches

**Step 4: Run tests to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/test_config_api_endpoints.py -k mcp -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/api/routers/config.py newbee_notebook/api/models/responses.py newbee_notebook/api/dependencies.py newbee_notebook/tests/unit/test_config_api_endpoints.py
git commit -m "feat(mcp): add runtime status settings endpoint"
```

---

### Task 4: Wire Real MCP SDK Connectors

**Files:**
- Modify: `pyproject.toml`
- Modify: `newbee_notebook/core/mcp/client_manager.py`
- Create: `newbee_notebook/core/mcp/connectors.py`
- Test: `newbee_notebook/tests/unit/core/mcp/test_connectors.py`
- Test: `newbee_notebook/tests/integration/core/mcp/test_mcp_protocol.py`

**Step 1: Write the failing tests**

Add tests for:
- connector factory selects `stdio` vs `streamable-http`
- manager calls `initialize` + `tools/list`
- integration test against a minimal MCP test server process

**Step 2: Run tests to verify they fail**

Run:
```bash
pytest newbee_notebook/tests/unit/core/mcp/test_connectors.py newbee_notebook/tests/integration/core/mcp/test_mcp_protocol.py -v
```

Expected: FAIL because real connectors do not exist

**Step 3: Write minimal implementation**

Implement:
- `mcp` dependency
- connector wrapper around MCP SDK client transports
- initialize/list-tools handshake

**Step 4: Run tests to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/mcp/test_connectors.py newbee_notebook/tests/integration/core/mcp/test_mcp_protocol.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml newbee_notebook/core/mcp/client_manager.py newbee_notebook/core/mcp/connectors.py newbee_notebook/tests/unit/core/mcp/test_connectors.py newbee_notebook/tests/integration/core/mcp/test_mcp_protocol.py
git commit -m "feat(mcp): add stdio and streamable-http connectors"
```

---

### Task 5: Backend Smoke and Live Verification

**Files:**
- Test only / no product code unless failures reveal a real bug

**Step 1: Run focused MCP suite**

Run:
```bash
pytest newbee_notebook/tests/unit/core/mcp newbee_notebook/tests/unit/core/tools/test_tool_registry.py newbee_notebook/tests/unit/test_config_api_endpoints.py -v
```

**Step 2: Run live backend smoke**

Verify:
- `GET /api/v1/settings/mcp/servers`
- `mcp.enabled=false` -> no MCP tools in agent
- `mcp.enabled=true` with one configured server -> MCP tools appear for `agent`
- `ask / explain / conclude` still do not get MCP tools

**Step 3: Commit**

```bash
git add -A
git commit -m "test(mcp): verify backend mcp slice end to end"
```

---

## Verification Gates

### Focused backend MCP suite

```bash
pytest newbee_notebook/tests/unit/core/mcp newbee_notebook/tests/unit/core/tools/test_tool_registry.py newbee_notebook/tests/unit/test_config_api_endpoints.py -v
```

### Integration

```bash
pytest newbee_notebook/tests/integration/core/mcp/test_mcp_protocol.py -v
```

### Manual checks

1. `configs/mcp.json` missing -> MCP silently disabled, no crash
2. `${VAR}` missing without default -> config parse error surfaced in status endpoint
3. `mcp.enabled=false` -> manager disconnects active servers immediately
4. `agent` gets MCP tools, `ask/explain/conclude` do not
5. tool names are prefixed as `server_tool`

