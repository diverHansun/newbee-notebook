# Tasks - Backend V4 Skills MVP

## Metadata

- Created: 2026-05-05
- Last Updated: 2026-05-05
- Source Plan: `docs/backend-v4/implement-1/implementation-plan.md`
- Current Phase: Phase 1 - Skills MVP

## Progress Summary

- Total: 11 tasks
- Completed: 0
- In Progress: 0
- Remaining: 11

## Phase 1: Skills MVP

- [ ] T001 Define Phase 1 source file layout under `newbee_notebook/core/skills/`.
- [ ] T002 Implement `ManifestParser` with Anthropic-compatible `name` and `description` validation.
- [ ] T003 Implement `ContentHasher` with deterministic path sorting and SHA-256 tree hashing.
- [ ] T004 Extend skill contracts with config skill metadata while preserving existing provider protocol.
- [ ] T005 Upgrade `SkillRegistry` to support built-in providers and enabled config providers without command conflicts.
- [ ] T006 Implement `ConfigSkillProvider` and `ActivationContextBuilder` with prompt-only progressive disclosure.
- [ ] T007 Implement local copy-only install preview and lifecycle list/enable/disable/uninstall services.
- [ ] T008 Add `/api/skills` list and lifecycle contract endpoints.
- [ ] T009 Integrate config skill activation into `ChatService._resolve_skill_runtime`.
- [ ] T010 Add unit and contract tests according to `docs-test/` directory rules.
- [ ] T011 Run targeted Phase 1 tests and update this plan with any discovered scope corrections before moving to Phase 2.

## Definition Of Done

- Unit tests for pure logic and service orchestration are under `newbee_notebook/tests/unit/core/skills/`.
- Chat routing tests continue to cover built-in skill compatibility.
- API contract tests for new router endpoints are under `newbee_notebook/tests/contract/api/`.
- Targeted verification commands run before a task is marked complete.
- No Phase 1 code path executes `scripts/` or requires sandbox.
