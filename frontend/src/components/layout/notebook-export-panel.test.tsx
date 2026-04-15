import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageContext } from "@/lib/i18n/language-context";
import { createQueryClient } from "@/test/test-utils";

const mocks = vi.hoisted(() => ({
  usePathname: vi.fn(),
  listAllNotebooks: vi.fn(),
  exportNotebook: vi.fn(),
  saveAs: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.usePathname(),
}));

vi.mock("@/lib/api/notebooks", () => ({
  listAllNotebooks: (...args: unknown[]) => mocks.listAllNotebooks(...args),
  exportNotebook: (...args: unknown[]) => mocks.exportNotebook(...args),
}));

vi.mock("file-saver", () => ({
  saveAs: (...args: unknown[]) => mocks.saveAs(...args),
}));

import { NotebookExportPanel } from "@/components/layout/notebook-export-panel";

function renderPanel() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>
        <NotebookExportPanel />
      </LanguageContext.Provider>
    </QueryClientProvider>
  );
}

describe("NotebookExportPanel", () => {
  beforeEach(() => {
    mocks.usePathname.mockReset();
    mocks.listAllNotebooks.mockReset();
    mocks.exportNotebook.mockReset();
    mocks.saveAs.mockReset();

    mocks.listAllNotebooks.mockResolvedValue({
      data: [
        {
          notebook_id: "nb-1",
          title: "Notebook One",
          description: "desc one",
          session_count: 2,
          document_count: 3,
          created_at: "2026-04-15T00:00:00Z",
          updated_at: "2026-04-15T00:00:00Z",
        },
        {
          notebook_id: "nb-2",
          title: "Notebook Two",
          description: "desc two",
          session_count: 1,
          document_count: 1,
          created_at: "2026-04-15T00:00:00Z",
          updated_at: "2026-04-15T00:00:00Z",
        },
      ],
      pagination: {
        total: 2,
        limit: 2,
        offset: 0,
        has_next: false,
        has_prev: false,
      },
    });
    mocks.exportNotebook.mockResolvedValue({
      blob: new Blob(["zip"], { type: "application/zip" }),
      filename: "Notebook One-export.zip",
    });
  });

  it("defaults to selecting current notebook on notebook detail page", async () => {
    mocks.usePathname.mockReturnValue("/notebooks/nb-1");
    renderPanel();

    const currentNotebookCheckbox = await screen.findByRole("checkbox", {
      name: "Notebook One",
    });
    expect(currentNotebookCheckbox).toBeChecked();

    const otherNotebookCheckbox = screen.getByRole("checkbox", {
      name: "Notebook Two",
    });
    expect(otherNotebookCheckbox).not.toBeChecked();
  });

  it("does not preselect notebooks on overview page", async () => {
    mocks.usePathname.mockReturnValue("/notebooks");
    renderPanel();

    const firstNotebookCheckbox = await screen.findByRole("checkbox", {
      name: "Notebook One",
    });
    expect(firstNotebookCheckbox).not.toBeChecked();
    expect(
      screen.getByRole("button", { name: /export selected notebooks/i })
    ).toBeDisabled();
  });

  it("continues exporting remaining notebooks and shows failures", async () => {
    mocks.usePathname.mockReturnValue("/notebooks/nb-1");
    mocks.exportNotebook
      .mockRejectedValueOnce(new Error("Notebook not found"))
      .mockResolvedValueOnce({
        blob: new Blob(["zip-2"], { type: "application/zip" }),
        filename: "Notebook Two-export.zip",
      });

    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("checkbox", { name: "Notebook Two" }));
    await user.click(screen.getByRole("button", { name: /export selected notebooks/i }));

    await waitFor(() => {
      expect(mocks.exportNotebook).toHaveBeenCalledTimes(2);
    });

    expect(mocks.exportNotebook).toHaveBeenNthCalledWith(1, "nb-1", [
      "documents",
      "notes",
      "marks",
      "diagrams",
      "video_summaries",
    ]);
    expect(mocks.exportNotebook).toHaveBeenNthCalledWith(2, "nb-2", [
      "documents",
      "notes",
      "marks",
      "diagrams",
      "video_summaries",
    ]);
    expect(mocks.saveAs).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/Failed notebook exports/i)).toBeInTheDocument();
  });

  it("sends only selected content types when exporting", async () => {
    mocks.usePathname.mockReturnValue("/notebooks/nb-1");
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("checkbox", { name: "Parsed documents" }));
    await user.click(screen.getByRole("checkbox", { name: "Video summaries" }));
    await user.click(screen.getByRole("button", { name: /export selected notebooks/i }));

    await waitFor(() => {
      expect(mocks.exportNotebook).toHaveBeenCalledTimes(1);
    });

    expect(mocks.exportNotebook).toHaveBeenCalledWith("nb-1", [
      "notes",
      "marks",
      "diagrams",
    ]);
  });
});
