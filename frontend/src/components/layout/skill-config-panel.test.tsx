import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageContext } from "@/lib/i18n/language-context";
import { createQueryClient } from "@/test/test-utils";

const apiMocks = vi.hoisted(() => ({
  deleteSkill: vi.fn(),
  listSkills: vi.fn(),
  toggleSkill: vi.fn(),
}));

vi.mock("@/lib/api/skills", () => ({
  deleteSkill: (...args: unknown[]) => apiMocks.deleteSkill(...args),
  listSkills: () => apiMocks.listSkills(),
  toggleSkill: (...args: unknown[]) => apiMocks.toggleSkill(...args),
}));

import { SkillConfigPanel } from "@/components/layout/skill-config-panel";

function renderPanel(ui: ReactNode) {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>{ui}</LanguageContext.Provider>
    </QueryClientProvider>
  );
}

function buildSkillsResponse() {
  return {
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
        content_hash: "hash123",
        path: "configs/skills/demo",
        scopes: ["/demo"],
        manageable: true,
        deletable: true,
        readonly_reason: null,
      },
    ],
  };
}

describe("SkillConfigPanel", () => {
  beforeEach(() => {
    apiMocks.deleteSkill.mockReset();
    apiMocks.listSkills.mockReset();
    apiMocks.toggleSkill.mockReset();
    apiMocks.listSkills.mockResolvedValue(buildSkillsResponse());
    apiMocks.toggleSkill.mockResolvedValue({
      ...buildSkillsResponse().skills[1],
      enabled: false,
    });
    apiMocks.deleteSkill.mockResolvedValue({ deleted: true, name: "demo" });
    vi.stubGlobal("confirm", vi.fn(() => true));
  });

  it("renders builtin skills as read-only and installed skills as manageable", async () => {
    renderPanel(<SkillConfigPanel />);

    expect(await screen.findByText("Studio Skills")).toBeInTheDocument();
    expect(screen.getByText("Installed Skills")).toBeInTheDocument();

    const noteRow = screen.getByText("/note").closest(".control-panel-skill-row");
    expect(noteRow).not.toBeNull();
    expect(within(noteRow as HTMLElement).getByText("Note and mark management skill")).toBeInTheDocument();
    expect(within(noteRow as HTMLElement).queryByRole("switch")).not.toBeInTheDocument();
    expect(within(noteRow as HTMLElement).queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();

    const demoRow = screen.getByText("/demo").closest(".control-panel-skill-row");
    expect(demoRow).not.toBeNull();
    expect(within(demoRow as HTMLElement).getByRole("switch", { name: "Toggle demo skill" })).toBeEnabled();
    expect(within(demoRow as HTMLElement).getByRole("button", { name: "Delete demo skill" })).toBeEnabled();
  });

  it("toggles and deletes installed skills", async () => {
    const user = userEvent.setup();
    renderPanel(<SkillConfigPanel />);

    await user.click(await screen.findByRole("switch", { name: "Toggle demo skill" }));

    await waitFor(() => {
      expect(apiMocks.toggleSkill).toHaveBeenCalledWith("demo", false);
    });

    await user.click(screen.getByRole("button", { name: "Delete demo skill" }));

    await waitFor(() => {
      expect(apiMocks.deleteSkill).toHaveBeenCalledWith("demo");
    });
  });
});
