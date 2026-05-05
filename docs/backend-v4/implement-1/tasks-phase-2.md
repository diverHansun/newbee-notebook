# Tasks - Backend V4 Policy Gate MVP

## Metadata

- Created: 2026-05-05
- Last Updated: 2026-05-05
- Source Plan: `docs/backend-v4/implement-1/implementation-plan.md`
- Current Phase: Phase 2 - Policy Gate MVP

## Scope Notes

- The policy and permission decision path must cover global runtime tools, not only config-skill `scripts/`.
- This batch introduces the policy decision core and connects it to every `AgentLoop` tool execution path.
- `ASK` decisions use the existing confirmation gateway as a compatibility bridge in this batch.
- The full `core/permission` gateway with session allow, permanent allow, queueing, and DB-backed permission records remains the next batch.
- Future `core/shell` tools such as `read`, `grep`, `glob`, `edit`, and `bash` will reuse the same tool metadata and policy gate.

## Progress Summary

- Total: 10 tasks
- Completed: 0
- In Progress: 0
- Remaining: 10

## Phase 2: Policy Gate MVP

- [ ] T201 Add `newbee_notebook/core/policy/` pure decision contracts and exports.
- [ ] T202 Implement deterministic capability signatures with stable canonical JSON.
- [ ] T203 Implement default/yolo decision matrix and dangerous bash command risk upgrade.
- [ ] T204 Extend `ToolDefinition` with `tool_class`, `risk_level`, and `sandbox_required` metadata while preserving existing constructor compatibility.
- [ ] T205 Annotate existing global tools in `newbee_notebook/core/tools/` with read/write risk metadata.
- [ ] T206 Annotate built-in skill tools that perform writes so policy can replace legacy confirm rules later.
- [ ] T207 Add optional policy gate to `AgentLoop` before every tool execution path, including final-synthesis textual tool calls.
- [ ] T208 Pass active skill name and content hash from skills runtime into policy signatures.
- [ ] T209 Keep existing confirmation behavior compatible while routing policy `ASK` through the same user approval event.
- [ ] T210 Run targeted unit tests and update task status before moving to the permission gateway batch.

## Definition Of Done

- `PolicyDecider.decide()` is synchronous and performs no DB, network, SSE, or tool execution.
- Default policy allows read tools and asks for write/edit/custom/dangerous bash tools.
- Yolo policy allows every tool while still generating a capability signature.
- Identical args produce identical signatures regardless of dict key order.
- Active skill `name + content_hash` changes the signature scope.
- All `AgentLoop` tool execution paths call the policy gate before `tool.execute()`.
- A denied confirmation result prevents the tool from executing and returns a failed tool result to the model.
- Tests are placed under `newbee_notebook/tests/unit/core/policy/`, `newbee_notebook/tests/unit/core/tools/`, `newbee_notebook/tests/unit/core/engine/`, and `newbee_notebook/tests/unit/core/session/` according to the touched layer.
