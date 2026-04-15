import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentReader } from "@/components/reader/document-reader";
import { LanguageContext } from "@/lib/i18n/language-context";
import { useReaderStore } from "@/stores/reader-store";
import { useStudioStore } from "@/stores/studio-store";
import { createQueryClient } from "@/test/test-utils";

const documentApiMocks = vi.hoisted(() => ({
  getDocument: vi.fn(),
  getDocumentContent: vi.fn(),
}));

const markApiMocks = vi.hoisted(() => ({
  createMark: vi.fn(),
  listMarksByDocument: vi.fn(),
}));

vi.mock("@/lib/api/documents", () => ({
  getDocument: (...args: unknown[]) => documentApiMocks.getDocument(...args),
  getDocumentContent: (...args: unknown[]) => documentApiMocks.getDocumentContent(...args),
}));

vi.mock("@/lib/api/marks", () => ({
  createMark: (...args: unknown[]) => markApiMocks.createMark(...args),
  listMarksByDocument: (...args: unknown[]) => markApiMocks.listMarksByDocument(...args),
}));

function renderDocumentReader() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>
        <DocumentReader
          documentId="doc-1"
          onBack={() => {}}
          onExplain={() => {}}
          onConclude={() => {}}
        />
      </LanguageContext.Provider>
    </QueryClientProvider>
  );
}

describe("DocumentReader mark creation", () => {
  beforeEach(() => {
    documentApiMocks.getDocument.mockReset();
    documentApiMocks.getDocumentContent.mockReset();
    markApiMocks.createMark.mockReset();
    markApiMocks.listMarksByDocument.mockReset();

    documentApiMocks.getDocument.mockResolvedValue({
      document_id: "doc-1",
      title: "Doc",
      status: "completed",
      content_path: "doc/content.md",
    });
    documentApiMocks.getDocumentContent.mockResolvedValue({
      document_id: "doc-1",
      title: "Doc",
      format: "markdown",
      content: "Alpha beta gamma",
      page_count: 1,
      content_size: 16,
    });
    markApiMocks.listMarksByDocument.mockResolvedValue({ marks: [], total: 0 });

    useReaderStore.setState({
      currentDocumentId: "doc-1",
      activeMarkId: null,
      markScrollTrigger: 0,
      selection: {
        documentId: "doc-1",
        selectedText: "x".repeat(1001),
      },
      isSelecting: false,
      isTocOpen: true,
      isMenuVisible: true,
      menuPosition: { top: 12, left: 24 },
    });
    useStudioStore.setState({
      activeMarkId: null,
    });
  });

  it("does not send an overlong bookmark selection to the backend", async () => {
    const user = userEvent.setup();
    renderDocumentReader();

    await user.click(screen.getByRole("button", { name: /bookmark/i }));

    expect(markApiMocks.createMark).not.toHaveBeenCalled();
    await waitFor(() => {
      const toast = screen.getByRole("status");
      expect(toast).toHaveClass("reader-toast", "reader-toast-warning");
      expect(toast).toHaveTextContent(/selected text is too long/i);
      expect(toast).toHaveTextContent(/1,000/i);
    });
  });
});
