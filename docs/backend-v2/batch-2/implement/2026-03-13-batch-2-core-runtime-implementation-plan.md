# Batch-2 Core Runtime Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current LlamaIndex-driven multi-mode runtime with a self-built `llm + context + engine + session + tools` runtime, while preserving API compatibility and phasing migrations mode-by-mode.

**Architecture:** Implement batch-2 as a strangler migration. Keep the public `/chat` API stable, introduce new runtime contracts first, then migrate `agent -> ask -> explain/conclude`, and delete the old `ModeSelector + modes/* + core/agent` stack only after all four modes are running on the new runtime.

**Tech Stack:** FastAPI, Pydantic, OpenAI Python SDK, LlamaIndex (retrieval/vector store/embedding only), pytest, pytest-asyncio

---

## Pre-Development Confirmations

This plan assumes the following implementation choices. Confirm these before code work starts:

1. **Internal mode naming**
   - New runtime uses `agent` as the internal mode name.
   - API keeps accepting `chat` as a compatibility alias.
   - New persisted messages should store `agent` for migrated mode traffic, not `chat`.

2. **Session lifecycle**
   - Do **not** keep a mutable `SessionManager` object cached per session in process memory.
   - Use a **request-scoped SessionManager / RuntimeOrchestrator** that:
     - loads history from repositories
     - builds a fresh `SessionMemory`
     - uses an **app-level `SessionLockManager`** keyed by `session_id`
   - This is safer for FastAPI deployment and avoids hidden in-memory state drift.

3. **Persistence boundary**
   - Persist only business messages (`user` / `assistant`) and references.
   - Do **not** persist `tool_call`, `tool_result`, or `phase` events as first-class DB rows in batch-2.

4. **Compatibility fields**
   - `include_ec_context` remains accepted at the API layer for compatibility during migration, but new runtime ignores it.

5. **MCP scope**
   - MCP integration is a late batch-2 phase and only attaches to `agent`.
   - Do not mix MCP work into the earlier core migration phases.

---

## Delivery Order

Implement in this order:

1. Phase 1: blocking-fix + warning SSE
2. Phase 2: `core/llm`
3. Phase 3: `core/tools`
4. Phase 4: `core/context`
5. Phase 5: `core/engine`
6. Phase 6: `core/session`
7. Phase 7: service + API integration for `agent`
8. Phase 8: `ask` migration
9. Phase 9: `explain / conclude` migration
10. Phase 10: old core cleanup
11. Phase 11: MCP integration

Each phase should end with green targeted tests and one commit.

---

### Task 1: Ship the Independent Blocking Fix First

**Files:**
- Modify: `newbee_notebook/application/services/chat_service.py`
- Modify: `newbee_notebook/api/routers/chat.py`
- Test: `newbee_notebook/tests/unit/test_chat_service_guards.py`
- Test: `newbee_notebook/tests/unit/test_chat_router_sse.py`

**Step 1: Write the failing tests**

Add tests for:
- `ask` is allowed when notebook has both completed and processing documents
- `explain / conclude` block when `context.document_id` points to a non-completed document
- streaming emits `warning` between `start` and `thinking`/compat phase signal

**Step 2: Run tests to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/test_chat_service_guards.py newbee_notebook/tests/unit/test_chat_router_sse.py -v
```

Expected:
- Existing guard tests fail because current `_validate_mode_guard()` blocks too broadly
- SSE tests fail because `warning` is not emitted/formatted yet

**Step 3: Write the minimal implementation**

Implement:
- partial-notebook allowance for `ask`
- target-document readiness check for `explain / conclude`
- `warning` event formatting and passthrough

**Step 4: Run tests to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/test_chat_service_guards.py newbee_notebook/tests/unit/test_chat_router_sse.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/application/services/chat_service.py newbee_notebook/api/routers/chat.py newbee_notebook/tests/unit/test_chat_service_guards.py newbee_notebook/tests/unit/test_chat_router_sse.py
git commit -m "fix(chat): relax notebook blocking and add warning events"
```

---

### Task 2: Introduce the New LLM Config and Client Layer

**Files:**
- Create: `newbee_notebook/core/llm/config.py`
- Create: `newbee_notebook/core/llm/client.py`
- Create: `newbee_notebook/core/llm/factory.py`
- Modify: `newbee_notebook/core/llm/__init__.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Test: `newbee_notebook/tests/unit/core/llm/test_llm_config.py`
- Test: `newbee_notebook/tests/unit/core/llm/test_llm_client.py`

**Step 1: Write the failing tests**

Add tests for:
- provider config resolution from settings/env
- OpenAI-compatible `chat()` parameter mapping
- OpenAI-compatible `chat_stream()` passthrough
- client refresh behavior after model/provider changes

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/core/llm/test_llm_config.py newbee_notebook/tests/unit/core/llm/test_llm_client.py -v
```

Expected: FAIL because files and classes do not exist

**Step 3: Write minimal implementation**

Implement:
- `ProviderConfig`
- `LLMRuntimeConfig`
- `LLMClient`
- `LLMClientFactory`
- dependency provider in `api/dependencies.py`

Minimal public API:
```python
class LLMClient:
    async def chat(self, *, messages: list, tools: list | None = None, tool_choice=None, **kwargs): ...
    async def chat_stream(self, *, messages: list, tools: list | None = None, tool_choice=None, **kwargs): ...
```

**Step 4: Run tests to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/llm/test_llm_config.py newbee_notebook/tests/unit/core/llm/test_llm_client.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/llm newbee_notebook/api/dependencies.py newbee_notebook/tests/unit/core/llm
git commit -m "feat(llm): add runtime client and provider factory"
```

---

### Task 3: Add Unified Tool Contracts

**Files:**
- Create: `newbee_notebook/core/tools/contracts.py`
- Modify: `newbee_notebook/core/tools/__init__.py`
- Test: `newbee_notebook/tests/unit/core/tools/test_tool_contracts.py`

**Step 1: Write the failing tests**

Cover:
- `ToolDefinition` shape
- `ToolCallResult` structure
- `SourceItem` and `ToolQualityMeta`
- MCP compatibility expectations (`sources` optional, `quality_meta` optional)

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/core/tools/test_tool_contracts.py -v
```

Expected: FAIL because contracts module does not exist

**Step 3: Write minimal implementation**

Implement typed structures and exports only. No registry logic yet.

**Step 4: Run test to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/tools/test_tool_contracts.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/tools/contracts.py newbee_notebook/core/tools/__init__.py newbee_notebook/tests/unit/core/tools/test_tool_contracts.py
git commit -m "feat(tools): add runtime tool contracts"
```

---

### Task 4: Build the New Tool Registry and Builtin Provider

**Files:**
- Create: `newbee_notebook/core/tools/registry.py`
- Create: `newbee_notebook/core/tools/builtin_provider.py`
- Modify: `newbee_notebook/core/tools/__init__.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Test: `newbee_notebook/tests/unit/core/tools/test_tool_registry.py`

**Step 1: Write the failing tests**

Cover:
- mode-based tool filtering
- `ask` gets `knowledge_base + time`
- `explain / conclude` get `knowledge_base` only
- `agent` path can merge future MCP tools without changing return type

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/core/tools/test_tool_registry.py -v
```

Expected: FAIL because registry/provider files do not exist

**Step 3: Write minimal implementation**

Implement:
- `BuiltinToolProvider.get_tools(mode)`
- `ToolRegistry.get_tools(mode, mcp_enabled=False)`
- DI stub in `api/dependencies.py`

Use the new `ToolDefinition` protocol, not `BaseTool`.

**Step 4: Run test to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/tools/test_tool_registry.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/tools/registry.py newbee_notebook/core/tools/builtin_provider.py newbee_notebook/core/tools/__init__.py newbee_notebook/api/dependencies.py newbee_notebook/tests/unit/core/tools/test_tool_registry.py
git commit -m "feat(tools): add mode-aware tool registry"
```

---

### Task 5: Implement `knowledge_base` as the Unified Retrieval Tool

**Files:**
- Create: `newbee_notebook/core/tools/knowledge_base.py`
- Modify: `newbee_notebook/core/tools/registry.py`
- Modify: `newbee_notebook/core/tools/builtin_provider.py`
- Test: `newbee_notebook/tests/unit/core/tools/test_knowledge_base_tool.py`

**Step 1: Write the failing tests**

Cover:
- `search_type` routing (`hybrid / semantic / keyword`)
- notebook/document scope binding
- result formatting into `content + sources + quality_meta`
- explain/conclude-specific defaults can be overridden later by policy

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/core/tools/test_knowledge_base_tool.py -v
```

Expected: FAIL because tool does not exist

**Step 3: Write minimal implementation**

Implement:
- `build_knowledge_base_tool(...)`
- retriever routing
- `quality_meta` normalization

**Step 4: Run test to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/tools/test_knowledge_base_tool.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/tools/knowledge_base.py newbee_notebook/core/tools/registry.py newbee_notebook/core/tools/builtin_provider.py newbee_notebook/tests/unit/core/tools/test_knowledge_base_tool.py
git commit -m "feat(tools): add unified knowledge base tool"
```

---

### Task 6: Add Minimal Context Module

**Files:**
- Create: `newbee_notebook/core/context/__init__.py`
- Create: `newbee_notebook/core/context/session_memory.py`
- Create: `newbee_notebook/core/context/budget.py`
- Create: `newbee_notebook/core/context/token_counter.py`
- Create: `newbee_notebook/core/context/compressor.py`
- Create: `newbee_notebook/core/context/context_builder.py`
- Test: `newbee_notebook/tests/unit/core/context/test_session_memory.py`
- Test: `newbee_notebook/tests/unit/core/context/test_context_builder.py`

**Step 1: Write the failing tests**

Cover:
- main/side track isolation
- main injection into explain/conclude reads
- deterministic truncation under budget
- OpenAI-compatible message list output

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/core/context/test_session_memory.py newbee_notebook/tests/unit/core/context/test_context_builder.py -v
```

Expected: FAIL because module files do not exist

**Step 3: Write minimal implementation**

Implement:
- `SessionMemory`
- `ContextBudget`
- `ContextBuilder`
- lightweight `Compressor.truncate()`

Do **not** add async summary in the first pass.

**Step 4: Run test to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/context/test_session_memory.py newbee_notebook/tests/unit/core/context/test_context_builder.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/context newbee_notebook/tests/unit/core/context
git commit -m "feat(context): add dual-track memory and builder"
```

---

### Task 7: Add Stream Events and Mode Config

**Files:**
- Create: `newbee_notebook/core/engine/stream_events.py`
- Create: `newbee_notebook/core/engine/mode_config.py`
- Modify: `newbee_notebook/domain/value_objects/mode_type.py`
- Test: `newbee_notebook/tests/unit/core/engine/test_stream_events.py`
- Test: `newbee_notebook/tests/unit/core/engine/test_mode_config.py`

**Step 1: Write the failing tests**

Cover:
- `ModeType.AGENT` introduction and compatibility handling
- `ModeConfig` builds correct `LoopPolicy` and `ToolPolicy`
- explain/conclude default iteration limits and document scope
- source policy/event enums

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/core/engine/test_stream_events.py newbee_notebook/tests/unit/core/engine/test_mode_config.py -v
```

Expected: FAIL because files or new enum values do not exist

**Step 3: Write minimal implementation**

Implement:
- typed StreamEvent structures
- `ModeConfigFactory`
- internal `agent` mode
- `chat -> agent` compatibility mapping helper

**Step 4: Run test to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/engine/test_stream_events.py newbee_notebook/tests/unit/core/engine/test_mode_config.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/engine/stream_events.py newbee_notebook/core/engine/mode_config.py newbee_notebook/domain/value_objects/mode_type.py newbee_notebook/tests/unit/core/engine/test_stream_events.py newbee_notebook/tests/unit/core/engine/test_mode_config.py
git commit -m "feat(engine): add stream events and mode policies"
```

---

### Task 8: Implement the Runtime Loop

**Files:**
- Create: `newbee_notebook/core/engine/agent_loop.py`
- Modify: `newbee_notebook/core/engine/__init__.py`
- Test: `newbee_notebook/tests/unit/core/engine/test_agent_loop.py`
- Test: `newbee_notebook/tests/unit/core/engine/test_error_recovery.py`

**Step 1: Write the failing tests**

Cover:
- open-loop tool execution
- invalid-tool repair
- explain/conclude retrieval-required loop
- early synthesis by quality gate
- forced synthesis at retrieval limit
- llm retry behavior

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/core/engine/test_agent_loop.py newbee_notebook/tests/unit/core/engine/test_error_recovery.py -v
```

Expected: FAIL because runtime does not exist

**Step 3: Write minimal implementation**

Implement:
- `AgentLoop.stream()`
- `AgentLoop.run()`
- repair path for missing required tool
- final synthesis stage

**Step 4: Run test to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/engine/test_agent_loop.py newbee_notebook/tests/unit/core/engine/test_error_recovery.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/engine/agent_loop.py newbee_notebook/core/engine/__init__.py newbee_notebook/tests/unit/core/engine/test_agent_loop.py newbee_notebook/tests/unit/core/engine/test_error_recovery.py
git commit -m "feat(engine): add policy-driven runtime loop"
```

---

### Task 9: Add Request-Scoped Session Orchestration and App-Level Locks

**Files:**
- Create: `newbee_notebook/core/session/__init__.py`
- Create: `newbee_notebook/core/session/session_manager.py`
- Create: `newbee_notebook/core/session/lock_manager.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Test: `newbee_notebook/tests/unit/core/session/test_lock_manager.py`
- Test: `newbee_notebook/tests/unit/core/session/test_session_manager.py`

**Step 1: Write the failing tests**

Cover:
- lock acquisition per `session_id`
- request-scoped session orchestration builds fresh context from DB history
- no shared mutable in-memory session object across requests
- non-stream result aggregates stream events

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/core/session/test_lock_manager.py newbee_notebook/tests/unit/core/session/test_session_manager.py -v
```

Expected: FAIL because session module does not exist

**Step 3: Write minimal implementation**

Implement:
- `SessionLockManager`
- request-scoped `SessionManager`
- dependency provider for lock manager singleton

**Step 4: Run test to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/session/test_lock_manager.py newbee_notebook/tests/unit/core/session/test_session_manager.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/session newbee_notebook/api/dependencies.py newbee_notebook/tests/unit/core/session
git commit -m "feat(session): add request-scoped orchestration and locks"
```

---

### Task 10: Integrate the New Runtime for `agent`

**Files:**
- Modify: `newbee_notebook/application/services/chat_service.py`
- Modify: `newbee_notebook/api/routers/chat.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Modify: `newbee_notebook/api/models/requests.py`
- Test: `newbee_notebook/tests/unit/test_chat_router_sse.py`
- Test: `newbee_notebook/tests/unit/test_chat_service_guards.py`
- Test: `newbee_notebook/tests/unit/test_chat_engine.py`

**Step 1: Write the failing tests**

Cover:
- `mode=chat` maps internally to `agent`
- `phase` is official stream event, `thinking` remains compatibility mapping only
- non-stream path aggregates event stream
- `agent` mode returns unified sources

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/test_chat_router_sse.py newbee_notebook/tests/unit/test_chat_service_guards.py newbee_notebook/tests/unit/test_chat_engine.py -v
```

Expected: FAIL because services and router still depend on `SessionManager -> ModeSelector`

**Step 3: Write minimal implementation**

Replace:
- old `SessionManager.chat/chat_stream` coupling
- `__PHASE__` marker parsing
- router-local mode semantics

Preserve:
- `/chat` endpoints
- `ChatRequest` shape
- `chat` alias behavior

**Step 4: Run test to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/test_chat_router_sse.py newbee_notebook/tests/unit/test_chat_service_guards.py newbee_notebook/tests/unit/test_chat_engine.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/application/services/chat_service.py newbee_notebook/api/routers/chat.py newbee_notebook/api/dependencies.py newbee_notebook/api/models/requests.py newbee_notebook/tests/unit/test_chat_router_sse.py newbee_notebook/tests/unit/test_chat_service_guards.py newbee_notebook/tests/unit/test_chat_engine.py
git commit -m "refactor(chat): route agent traffic through new runtime"
```

---

### Task 11: Migrate `ask` to the New Runtime

**Files:**
- Modify: `newbee_notebook/core/engine/mode_config.py`
- Modify: `newbee_notebook/core/tools/builtin_provider.py`
- Modify: `newbee_notebook/application/services/chat_service.py`
- Test: `newbee_notebook/tests/unit/test_modes.py`
- Test: `newbee_notebook/tests/unit/test_tools.py`
- Test: `newbee_notebook/tests/unit/test_chat_engine.py`

**Step 1: Write the failing tests**

Cover:
- `ask` receives only `knowledge_base + time`
- `ask` prompt/tool policy biases toward `knowledge_base`
- `ask` returns grounded sources through unified contract

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/test_modes.py newbee_notebook/tests/unit/test_tools.py newbee_notebook/tests/unit/test_chat_engine.py -k ask -v
```

Expected: FAIL because old `AskMode` is still in use

**Step 3: Write minimal implementation**

Cut over `ask` in runtime config and service dispatch only. Do not delete old `AskMode` yet.

**Step 4: Run test to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/test_modes.py newbee_notebook/tests/unit/test_tools.py newbee_notebook/tests/unit/test_chat_engine.py -k ask -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/engine/mode_config.py newbee_notebook/core/tools/builtin_provider.py newbee_notebook/application/services/chat_service.py newbee_notebook/tests/unit/test_modes.py newbee_notebook/tests/unit/test_tools.py newbee_notebook/tests/unit/test_chat_engine.py
git commit -m "feat(ask): migrate ask mode to runtime policies"
```

---

### Task 12: Migrate `explain / conclude` to Retrieval-Required Runtime

**Files:**
- Modify: `newbee_notebook/core/engine/mode_config.py`
- Modify: `newbee_notebook/core/engine/agent_loop.py`
- Modify: `newbee_notebook/core/tools/knowledge_base.py`
- Modify: `newbee_notebook/application/services/chat_service.py`
- Modify: `newbee_notebook/api/routers/chat.py`
- Test: `newbee_notebook/tests/unit/test_modes.py`
- Test: `newbee_notebook/tests/unit/test_chat_engine.py`
- Test: `newbee_notebook/tests/unit/test_chat_service_guards.py`

**Step 1: Write the failing tests**

Cover:
- explain/conclude require `context.selected_text` and `context.document_id`
- each retrieval iteration must call `knowledge_base`
- quality gate can relax scope from `document -> notebook`
- synthesis happens after max 3 retrieval iterations

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/test_modes.py newbee_notebook/tests/unit/test_chat_engine.py newbee_notebook/tests/unit/test_chat_service_guards.py -k "explain or conclude" -v
```

Expected: FAIL because old QueryEngine path is still active

**Step 3: Write minimal implementation**

Implement:
- retrieval-required loop policy
- explain/conclude default search templates
- quality gate + scope relaxation
- chat service validation for selection-triggered requests

**Step 4: Run test to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/test_modes.py newbee_notebook/tests/unit/test_chat_engine.py newbee_notebook/tests/unit/test_chat_service_guards.py -k "explain or conclude" -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/engine/mode_config.py newbee_notebook/core/engine/agent_loop.py newbee_notebook/core/tools/knowledge_base.py newbee_notebook/application/services/chat_service.py newbee_notebook/api/routers/chat.py newbee_notebook/tests/unit/test_modes.py newbee_notebook/tests/unit/test_chat_engine.py newbee_notebook/tests/unit/test_chat_service_guards.py
git commit -m "feat(explain-conclude): migrate retrieval-required workflows"
```

---

### Task 13: Remove the Old Runtime Stack

**Files:**
- Delete: `newbee_notebook/core/engine/selector.py`
- Delete: `newbee_notebook/core/engine/session.py`
- Delete: `newbee_notebook/core/engine/modes/base.py`
- Delete: `newbee_notebook/core/engine/modes/chat_mode.py`
- Delete: `newbee_notebook/core/engine/modes/ask_mode.py`
- Delete: `newbee_notebook/core/engine/modes/explain_mode.py`
- Delete: `newbee_notebook/core/engine/modes/conclude_mode.py`
- Delete: `newbee_notebook/core/engine/modes/utils.py`
- Delete: `newbee_notebook/core/engine/modes/__init__.py`
- Modify: `newbee_notebook/core/engine/__init__.py`
- Modify: tests still importing old modes

**Step 1: Write or update the failing tests**

Replace old mode-selector-based tests with runtime-based tests only.

**Step 2: Run the focused suite and confirm imports fail before cleanup**

Run:
```bash
pytest newbee_notebook/tests/unit/test_modes.py newbee_notebook/tests/unit/test_chat_engine.py -v
```

Expected: import failures or old behavior mismatches

**Step 3: Remove old code and update imports**

Keep:
- `index_builder.py`
- `notebook_context.py`

Remove only the old runtime pieces.

**Step 4: Run focused regression**

Run:
```bash
pytest newbee_notebook/tests/unit/test_modes.py newbee_notebook/tests/unit/test_chat_engine.py newbee_notebook/tests/unit/test_chat_router_sse.py newbee_notebook/tests/unit/test_chat_service_guards.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add -A newbee_notebook/core/engine newbee_notebook/tests/unit
git commit -m "refactor(engine): remove legacy mode selector runtime"
```

---

### Task 14: Add MCP on Top of the New Tool Registry

**Files:**
- Create: `newbee_notebook/core/mcp/config.py`
- Create: `newbee_notebook/core/mcp/client_manager.py`
- Create: `newbee_notebook/core/mcp/tool_adapter.py`
- Create: `newbee_notebook/core/mcp/types.py`
- Modify: `newbee_notebook/core/tools/registry.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Test: `newbee_notebook/tests/unit/core/mcp/test_tool_adapter.py`
- Test: `newbee_notebook/tests/unit/core/mcp/test_client_manager.py`

**Step 1: Write the failing tests**

Cover:
- MCP tool conversion to `ToolDefinition`
- `agent`-only injection
- server name prefixing for tool uniqueness
- disabled server exclusion

**Step 2: Run test to verify failure**

Run:
```bash
pytest newbee_notebook/tests/unit/core/mcp/test_tool_adapter.py newbee_notebook/tests/unit/core/mcp/test_client_manager.py -v
```

Expected: FAIL because MCP runtime code does not exist

**Step 3: Write minimal implementation**

Implement MCP only after the core runtime is stable. Do not allow MCP into `ask`, `explain`, or `conclude`.

**Step 4: Run test to verify pass**

Run:
```bash
pytest newbee_notebook/tests/unit/core/mcp/test_tool_adapter.py newbee_notebook/tests/unit/core/mcp/test_client_manager.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add newbee_notebook/core/mcp newbee_notebook/core/tools/registry.py newbee_notebook/api/dependencies.py newbee_notebook/tests/unit/core/mcp
git commit -m "feat(mcp): attach external tools to agent runtime"
```

---

## Verification Gates

Run these verification sets before declaring the full batch-2 implementation complete.

### Core unit suite

```bash
pytest newbee_notebook/tests/unit/core/llm newbee_notebook/tests/unit/core/tools newbee_notebook/tests/unit/core/context newbee_notebook/tests/unit/core/engine newbee_notebook/tests/unit/core/session -v
```

### Service and router regression

```bash
pytest newbee_notebook/tests/unit/test_chat_service_guards.py newbee_notebook/tests/unit/test_chat_router_sse.py newbee_notebook/tests/unit/test_chat_engine.py newbee_notebook/tests/unit/test_tools.py -v
```

### API-level integration

```bash
pytest newbee_notebook/tests/integration/test_chat_engine_integration.py -v
```

### Manual checks

1. `chat` API still works with `mode=chat`
2. `mode=agent` works through the same endpoint
3. `ask` only exposes `knowledge_base + time`
4. `explain / conclude` reject missing `selected_text` or `document_id`
5. `explain / conclude` stay within current document first, then relax to notebook scope when quality is low
6. `phase` is emitted as the official SSE event type

---

## Recommended Commit Cadence

Use one commit per task. Do not combine multiple runtime phases into a single commit. The minimum acceptable split is:

1. blocking-fix
2. llm
3. tool contracts + registry
4. knowledge_base
5. context
6. engine config/events
7. runtime loop
8. session
9. agent integration
10. ask migration
11. explain/conclude migration
12. cleanup
13. mcp

This keeps rollback and review cost low.
