# Tasks - Backend V4 Skills MVP

## Metadata

- Created: 2026-05-05
- Last Updated: 2026-05-05
- Source Plan: `docs/backend-v4/implement-1/implementation-plan.md`
- Current Phase: Phase 1 - Skills MVP

## Progress Summary

- Total: 11 tasks
- Completed: 11
- In Progress: 0
- Remaining: 0

## Phase 1: Skills MVP

- [X] T001 Define Phase 1 source file layout under `newbee_notebook/core/skills/`.
- [X] T002 Implement `ManifestParser` with Anthropic-compatible `name` and `description` validation.
- [X] T003 Implement `ContentHasher` with deterministic path sorting and SHA-256 tree hashing.
- [X] T004 Extend skill contracts with config skill metadata while preserving existing provider protocol.
- [X] T005 Upgrade `SkillRegistry` to support built-in providers and enabled config providers without command conflicts.
- [X] T006 Implement `ConfigSkillProvider` and `ActivationContextBuilder` with prompt-only progressive disclosure.
- [X] T007 Implement local copy-only install preview and lifecycle list/enable/disable/uninstall services.
- [X] T008 Add `/api/skills` list and lifecycle contract endpoints.
- [X] T009 Integrate config skill activation into `ChatService._resolve_skill_runtime`.
- [X] T010 Add unit and contract tests according to `docs-test/` directory rules.
- [X] T011 Run targeted Phase 1 tests and update this plan with any discovered scope corrections before moving to Phase 2.

## Definition Of Done

- Unit tests for pure logic and service orchestration are under `newbee_notebook/tests/unit/core/skills/`.
- Chat routing tests continue to cover built-in skill compatibility.
- API contract tests for new router endpoints are under `newbee_notebook/tests/contract/api/`.
- Targeted verification commands run before a task is marked complete.
- No Phase 1 code path executes `scripts/` or requires sandbox.
