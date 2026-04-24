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

  it("renders the upload trigger as a real button for browser interaction", async () => {
    const user = userEvent.setup();
    const { container } = renderLibraryPage();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement | null;

    expect(input).not.toBeNull();
    const clickSpy = vi.spyOn(input as HTMLInputElement, "click");

    const trigger = await screen.findByRole("button", {
      name: /upload documents/i,
    });

    expect(trigger).toBeInTheDocument();

    await user.click(trigger);

    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it("exposes html, ppt, and common image formats in the upload input and support hint", async () => {
    const { container } = renderLibraryPage();

    expect(
      await screen.findByText(/supports pdf, word, powerpoint, html, images, epub/i)
    ).toBeInTheDocument();

    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();
    expect(input?.getAttribute("accept")).toContain(".ppt");
    expect(input?.getAttribute("accept")).toContain(".pptx");
    expect(input?.getAttribute("accept")).toContain(".html");
    expect(input?.getAttribute("accept")).toContain(".htm");
    expect(input?.getAttribute("accept")).toContain(".png");
    expect(input?.getAttribute("accept")).toContain(".jpg");
    expect(input?.getAttribute("accept")).toContain(".jpeg");
    expect(input?.getAttribute("accept")).toContain(".gif");
    expect(input?.getAttribute("accept")).toContain(".jp2");
    expect(input?.getAttribute("accept")).toContain(".epub");
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
