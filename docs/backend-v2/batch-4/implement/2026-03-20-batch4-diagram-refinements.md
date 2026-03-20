# Batch-4 Diagram Refinements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refine Studio diagram UX for batch-4 by improving readability, exposing copyable diagram IDs, enforcing notebook-scoped diagram operations, and completing Mermaid rendering coverage.

**Architecture:** Keep diagrams notebook-owned with document associations. Update the Studio list/detail UI and diagram renderers in the frontend, then tighten backend read/update/delete paths so `diagram_id` operations are still constrained by the active notebook context.

**Tech Stack:** Next.js, React Query, React Flow, Mermaid, FastAPI, pytest, Playwright

---

### Task 1: Diagram Metadata UX

**Files:**
- Modify: `frontend/src/components/studio/studio-panel.tsx`
- Modify: `frontend/src/lib/i18n/strings.ts`
- Test: `frontend/src/components/studio/studio-panel.test.tsx` or existing Studio tests if present

**Step 1: Write the failing test**
- Add a test that expects each diagram card to show a copyable diagram ID chip and only the diagram type badge.

**Step 2: Run test to verify it fails**
- Run: `pnpm --dir frontend test -- studio`

**Step 3: Write minimal implementation**
- Add copyable diagram ID chips in list/detail views.
- Remove `format` and document-count badges from diagram cards.

**Step 4: Run test to verify it passes**
- Run the targeted frontend test again.

**Step 5: Commit**
- Commit after diagram metadata UX is stable.

### Task 2: React Flow Readability

**Files:**
- Modify: `frontend/src/components/studio/reactflow-renderer.tsx`
- Modify: `frontend/src/lib/diagram/reactflow-layout.ts`
- Test: `frontend/src/components/studio/reactflow-renderer.test.tsx`
- Test: `frontend/src/lib/diagram/reactflow-layout.test.ts`

**Step 1: Write the failing test**
- Add assertions for larger node sizing and updated root node class/styling assumptions.

**Step 2: Run test to verify it fails**
- Run the targeted renderer/layout tests.

**Step 3: Write minimal implementation**
- Switch root styling to pale green.
- Increase node and font sizes for right-panel readability.

**Step 4: Run test to verify it passes**
- Re-run targeted renderer/layout tests.

**Step 5: Commit**
- Commit after visual regression checks pass.

### Task 3: Mermaid Rendering and Diagram Reply Cleanup

**Files:**
- Create: `frontend/src/components/studio/mermaid-renderer.tsx`
- Modify: `frontend/src/components/studio/diagram-viewer.tsx`
- Modify: `frontend/src/components/studio/diagram-viewer.test.tsx`
- Create: `frontend/src/components/studio/mermaid-renderer.test.tsx`
- Modify: `newbee_notebook/skills/diagram/provider.py`
- Modify: `newbee_notebook/skills/diagram/tools.py`
- Test: `newbee_notebook/tests/unit/skills/diagram/test_tools.py`

**Step 1: Write the failing test**
- Add tests for Mermaid component rendering path and for create-tool replies avoiding raw prose ID guidance.

**Step 2: Run test to verify it fails**
- Run targeted frontend and backend tests.

**Step 3: Write minimal implementation**
- Extract Mermaid renderer component.
- Keep Mermaid read-only.
- Keep `diagram_id` in tool metadata but remove redundant prose instructions from normal assistant replies.

**Step 4: Run test to verify it passes**
- Re-run targeted tests.

**Step 5: Commit**
- Commit after diagram renderers and replies are stable.

### Task 4: Notebook Scope Guard

**Files:**
- Modify: `newbee_notebook/application/services/diagram_service.py`
- Modify: `newbee_notebook/skills/diagram/tools.py`
- Test: `newbee_notebook/tests/unit/application/services/test_diagram_service.py`
- Test: `newbee_notebook/tests/unit/skills/diagram/test_tools.py`

**Step 1: Write the failing test**
- Add tests proving update/read/delete paths reject diagram IDs outside the active notebook.

**Step 2: Run test to verify it fails**
- Run targeted pytest commands.

**Step 3: Write minimal implementation**
- Add notebook-scoped service helpers and use them in skill tools that operate on `diagram_id`.

**Step 4: Run test to verify it passes**
- Re-run targeted backend tests.

**Step 5: Commit**
- Commit after notebook isolation is enforced.

### Task 5: Verification

**Files:**
- No code changes expected

**Step 1: Run automated verification**
- Run: `pnpm --dir frontend typecheck`
- Run: `pnpm --dir frontend test`
- Run: `python -m pytest newbee_notebook/tests/unit/application/services/test_diagram_service.py newbee_notebook/tests/unit/skills/diagram/test_tools.py -q`

**Step 2: Run manual verification**
- Use Playwright against `http://localhost:3000/notebooks`
- Confirm diagram list badges, copyable ID chips, React Flow readability, Mermaid rendering, and diagram persistence behavior

**Step 3: Capture screenshots**
- Save screenshots before/after the key diagram screens for review

**Step 4: Commit**
- Commit the verified batch-4 refinement slice
