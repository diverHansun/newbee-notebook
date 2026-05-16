# Skills Settings Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable the Control Panel Skills tab so users can view builtin Studio skills as read-only capabilities and manage installed skills stored under `configs/skills/`, while moving MCP config display and loading to `configs/mcp/`.

**Architecture:** Treat skills as a catalog with two sources: builtin Studio skills (`/note`, `/diagram`, `/video`) and config-installed skills discovered from `configs/skills/`. The frontend renders builtin skills as read-only cards and installed skills as hot-reloaded manageable rows backed by REST APIs. MCP server definitions move from a single `configs/mcp.json` file to `configs/mcp/mcp.json`, with the example file living next to it as `configs/mcp/mcp.example.json`.

**Tech Stack:** FastAPI, Pydantic, React 19, Next.js 15, TanStack Query, Vitest, pytest.

---

## Current State And Decisions

- `frontend/src/components/layout/control-panel.tsx` keeps `skills` in `DISABLED_ITEMS`, so the nav item still shows "即将推出".
- `newbee_notebook/api/routers/skills.py` exposes `GET /api/v1/skills`, `POST /api/v1/skills/{name}/toggle`, and `DELETE /api/v1/skills/{name}` for installed config skills only.
- Builtin Studio skills are registered in `get_runtime_skill_registry_dep()` through `NoteSkillProvider`, `DiagramSkillProvider`, and `VideoSkillProvider`; they are not listed by the management API.
- `SkillLifecycle.list_skills()` reads `configs/skills/` from disk and DB settings on demand, so installed skill list changes are naturally hot-reloadable if the API is called again.
- `frontend/src/components/chat/slash-command-hint.tsx` hardcodes `/note`, `/diagram`, and `/video`.
- MCP code and UI still reference `configs/mcp.json`; the new target is `configs/mcp/mcp.json` with example file `configs/mcp/mcp.example.json`.

No open product question blocks implementation. The main implementation choice is to add a catalog response rather than making the frontend hardcode builtin skills.

## File Structure

- Modify `newbee_notebook/api/routers/skills.py`: extend list response to include builtin and installed skills with manageability flags.
- Modify `newbee_notebook/api/dependencies.py`: use a helper for MCP config path, targeting `configs/mcp/mcp.json`.
- Create `newbee_notebook/core/mcp/paths.py`: single source of truth for MCP config and example paths.
- Modify `newbee_notebook/core/mcp/config.py`: keep parser unchanged, but tests should call the new path helper where runtime paths matter.
- Modify `newbee_notebook/tests/contract/api/test_skills_router.py`: verify builtin read-only catalog plus installed skills.
- Modify `newbee_notebook/tests/unit/core/mcp/test_config.py`: update default config path expectations.
- Modify `newbee_notebook/tests/contract/api/test_mcp_settings_router.py`: assert displayed/configured path is `configs/mcp/mcp.json` if API exposes it.
- Create `frontend/src/lib/api/skills.ts`: skills API types and calls.
- Create `frontend/src/components/layout/skill-config-panel.tsx`: Skills tab panel.
- Modify `frontend/src/components/layout/control-panel.tsx`: enable `skills` as an active tab and render `SkillConfigPanel`.
- Modify `frontend/src/components/layout/mcp-config-panel.tsx`: display `configs/mcp/mcp.json`.
- Modify `frontend/src/lib/i18n/strings.ts`: add Skills panel labels and update MCP config path text.
- Modify `frontend/src/components/chat/slash-command-hint.tsx`: fetch enabled skill catalog and include installed skills.
- Add tests in `frontend/src/components/layout/skill-config-panel.test.tsx` and update `frontend/src/components/chat/chat-input.test.tsx`.
- Move `configs/mcp.example.json` to `configs/mcp/mcp.example.json`; do not commit user secrets or real MCP config.
- Do not keep a fallback to the old `configs/mcp.json` path.

## API Contract

`GET /api/v1/skills` should return:

```json
{
  "skills": [
    {
      "name": "note",
      "command": "/note",
      "description": "Note and mark management skill",
      "enabled": true,
      "kind": "builtin",
      "source": "studio",
      "content_hash": "",
      "path": "",
      "scopes": ["/note"],
      "manageable": false,
      "deletable": false,
      "readonly_reason": "builtin"
    },
    {
      "name": "demo",
      "command": "/demo",
      "description": "Prepare a concise notebook brief.",
      "enabled": true,
      "kind": "installed",
      "source": "local",
      "content_hash": "hash123",
      "path": "configs/skills/demo",
      "scopes": ["/demo"],
      "manageable": true,
      "deletable": true,
      "readonly_reason": null
    }
  ]
}
```

`POST /api/v1/skills/{name}/toggle` and `DELETE /api/v1/skills/{name}` remain installed-skill-only. Builtin names must return `400` with a clear error if called by mistake.

## Task 1: Backend Skills Catalog

**Files:**
- Modify: `newbee_notebook/api/routers/skills.py`
- Test: `newbee_notebook/tests/contract/api/test_skills_router.py`

- [ ] **Step 1: Write failing contract tests**

Add assertions that `GET /api/v1/skills` returns builtin read-only skills before installed skills:

```python
def test_get_skills_includes_builtin_readonly_catalog():
    client, _lifecycle = _build_client()

    response = client.get("/api/v1/skills")

    assert response.status_code == 200
    skills = response.json()["skills"]
    note = next(item for item in skills if item["name"] == "note")
    assert note["command"] == "/note"
    assert note["kind"] == "builtin"
    assert note["source"] == "studio"
    assert note["enabled"] is True
    assert note["manageable"] is False
    assert note["deletable"] is False
    assert note["readonly_reason"] == "builtin"
```

Add builtin protection tests:

```python
def test_toggle_builtin_skill_is_rejected():
    client, _lifecycle = _build_client()

    response = client.post("/api/v1/skills/note/toggle", json={"enabled": False})

    assert response.status_code == 400


def test_delete_builtin_skill_is_rejected():
    client, _lifecycle = _build_client()

    response = client.delete("/api/v1/skills/note")

    assert response.status_code == 400
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest newbee_notebook/tests/contract/api/test_skills_router.py -q`

Expected: failures mentioning missing `command`, `kind`, `manageable`, or builtin entries.

- [ ] **Step 3: Extend response model**

In `newbee_notebook/api/routers/skills.py`, extend `SkillResponse`:

```python
class SkillResponse(BaseModel):
    name: str
    command: str
    description: str
    enabled: bool
    kind: str
    source: str
    content_hash: str
    path: str
    scopes: list[str]
    manageable: bool
    deletable: bool
    readonly_reason: str | None = None
```

Add builtin catalog constants:

```python
BUILTIN_SKILLS = [
    SkillResponse(
        name="note",
        command="/note",
        description="Note and mark management skill",
        enabled=True,
        kind="builtin",
        source="studio",
        content_hash="",
        path="",
        scopes=["/note"],
        manageable=False,
        deletable=False,
        readonly_reason="builtin",
    ),
    SkillResponse(
        name="diagram",
        command="/diagram",
        description="Diagram generation and management skill",
        enabled=True,
        kind="builtin",
        source="studio",
        content_hash="",
        path="",
        scopes=["/diagram"],
        manageable=False,
        deletable=False,
        readonly_reason="builtin",
    ),
    SkillResponse(
        name="video",
        command="/video",
        description="Video metadata lookup and summarization skill",
        enabled=True,
        kind="builtin",
        source="studio",
        content_hash="",
        path="",
        scopes=["/video"],
        manageable=False,
        deletable=False,
        readonly_reason="builtin",
    ),
]
BUILTIN_SKILL_NAMES = {item.name for item in BUILTIN_SKILLS}
```

Update installed conversion:

```python
def _to_response(record: SkillRecord) -> SkillResponse:
    return SkillResponse(
        name=record.name,
        command=f"/{record.name}",
        description=record.description,
        enabled=record.enabled,
        kind="installed",
        source=record.source,
        content_hash=record.content_hash,
        path=record.path,
        scopes=[f"/{record.name}"],
        manageable=True,
        deletable=True,
        readonly_reason=None,
    )
```

Update list endpoint:

```python
records = await lifecycle.list_skills()
return SkillsListResponse(
    skills=[*BUILTIN_SKILLS, *[_to_response(record) for record in records]]
)
```

Guard mutations:

```python
if skill_name in BUILTIN_SKILL_NAMES:
    raise HTTPException(status_code=400, detail="builtin skills are read-only")
```

- [ ] **Step 4: Run backend skills tests**

Run: `pytest newbee_notebook/tests/contract/api/test_skills_router.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add newbee_notebook/api/routers/skills.py newbee_notebook/tests/contract/api/test_skills_router.py
git commit -m "feat(api): expose skills catalog"
```

## Task 2: Frontend Skills API Client

**Files:**
- Create: `frontend/src/lib/api/skills.ts`
- Test: `frontend/src/lib/api/skills.test.ts`

- [ ] **Step 1: Write API client test**

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import { deleteSkill, listSkills, toggleSkill } from "@/lib/api/skills";

describe("skills api", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("lists skills through the v1 api", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ skills: [] }),
    }) as unknown as typeof fetch;

    await expect(listSkills()).resolves.toEqual({ skills: [] });
    expect(global.fetch).toHaveBeenCalledWith("/api/v1/skills", expect.any(Object));
  });

  it("toggles an installed skill", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ name: "demo", enabled: false }),
    }) as unknown as typeof fetch;

    await toggleSkill("demo", false);
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/v1/skills/demo/toggle",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("deletes an installed skill", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ deleted: true, name: "demo" }),
    }) as unknown as typeof fetch;

    await deleteSkill("demo");
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/v1/skills/demo",
      expect.objectContaining({ method: "DELETE" })
    );
  });
});
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd frontend && pnpm test src/lib/api/skills.test.ts`

Expected: module not found for `@/lib/api/skills`.

- [ ] **Step 3: Create API client**

Create `frontend/src/lib/api/skills.ts`:

```ts
import { apiFetch } from "@/lib/api/client";

export type SkillKind = "builtin" | "installed";

export type SkillCatalogItem = {
  name: string;
  command: string;
  description: string;
  enabled: boolean;
  kind: SkillKind;
  source: string;
  content_hash: string;
  path: string;
  scopes: string[];
  manageable: boolean;
  deletable: boolean;
  readonly_reason?: string | null;
};

export type SkillsListResponse = {
  skills: SkillCatalogItem[];
};

export type DeleteSkillResponse = {
  deleted: boolean;
  name: string;
};

export function listSkills() {
  return apiFetch<SkillsListResponse>("/skills");
}

export function toggleSkill(name: string, enabled: boolean) {
  return apiFetch<SkillCatalogItem>(`/skills/${encodeURIComponent(name)}/toggle`, {
    method: "POST",
    body: { enabled },
  });
}

export function deleteSkill(name: string) {
  return apiFetch<DeleteSkillResponse>(`/skills/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}
```

- [ ] **Step 4: Run API client test**

Run: `cd frontend && pnpm test src/lib/api/skills.test.ts`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api/skills.ts frontend/src/lib/api/skills.test.ts
git commit -m "feat(frontend): add skills api client"
```

## Task 3: Skills Control Panel UI

**Files:**
- Create: `frontend/src/components/layout/skill-config-panel.tsx`
- Create: `frontend/src/components/layout/skill-config-panel.test.tsx`
- Modify: `frontend/src/components/layout/control-panel.tsx`
- Modify: `frontend/src/lib/i18n/strings.ts`
- Modify: `frontend/src/styles/control-panel.css`

- [ ] **Step 1: Write panel tests**

Mock `@/lib/api/skills` and assert builtin read-only behavior:

```tsx
it("renders builtin skills as readonly and installed skills as manageable", async () => {
  vi.mocked(listSkills).mockResolvedValue({
    skills: [
      {
        name: "note",
        command: "/note",
        description: "Note and mark management skill",
        enabled: true,
        kind: "builtin",
        source: "studio",
        content_hash: "",
        path: "",
        scopes: ["/note"],
        manageable: false,
        deletable: false,
        readonly_reason: "builtin",
      },
      {
        name: "demo",
        command: "/demo",
        description: "Prepare a concise notebook brief.",
        enabled: true,
        kind: "installed",
        source: "local",
        content_hash: "hash123456789",
        path: "configs/skills/demo",
        scopes: ["/demo"],
        manageable: true,
        deletable: true,
        readonly_reason: null,
      },
    ],
  });

  render(<SkillConfigPanel />);

  expect(await screen.findByText("/note")).toBeInTheDocument();
  expect(screen.getByText(/builtin/i)).toBeInTheDocument();
  expect(screen.getByText("/demo")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /disable demo/i })).toBeEnabled();
  expect(screen.getByRole("button", { name: /delete demo/i })).toBeEnabled();
});
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd frontend && pnpm test src/components/layout/skill-config-panel.test.tsx`

Expected: module not found for `SkillConfigPanel`.

- [ ] **Step 3: Implement panel**

Create `SkillConfigPanel` with these behaviors:

```tsx
const builtinSkills = skills.filter((skill) => skill.kind === "builtin");
const installedSkills = skills.filter((skill) => skill.kind === "installed");
```

Render two cards:

- `Studio Skills`: builtin list, command, description, source badge, no destructive controls.
- `Installed Skills`: installed list, command, description, hash short code, path, enable/disable segmented control or switch, delete button, refresh button.

Mutation rules:

```tsx
const toggleMutation = useMutation({
  mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) =>
    toggleSkill(name, enabled),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["skills-catalog"] });
  },
});
```

Delete rules:

```tsx
const deleteMutation = useMutation({
  mutationFn: deleteSkill,
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["skills-catalog"] });
  },
});
```

- [ ] **Step 4: Enable nav tab**

In `control-panel.tsx`:

```ts
export type ControlPanelTab =
  | "language"
  | "theme"
  | "model"
  | "mcp"
  | "skills"
  | "data"
  | "about";
```

Move `{ key: "skills" }` into `ACTIVE_ITEMS`, remove `DISABLED_ITEMS`, and render:

```tsx
{activeTab === "skills" && <SkillConfigPanel />}
```

- [ ] **Step 5: Add i18n labels**

Add labels under `uiStrings.controlPanel`, including:

```ts
skillsStudio: { zh: "Studio Skills", en: "Studio Skills" },
skillsInstalled: { zh: "Installed Skills", en: "Installed Skills" },
skillsInstalledHint: {
  zh: "这些 skill 从 configs/skills/ 热加载，可启用、禁用或删除。",
  en: "These skills are hot-loaded from configs/skills/ and can be enabled, disabled, or deleted.",
},
skillsBuiltinHint: {
  zh: "内置 Studio skill 由应用提供，只读且不可删除。",
  en: "Builtin Studio skills are provided by the app and cannot be deleted.",
},
skillDisable: { zh: "禁用 {name}", en: "Disable {name}" },
skillEnable: { zh: "启用 {name}", en: "Enable {name}" },
skillDelete: { zh: "删除 {name}", en: "Delete {name}" },
skillReadonly: { zh: "只读", en: "Readonly" },
skillNoInstalled: { zh: "暂无已安装 skill。", en: "No installed skills yet." },
```

- [ ] **Step 6: Run panel tests**

Run: `cd frontend && pnpm test src/components/layout/skill-config-panel.test.tsx`

Expected: pass.

- [ ] **Step 7: Run full relevant frontend tests**

Run: `cd frontend && pnpm test src/components/layout/skill-config-panel.test.tsx src/components/chat/chat-input.test.tsx`

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/layout/skill-config-panel.tsx frontend/src/components/layout/skill-config-panel.test.tsx frontend/src/components/layout/control-panel.tsx frontend/src/lib/i18n/strings.ts frontend/src/styles/control-panel.css
git commit -m "feat(frontend): enable skills settings panel"
```

## Task 4: Dynamic Slash Command Hint

**Files:**
- Modify: `frontend/src/components/chat/slash-command-hint.tsx`
- Modify: `frontend/src/components/chat/chat-input.test.tsx`

- [ ] **Step 1: Write failing tests**

Add a test where `listSkills()` returns `/note`, `/diagram`, `/video`, and `/demo`; assert `/demo` appears and disabled installed skills do not appear.

```tsx
it("shows enabled installed skills in slash command hint", async () => {
  vi.mocked(listSkills).mockResolvedValue({
    skills: [
      builtinSkill("note", "/note"),
      installedSkill("demo", "/demo", true),
      installedSkill("off", "/off", false),
    ],
  });

  render(<ChatInput {...props} />);
  await user.type(screen.getByRole("textbox"), "/");

  expect(await screen.findByText("/demo")).toBeInTheDocument();
  expect(screen.queryByText("/off")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd frontend && pnpm test src/components/chat/chat-input.test.tsx`

Expected: `/demo` is missing.

- [ ] **Step 3: Fetch catalog in `SlashCommandHint`**

Use React Query:

```tsx
const skillsQuery = useQuery({
  queryKey: ["skills-catalog"],
  queryFn: listSkills,
  staleTime: 15_000,
  retry: false,
});
```

Build commands:

```tsx
const commands = useMemo<SlashCommand[]>(() => {
  const catalog = skillsQuery.data?.skills ?? DEFAULT_BUILTIN_COMMANDS;
  return catalog
    .filter((skill) => skill.enabled)
    .map((skill) => ({
      command: skill.command,
      description: skill.description,
      available: true,
    }));
}, [skillsQuery.data?.skills]);
```

Keep a default builtin fallback so the hint works while the request is loading or failed.

- [ ] **Step 4: Run slash tests**

Run: `cd frontend && pnpm test src/components/chat/chat-input.test.tsx`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/slash-command-hint.tsx frontend/src/components/chat/chat-input.test.tsx
git commit -m "feat(frontend): load slash commands from skills catalog"
```

## Task 5: MCP Config Directory Migration

**Files:**
- Create: `newbee_notebook/core/mcp/paths.py`
- Modify: `newbee_notebook/api/dependencies.py`
- Modify: `frontend/src/components/layout/mcp-config-panel.tsx`
- Modify: `frontend/src/lib/i18n/strings.ts`
- Modify: `newbee_notebook/tests/unit/core/mcp/test_config.py`
- Modify: `newbee_notebook/tests/unit/core/mcp/test_client_manager.py`
- Modify: `newbee_notebook/tests/contract/api/test_mcp_settings_router.py`
- Move: `configs/mcp.example.json` -> `configs/mcp/mcp.example.json`

- [ ] **Step 1: Write failing path test**

In `newbee_notebook/tests/unit/core/mcp/test_config.py`:

```python
def test_default_mcp_config_path_uses_configs_mcp_directory():
    from newbee_notebook.core.mcp.paths import get_mcp_config_path

    path = get_mcp_config_path()

    assert path.as_posix().endswith("configs/mcp/mcp.json")
```

Do not add a legacy fallback test; the old `configs/mcp.json` path is no longer supported.

- [ ] **Step 2: Run test to verify failure**

Run: `pytest newbee_notebook/tests/unit/core/mcp/test_config.py -q`

Expected: import error for `newbee_notebook.core.mcp.paths`.

- [ ] **Step 3: Add path helper**

Create `newbee_notebook/core/mcp/paths.py`:

```python
from __future__ import annotations

from pathlib import Path

from newbee_notebook.core.common.project_paths import get_configs_directory


def get_mcp_config_directory() -> Path:
    return get_configs_directory() / "mcp"


def get_mcp_config_path() -> Path:
    return get_mcp_config_directory() / "mcp.json"


def get_mcp_example_config_path() -> Path:
    return get_mcp_config_directory() / "mcp.example.json"


```

- [ ] **Step 4: Use helper in dependencies**

Replace:

```python
MCPClientManager(config_path=get_configs_directory() / "mcp.json")
```

with:

```python
from newbee_notebook.core.mcp.paths import get_mcp_config_path

MCPClientManager(config_path=get_mcp_config_path())
```

- [ ] **Step 5: Move example config**

Move the example file without creating a real `mcp.json`:

```powershell
Move-Item -LiteralPath configs\mcp.example.json -Destination configs\mcp\mcp.example.json
```

The implementation should use `git mv configs/mcp.example.json configs/mcp/mcp.example.json` if the file is tracked.

- [ ] **Step 6: Update frontend text**

In `mcp-config-panel.tsx`, display:

```tsx
<span>configs/mcp/mcp.json</span>
```

In `strings.ts`, update MCP hints to mention `configs/mcp/mcp.json`.

- [ ] **Step 7: Run MCP tests**

Run:

```bash
pytest newbee_notebook/tests/unit/core/mcp/test_config.py newbee_notebook/tests/unit/core/mcp/test_client_manager.py newbee_notebook/tests/contract/api/test_mcp_settings_router.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add newbee_notebook/core/mcp/paths.py newbee_notebook/api/dependencies.py newbee_notebook/tests/unit/core/mcp/test_config.py newbee_notebook/tests/unit/core/mcp/test_client_manager.py newbee_notebook/tests/contract/api/test_mcp_settings_router.py frontend/src/components/layout/mcp-config-panel.tsx frontend/src/lib/i18n/strings.ts configs/mcp/mcp.example.json
git rm configs/mcp.example.json
git commit -m "refactor(config): move mcp config under configs mcp"
```

## Task 6: Verification

**Files:**
- No new files.

- [ ] **Step 1: Backend verification**

Run:

```bash
pytest newbee_notebook/tests/contract/api/test_skills_router.py newbee_notebook/tests/unit/core/mcp/test_config.py newbee_notebook/tests/unit/core/mcp/test_client_manager.py newbee_notebook/tests/contract/api/test_mcp_settings_router.py -q
```

Expected: all pass.

- [ ] **Step 2: Frontend verification**

Run:

```bash
cd frontend
pnpm test src/components/layout/skill-config-panel.test.tsx src/components/chat/chat-input.test.tsx src/lib/api/skills.test.ts
pnpm typecheck
```

Expected: all pass.

- [ ] **Step 3: Manual browser verification**

With backend on `http://localhost:8000` and frontend on `http://localhost:3000`:

1. Open a notebook page.
2. Open the bottom-left Control Panel.
3. Click `Skills`.
4. Confirm builtin Studio skills are visible and read-only.
5. Add a sample directory under `configs/skills/demo/SKILL.md`, refresh the panel, and confirm `/demo` appears.
6. Type `/` in chat and confirm `/demo` appears after refresh.
7. Open MCP tab and confirm the path shows `configs/mcp/mcp.json`.

Expected: no console errors and no layout overlap.

## Self-Review

- Spec coverage: builtin read-only skills, installed skill hot reload from `configs/skills/`, Control Panel Skills activation, slash hint catalog, MCP path migration to `configs/mcp/` are all covered.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: API fields use `command`, `kind`, `manageable`, `deletable`, and `readonly_reason` consistently across backend, frontend client, panel, and tests.
