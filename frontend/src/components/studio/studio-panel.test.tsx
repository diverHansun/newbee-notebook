import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageContext } from "@/lib/i18n/language-context";
import { useStudioStore } from "@/stores/studio-store";
import { createQueryClient } from "@/test/test-utils";

const mocks = vi.hoisted(() => ({
  listDocumentsInNotebook: vi.fn(),
  listMarksByNotebook: vi.fn(),
  deleteMark: vi.fn(),
  createNote: vi.fn(),
  deleteNote: vi.fn(),
  exportNoteMarkdown: vi.fn(),
  getNote: vi.fn(),
  listNotes: vi.fn(),
  updateNote: vi.fn(),
  addNoteDocument: vi.fn(),
  removeNoteDocument: vi.fn(),
  useDiagrams: vi.fn(),
  useDiagram: vi.fn(),
  useDiagramContent: vi.fn(),
  useDeleteDiagram: vi.fn(),
  clipboardWriteText: vi.fn(),
  saveAs: vi.fn(),
}));

vi.mock("@/lib/api/documents", () => ({
  listDocumentsInNotebook: mocks.listDocumentsInNotebook,
}));

vi.mock("@/lib/api/marks", () => ({
  deleteMark: mocks.deleteMark,
  listMarksByNotebook: mocks.listMarksByNotebook,
}));

vi.mock("@/lib/api/notes", () => ({
  addNoteDocument: mocks.addNoteDocument,
  createNote: mocks.createNote,
  deleteNote: mocks.deleteNote,
  exportNoteMarkdown: mocks.exportNoteMarkdown,
  getNote: mocks.getNote,
  listNotes: mocks.listNotes,
  removeNoteDocument: mocks.removeNoteDocument,
  updateNote: mocks.updateNote,
}));

vi.mock("file-saver", () => ({
  saveAs: (...args: unknown[]) => mocks.saveAs(...args),
}));

vi.mock("@/lib/hooks/use-diagrams", () => ({
  useDeleteDiagram: mocks.useDeleteDiagram,
  useDiagram: mocks.useDiagram,
  useDiagramContent: mocks.useDiagramContent,
  useDiagrams: mocks.useDiagrams,
}));

vi.mock("@/components/studio/diagram-viewer", () => ({
  DiagramViewer: () => <div data-testid="diagram-viewer" />,
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
  ConfirmDialog: () => null,
}));

import { StudioPanel } from "@/components/studio/studio-panel";

function renderPanel() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>
        <StudioPanel notebookId="notebook-1" onOpenDocument={() => {}} />
      </LanguageContext.Provider>
    </QueryClientProvider>
  );
}

describe("StudioPanel diagrams", () => {
  beforeEach(() => {
    useStudioStore.setState({
      studioView: "diagrams",
      activeNoteId: null,
      activeDiagramId: null,
      activeMarkId: null,
      noteDocFilter: null,
      markDocFilter: null,
      navigateTo: (view) => useStudioStore.setState({ studioView: view }),
      openNoteEditor: (noteId) =>
        useStudioStore.setState({ studioView: "note-detail", activeNoteId: noteId }),
      openDiagramDetail: (diagramId) =>
        useStudioStore.setState({ studioView: "diagram-detail", activeDiagramId: diagramId }),
      backToList: () => useStudioStore.setState({ studioView: "notes", activeNoteId: null }),
      backToDiagramList: () =>
        useStudioStore.setState({ studioView: "diagrams", activeDiagramId: null }),
      backToHome: () =>
        useStudioStore.setState({
          studioView: "home",
          activeNoteId: null,
          activeDiagramId: null,
          activeMarkId: null,
        }),
      setActiveMarkId: (markId) =>
        useStudioStore.setState({
          studioView: "notes",
          activeMarkId: markId,
        }),
      setNoteDocFilter: (documentId) => useStudioStore.setState({ noteDocFilter: documentId }),
      setMarkDocFilter: (documentId) => useStudioStore.setState({ markDocFilter: documentId }),
    });

    mocks.listDocumentsInNotebook.mockResolvedValue({
      data: [],
      pagination: {
        total: 0,
        limit: 100,
        offset: 0,
        has_next: false,
        has_prev: false,
      },
    });
    mocks.listNotes.mockResolvedValue({ notes: [] });
    mocks.listMarksByNotebook.mockResolvedValue({ marks: [] });
    mocks.useDiagrams.mockReturnValue({
      data: {
        diagrams: [
          {
            diagram_id: "diag-flow-001",
            notebook_id: "notebook-1",
            title: "Course Flow",
            diagram_type: "flowchart",
            format: "mermaid",
            document_ids: ["doc-1"],
            node_positions: null,
            created_at: "2026-03-20T00:00:00Z",
            updated_at: "2026-03-20T00:00:00Z",
          },
        ],
        total: 1,
      },
      isLoading: false,
    });
    mocks.useDiagram.mockReturnValue({ data: null, isLoading: false });
    mocks.useDiagramContent.mockReturnValue({ data: "", isLoading: false, isError: false });
    mocks.useDeleteDiagram.mockReturnValue({ isPending: false, mutateAsync: vi.fn() });
    mocks.clipboardWriteText.mockReset();
    mocks.exportNoteMarkdown.mockReset();
    mocks.saveAs.mockReset();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: mocks.clipboardWriteText,
      },
    });
  });

  it("shows a copyable diagram ID chip and hides format/doc badges", async () => {
    renderPanel();

    expect(await screen.findByText("Course Flow")).toBeInTheDocument();
    expect(screen.getByText("Flowchart")).toBeInTheDocument();
    expect(screen.queryByText("mermaid")).not.toBeInTheDocument();
    expect(screen.queryByText("1 docs")).not.toBeInTheDocument();

    const copyIdButton = screen.getByTestId("diagram-id-text-diag-flow-001");
    expect(copyIdButton).toHaveTextContent("Copy ID");

    fireEvent.click(copyIdButton);

    expect(mocks.clipboardWriteText).toHaveBeenCalledWith("diag-flow-001");
  });

  it("downloads note markdown via backend export endpoint in note detail", async () => {
    useStudioStore.setState({
      studioView: "note-detail",
      activeNoteId: "note-1",
      activeDiagramId: null,
      activeVideoId: null,
      activeMarkId: null,
    });
    mocks.getNote.mockResolvedValue({
      note_id: "note-1",
      notebook_id: "notebook-1",
      title: "My Note",
      content: "# Note Body",
      document_ids: [],
      mark_ids: [],
      created_at: "2026-04-15T00:00:00Z",
      updated_at: "2026-04-15T00:00:00Z",
    });
    mocks.exportNoteMarkdown.mockResolvedValue({
      blob: new Blob(["# Note Body"], { type: "text/markdown;charset=utf-8" }),
      filename: "My Note_note-1.md",
    });

    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("button", { name: /export markdown/i }));

    await waitFor(() => {
      expect(mocks.exportNoteMarkdown).toHaveBeenCalledWith("note-1");
    });
    expect(mocks.saveAs).toHaveBeenCalledTimes(1);
  });
});
