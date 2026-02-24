# Frontend V1 Improve-5 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement improve-5 (P3 refresh-button fix, P1 global control panel with theme/language/about, P2 notebook card sizing + pagination) while preserving existing create-notebook navigation behavior.

**Architecture:** Add a root-level control panel mounted in `layout.tsx` and a new `ThemeProvider`, keep i18n APIs stable, and implement notebook pagination using backend pagination metadata. Use minimal targeted changes for P3 and CSS module-aligned additions for new UI styles.

**Tech Stack:** Next.js App Router, React 19, TypeScript, TanStack Query, existing CSS modular styles, Playwright MCP for UI verification.

---

## Notes Before Execution

- Frontend currently has no automated unit test runner configured (`package.json` only has `typecheck`, `build`, `lint`).
- Apply TDD where practical for isolated logic; otherwise use behavior-first verification with typecheck/build + Playwright regression evidence.
- Do not modify unrelated dirty worktree files.

### Task 1: Align docs and add system API module

**Files:**
- Modify: `docs/frontend-v1/improve-5/P2-notebook-cards-pagination.md`
- Create: `frontend/src/lib/api/system.ts`

**Step 1: Write failing checks (behavior spec)**

- Document expected behavior: create notebook keeps current navigation to detail page.
- Define API function signatures for `/info` and `/health` in TypeScript.

**Step 2: Verify RED**

- Run `rg -n "创建后跳转到第一页" docs/frontend-v1/improve-5/P2-notebook-cards-pagination.md`
- Expected: one match exists (needs update).

**Step 3: Write minimal implementation**

- Update P2 doc wording to keep create->detail behavior.
- Implement `getSystemInfo()` and `getHealthStatus()` using `apiFetch`.

**Step 4: Verify GREEN**

- `rg -n "创建后跳转到第一页" docs/frontend-v1/improve-5/P2-notebook-cards-pagination.md`
- Expected: no matches
- `pnpm typecheck` (later batch verification also acceptable)

### Task 2: P3 refresh button visual feedback fix

**Files:**
- Modify: `frontend/src/components/sources/source-list.tsx`

**Step 1: Write failing test/check**

- Baseline runtime behavior already observed: refresh button uses `btn-ghost` and hover border remains transparent.

**Step 2: Verify RED**

- `rg -n 'className=\"btn btn-ghost btn-sm\"' frontend/src/components/sources/source-list.tsx`
- Expected: refresh button match exists.

**Step 3: Write minimal implementation**

- Change refresh button class to `btn btn-sm`.

**Step 4: Verify GREEN**

- `rg -n '刷新' frontend/src/components/sources/source-list.tsx`
- Playwright hover inspection shows border feedback matches add button.

### Task 3: Add theme context/provider (P1 foundation)

**Files:**
- Create: `frontend/src/lib/theme/theme-context.tsx`
- Modify: `frontend/src/components/providers/app-provider.tsx`
- Modify: `frontend/src/app/globals.css`

**Step 1: Write failing checks**

- `rg --files frontend/src/lib/theme` should return no theme context file.
- `AppProvider` currently lacks `ThemeProvider`.

**Step 2: Verify RED**

- Confirm file missing and provider order absent.

**Step 3: Write minimal implementation**

- Add `ThemeProvider` + `useTheme`
- Sync `localStorage("theme")` and `<html>.dark` class without blocking child render
- Wrap app providers with `ThemeProvider`
- Add dark user bubble variables to `.dark` in `globals.css`

**Step 4: Verify GREEN**

- `pnpm typecheck`
- Optional quick browser eval of `document.documentElement.classList` after toggling (done later in P1 runtime verification)

### Task 4: Build global control panel UI (P1 main)

**Files:**
- Create: `frontend/src/components/layout/control-panel.tsx`
- Create: `frontend/src/components/layout/control-panel-icon.tsx`
- Create: `frontend/src/styles/control-panel.css`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/components/layout/app-shell.tsx`
- Modify: `frontend/src/lib/i18n/strings.ts`

**Step 1: Write failing checks**

- No control panel files exist
- `app-shell.tsx` still renders language segmented control in header

**Step 2: Verify RED**

- `rg -n "SegmentedControl" frontend/src/components/layout/app-shell.tsx`
- Expected: language switch usage present

**Step 3: Write minimal implementation**

- Add fixed global icon + popover
- Add language tab (reuse `useLang`)
- Add theme tab (reuse `useTheme`)
- Add about tab (TanStack Query + system API)
- Add disabled placeholder nav items
- Remove header language switch from `app-shell.tsx`
- Add i18n strings for control panel and pagination
- Import `control-panel.css`
- Dev-only position offset to avoid Next Dev Tools overlap

**Step 4: Verify GREEN**

- `pnpm typecheck`
- `pnpm build`
- Playwright: all pages show icon, header language switch removed, language/theme toggles work, about panel loads info/health

### Task 5: Implement notebook card sizing + pagination (P2)

**Files:**
- Modify: `frontend/src/app/notebooks/page.tsx`
- Modify: `frontend/src/styles/layout.css`
- Modify: `frontend/src/styles/cards.css`
- Modify: `frontend/src/lib/i18n/strings.ts`

**Step 1: Write failing checks**

- `notebooks/page.tsx` uses `listNotebooks(100, 0)`
- no pagination state/UI
- grid min width still 280px

**Step 2: Verify RED**

- `rg -n "listNotebooks\\(100, 0\\)" frontend/src/app/notebooks/page.tsx`
- `rg -n "minmax\\(280px, 1fr\\)" frontend/src/styles/layout.css`

**Step 3: Write minimal implementation**

- Add `currentPage` + `PAGE_SIZE = 12`
- Query by page (`["notebooks", currentPage, PAGE_SIZE]`)
- Render pager when `totalPages > 1`
- Handle delete-empty-page fallback
- Preserve create success direct navigation to detail
- Increase grid min width and card sizing styles

**Step 4: Verify GREEN**

- `pnpm typecheck`
- Playwright visual check for card sizing + pager behavior (if enough notebooks; otherwise verify hidden pager edge case)

### Task 6: End-to-end verification (improve-5 + improve-1~4 smoke)

**Files:**
- No code changes required unless regressions found

**Step 1: Verify improve-5 acceptance**

- Playwright MCP manual checks:
  - P1: control panel on Notebooks/Library/Detail, language & theme persist, about panel info/health
  - P2: card sizing visible; pagination UI/behavior (create enough notebooks if needed)
  - P3: refresh hover/active feedback

**Step 2: Verify improve-1~4 regression smoke**

- Notebooks list create/delete dialog
- Library page basic load/filter controls
- Notebook detail shell load (sources/main/studio)
- Language switch still updates migrated text globally
- Chat input segmented mode + source selector open/close
- Source list add/refresh/remove dialog still works

**Step 3: Static verification**

- Run: `pnpm typecheck`
- Run: `pnpm build`

**Step 4: Record evidence**

- Summarize verified pages, notable console/network observations, and any residual risk (e.g., pagination full-page scenario depends on dataset size)

