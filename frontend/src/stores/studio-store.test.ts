import { beforeEach, describe, expect, it } from "vitest";

import { useStudioStore } from "@/stores/studio-store";

describe("studio-store", () => {
  beforeEach(() => {
    useStudioStore.setState({
      studioView: "home",
      activeNoteId: null,
      activeDiagramId: null,
      activeMarkId: null,
      noteDocFilter: null,
      markDocFilter: null,
    });
  });

  it("navigates into note detail and back to the notes list", () => {
    useStudioStore.getState().navigateTo("notes");
    useStudioStore.getState().openNoteEditor("note-1");

    expect(useStudioStore.getState().studioView).toBe("note-detail");
    expect(useStudioStore.getState().activeNoteId).toBe("note-1");

    useStudioStore.getState().backToList();

    expect(useStudioStore.getState().studioView).toBe("notes");
    expect(useStudioStore.getState().activeNoteId).toBeNull();
  });

  it("keeps the selected mark when switching to the notes view", () => {
    useStudioStore.getState().setActiveMarkId("mark-1");

    expect(useStudioStore.getState().studioView).toBe("notes");
    expect(useStudioStore.getState().activeMarkId).toBe("mark-1");
  });

  it("navigates into diagram detail and back to diagram list", () => {
    useStudioStore.getState().navigateTo("diagrams");
    useStudioStore.getState().openDiagramDetail("diagram-1");

    expect(useStudioStore.getState().studioView).toBe("diagram-detail");
    expect(useStudioStore.getState().activeDiagramId).toBe("diagram-1");

    useStudioStore.getState().backToDiagramList();

    expect(useStudioStore.getState().studioView).toBe("diagrams");
    expect(useStudioStore.getState().activeDiagramId).toBeNull();
  });
});
