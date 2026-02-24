# Frontend V1 Improve-5 Design (Approved)

## Context

This design is the pre-implementation baseline for `frontend-v1` improve-5.
It builds on improve-1~4 outcomes:

- improve-1~2 stabilized core UX/performance/API behavior
- improve-3 improved UI interaction patterns and introduced segmented controls
- improve-4 established CSS modularization + i18n infrastructure + dark theme variables

The improve-5 scope remains:

- `P1` Global control panel (language migration, theme switch, about panel, placeholders)
- `P2` Notebook cards sizing + pagination
- `P3` Sources refresh button interaction feedback fix

## Approved Decisions

### 1. Execution order

Use `P3 -> P1 -> P2`.

Rationale:

- P3 is low-risk and validates style behavior quickly
- P1 is the stage core and affects global layout/provider wiring
- P2 is independent but larger than P3 and benefits from finishing global UI changes first

### 2. P2 create behavior (important deviation from original improve-5 P2 doc)

Keep current behavior:

- Creating a notebook still navigates directly to the notebook detail page
- Pagination only affects list browsing

This supersedes the earlier P2 note that suggested returning to page 1 after create.

### 3. Global control panel architecture (P1)

- Mount a global entry component in `frontend/src/app/layout.tsx`
- Add `ThemeProvider` in `frontend/src/components/providers/app-provider.tsx`
- Provider order: `ThemeProvider -> LanguageProvider -> QueryProvider`
- Keep `useLang()` API and `localStorage("lang")` behavior unchanged
- Add control panel styles in `frontend/src/styles/control-panel.css`
- Import `control-panel.css` from `frontend/src/app/globals.css`

### 4. Theme provider implementation rule

Do **not** block app rendering before mount (no `return null` for entire app tree).

Reason:

- avoids blank first paint
- preserves current SSR/client behavior
- keeps theme side effects localized to DOM class synchronization

### 5. Control panel tab state rule

Only clickable tabs are part of runtime tab state:

- `language`
- `theme`
- `about`

Placeholder items (`model`, `rag`, `mcp`, `skills`) are rendered as disabled nav items and are not selectable.

### 6. About panel data fetching rule

About panel queries are enabled only when:

- panel is open, and
- active tab is `about`

Recommended cache behavior:

- `/api/v1/info`: long-lived cache (`staleTime: Infinity`)
- `/api/v1/health`: short cache / polling while visible only

### 7. Dev environment overlap rule

In development, the control-panel icon should avoid overlapping the Next.js Dev Tools button.
Use a dev-only position offset (same corner, shifted upward) while keeping production placement at bottom-left.

### 8. Theme switch regression prevention

While implementing P1, also add dark-mode values for improve-4 user bubble tokens:

- `--user-bubble-bg`
- `--user-bubble-fg`

This prevents obvious visual regressions after enabling theme toggling.

## Detailed Design

### P3: Sources refresh button interaction fix

Use the approved minimal fix:

- change refresh button class in `frontend/src/components/sources/source-list.tsx`
- from `btn btn-ghost btn-sm`
- to `btn btn-sm`

No global `btn-ghost` style changes.

### P1: Global control panel

#### Components

- `frontend/src/lib/theme/theme-context.tsx`
  - `ThemeProvider`
  - `useTheme()`
- `frontend/src/components/layout/control-panel-icon.tsx`
  - fixed entry button
  - open/close state
  - outside-click + ESC close
- `frontend/src/components/layout/control-panel.tsx`
  - split panel layout (nav + content)
  - active-tab rendering
  - about panel query integration

#### API usage

Add a small frontend API module for system info:

- `frontend/src/lib/api/system.ts`
  - `getSystemInfo()`
  - `getHealthStatus()`

This keeps fetch logic out of UI components and aligns with improve-2 API layer discipline.

#### Responsive behavior

Preserve split-panel concept, but ensure width works on narrow viewports:

- `width: min(450px, calc(100vw - 24px))`
- right content scrolls if needed

#### Accessibility

- icon button: `aria-label`
- panel: `role="dialog"` + `aria-modal="false"` (popover-style)
- ESC closes
- focus remains usable for keyboard nav

### P2: Notebook cards + pagination

#### Card sizing

- grid min width `280px -> 320px`
- card min height + padding increase
- keep current card structure and text behavior

#### Pagination

- page size `12`
- query key includes page and page size
- page controls visible only when `totalPages > 1`
- use backend pagination metadata (`total`, `has_prev`, `has_next`)

#### Edge cases

- empty list: existing empty state unchanged
- one page: no pager
- delete causing empty current page: move to previous page
- create success: keep direct navigation to detail (approved)

## Files In Scope

### New files

- `frontend/src/lib/theme/theme-context.tsx`
- `frontend/src/lib/api/system.ts`
- `frontend/src/components/layout/control-panel.tsx`
- `frontend/src/components/layout/control-panel-icon.tsx`
- `frontend/src/styles/control-panel.css`

### Modified files

- `frontend/src/app/layout.tsx`
- `frontend/src/components/providers/app-provider.tsx`
- `frontend/src/components/layout/app-shell.tsx`
- `frontend/src/app/notebooks/page.tsx`
- `frontend/src/components/sources/source-list.tsx`
- `frontend/src/app/globals.css`
- `frontend/src/styles/layout.css`
- `frontend/src/styles/cards.css`
- `frontend/src/lib/i18n/strings.ts`
- `docs/frontend-v1/improve-5/P2-notebook-cards-pagination.md` (doc alignment for create behavior)

## Verification Plan (Implementation Stage)

- `pnpm typecheck`
- `pnpm build`
- Playwright manual verification for improve-5 (P1/P2/P3)
- Playwright regression smoke across improve-1~4 core flows:
  - notebooks list
  - library page
  - notebook detail shell (sources/main/studio)
  - language switching
  - chat input presence/basic interactions

