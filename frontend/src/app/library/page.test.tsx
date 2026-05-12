import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LibraryPage from "@/app/library/page";
import { LanguageContext } from "@/lib/i18n/language-context";
import { createQueryClient } from "@/test/test-utils";

const mockListLibraryDocuments = vi.fn();
const mockUploadDocumentsToLibrary = vi.fn();
const mockDeleteLibraryDocument = vi.fn();

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("@/lib/api/library", () => ({
  listLibraryDocuments: (...args: unknown[]) => mockListLibraryDocuments(...args),
  deleteLibraryDocument: (...args: unknown[]) => mockDeleteLibraryDocument(...args),
}));

vi.mock("@/lib/api/documents", () => ({
  uploadDocumentsToLibrary: (...args: unknown[]) => mockUploadDocumentsToLibrary(...args),
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
  ConfirmDialog: () => null,
}));

function renderLibraryPage() {
  const queryClient = createQueryClient();

  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>
        <LibraryPage />
      </LanguageContext.Provider>
    </QueryClientProvider>
  );
}

function libraryDocument(overrides: Partial<{
  document_id: string;
  title: string;
  content_type: string;
  status: string;
  created_at: string;
}> = {}) {
  return {
    document_id: overrides.document_id ?? "d1",
    title: overrides.title ?? "Sample Document",
    content_type: overrides.content_type ?? "pdf",
    status: overrides.status ?? "completed",
    library_id: "lib",
    notebook_id: null,
    page_count: 1,
    chunk_count: 1,
    file_size: 100,
    created_at: overrides.created_at ?? "2026-04-01T00:00:00Z",
    updated_at: overrides.created_at ?? "2026-04-01T00:00:00Z",
  };
}

describe("LibraryPage", () => {
  beforeEach(() => {
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
    mockUploadDocumentsToLibrary.mockResolvedValue(undefined);
    mockDeleteLibraryDocument.mockResolvedValue(undefined);
  });

  it("exposes ppt, pptx and epub in the upload input and support hint", async () => {
    const { container } = renderLibraryPage();

    expect(await screen.findByText(/supports pdf, word, powerpoint, epub/i)).toBeInTheDocument();

    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();
    const acceptedExtensions = input?.getAttribute("accept")?.split(",") ?? [];
    expect(acceptedExtensions).toEqual(expect.arrayContaining([".ppt", ".pptx", ".epub"]));
  });

  it("renders the file type column with uppercase extension badge", async () => {
    mockListLibraryDocuments.mockResolvedValue({
      data: [
        libraryDocument({
          title: "Sample PPT",
          content_type: "pptx",
        }),
      ],
      pagination: { total: 1, limit: 100, offset: 0, has_next: false, has_prev: false },
    });

    renderLibraryPage();

    expect(await screen.findByText("Sample PPT")).toBeInTheDocument();
    expect(screen.getByText("PPTX")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /^Type$/i })).toBeInTheDocument();
  });

  it("wraps the data table in a horizontal scroll region", async () => {
    mockListLibraryDocuments.mockResolvedValue({
      data: [libraryDocument({ title: "Wide table document" })],
      pagination: { total: 1, limit: 100, offset: 0, has_next: false, has_prev: false },
    });

    renderLibraryPage();

    expect(await screen.findByText("Wide table document")).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(table.parentElement).toHaveClass("library-table-scroll");
    expect(table).toHaveClass("library-data-table");
  });

  it("passes selected type groups as contentTypes when a chip is toggled", async () => {
    const user = userEvent.setup();
    renderLibraryPage();

    await screen.findByRole("button", { name: /Slides/i });

    mockListLibraryDocuments.mockClear();
    await user.click(screen.getByRole("button", { name: /Slides/i }));

    await screen.findByRole("button", { name: /Clear filters/i });

    const lastCall = mockListLibraryDocuments.mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({
      contentTypes: ["pptx"],
    });
  });

  it("clears type filter via the Clear filters button", async () => {
    const user = userEvent.setup();
    renderLibraryPage();

    await user.click(await screen.findByRole("button", { name: /Spreadsheet/i }));
    await screen.findByText(/1 selected/i);

    mockListLibraryDocuments.mockClear();
    await user.click(screen.getByRole("button", { name: /Clear filters/i }));

    expect(screen.queryByRole("button", { name: /Clear filters/i })).not.toBeInTheDocument();
    const lastCall = mockListLibraryDocuments.mock.calls.at(-1);
    expect(lastCall?.[0].contentTypes).toBeUndefined();
  });

  it("clears selected rows when the status filter changes", async () => {
    const user = userEvent.setup();
    mockListLibraryDocuments.mockResolvedValue({
      data: [libraryDocument({ title: "Selected PDF" })],
      pagination: { total: 1, limit: 100, offset: 0, has_next: false, has_prev: false },
    });

    renderLibraryPage();

    expect(await screen.findByText("Selected PDF")).toBeInTheDocument();
    await user.click(screen.getAllByRole("checkbox")[1]);
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Completed/i }));

    expect(screen.queryByText(/1 selected/i)).not.toBeInTheDocument();
  });

  it("clears selected rows when the type filter changes", async () => {
    const user = userEvent.setup();
    mockListLibraryDocuments.mockResolvedValue({
      data: [libraryDocument({ title: "Selected slide", content_type: "pptx" })],
      pagination: { total: 1, limit: 100, offset: 0, has_next: false, has_prev: false },
    });

    renderLibraryPage();

    expect(await screen.findByText("Selected slide")).toBeInTheDocument();
    await user.click(screen.getAllByRole("checkbox")[1]);
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Slides/i }));

    expect(screen.queryByRole("button", { name: /Batch delete/i })).not.toBeInTheDocument();
  });

  it("shows a visible failure message when the upload API reports rejected files", async () => {
    const user = userEvent.setup();
    mockUploadDocumentsToLibrary.mockResolvedValue({
      documents: [],
      total: 0,
      failed: [
        {
          filename: "demo.epub",
          reason: "Unsupported file type: .epub",
        },
      ],
    });

    const { container } = renderLibraryPage();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement | null;

    expect(input).not.toBeNull();
    await user.upload(
      input as HTMLInputElement,
      new File(["demo"], "demo.epub", { type: "application/epub+zip" })
    );

    expect(await screen.findByText(/demo\.epub/i)).toBeInTheDocument();
    expect(await screen.findByText(/unsupported file type: \.epub/i)).toBeInTheDocument();
  });
});
