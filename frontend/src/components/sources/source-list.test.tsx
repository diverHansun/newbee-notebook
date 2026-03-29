import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SourceList } from "@/components/sources/source-list";
import type { NotebookDocumentItem } from "@/lib/api/types";
import { LanguageContext } from "@/lib/i18n/language-context";
import { createQueryClient } from "@/test/test-utils";

const mockListDocumentsInNotebook = vi.fn();
const mockAddDocumentsToNotebook = vi.fn();
const mockRemoveDocumentFromNotebook = vi.fn();
const mockListLibraryDocuments = vi.fn();

vi.mock("@/lib/api/documents", () => ({
  listDocumentsInNotebook: (...args: unknown[]) => mockListDocumentsInNotebook(...args),
  addDocumentsToNotebook: (...args: unknown[]) => mockAddDocumentsToNotebook(...args),
  removeDocumentFromNotebook: (...args: unknown[]) => mockRemoveDocumentFromNotebook(...args),
}));

vi.mock("@/lib/api/library", () => ({
  listLibraryDocuments: (...args: unknown[]) => mockListLibraryDocuments(...args),
}));


vi.mock("@/components/sources/source-card", () => ({
  SourceCard: ({
    document,
    onRemove,
  }: {
    document: NotebookDocumentItem;
    onRemove: (document: NotebookDocumentItem) => void;
  }) => (
    <li>
      <span>{document.title}</span>
      <button type="button" onClick={() => onRemove(document)}>
        Remove {document.title}
      </button>
    </li>
  ),
}));

const documentRow: NotebookDocumentItem = {
  document_id: "doc-1",
  title: "Document One",
  status: "completed",
  content_type: "text/markdown",
  file_size: 100,
  page_count: 1,
  chunk_count: 1,
  created_at: "2026-03-19T00:00:00.000Z",
  added_at: "2026-03-19T00:00:00.000Z",
};


function renderSourceList() {
  const queryClient = createQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>
        <SourceList notebookId="nb-1" onOpenDocument={() => {}} />
      </LanguageContext.Provider>
    </QueryClientProvider>
  );
}

describe("SourceList", () => {
  beforeEach(() => {
    mockListDocumentsInNotebook.mockResolvedValue({
      data: [documentRow],
      pagination: {
        total: 1,
        limit: 100,
        offset: 0,
        has_next: false,
        has_prev: false,
      },
    });
    mockListLibraryDocuments.mockResolvedValue({
      data: [],
      pagination: {
        total: 0,
        limit: 100,
        offset: 0,
        has_next: false,
        has_prev: false,
      },
    });
    mockAddDocumentsToNotebook.mockResolvedValue(undefined);
    mockRemoveDocumentFromNotebook.mockResolvedValue(undefined);
  });

  it("shows a remove confirmation without bookmark warning", async () => {
    const user = userEvent.setup();
    render(renderSourceList());

    await user.click(await screen.findByRole("button", { name: "Remove Document One" }));

    expect(
      await screen.findByText(/Remove "Document One" from this notebook\?/)
    ).toBeInTheDocument();
    expect(screen.queryByText(/bookmarks/i)).not.toBeInTheDocument();
  });
});
