"use client";

import { create } from "zustand";

export type StudioView = "home" | "notes" | "note-detail" | "diagrams" | "diagram-detail";

type StudioState = {
  studioView: StudioView;
  activeNoteId: string | null;
  activeDiagramId: string | null;
  activeMarkId: string | null;
  /** Filter notes by associated document ID (null = show all) */
  noteDocFilter: string | null;
  /** Filter marks by document ID within current notebook (null = show all) */
  markDocFilter: string | null;
  navigateTo: (view: StudioView) => void;
  openNoteEditor: (noteId: string) => void;
  openDiagramDetail: (diagramId: string) => void;
  backToList: () => void;
  backToDiagramList: () => void;
  backToHome: () => void;
  setActiveMarkId: (markId: string | null) => void;
  setNoteDocFilter: (documentId: string | null) => void;
  setMarkDocFilter: (documentId: string | null) => void;
};

export const useStudioStore = create<StudioState>((set) => ({
  studioView: "home",
  activeNoteId: null,
  activeDiagramId: null,
  activeMarkId: null,
  noteDocFilter: null,
  markDocFilter: null,
  navigateTo: (view) => set({ studioView: view }),
  openNoteEditor: (noteId) =>
    set({
      studioView: "note-detail",
      activeNoteId: noteId,
    }),
  openDiagramDetail: (diagramId) =>
    set({
      studioView: "diagram-detail",
      activeDiagramId: diagramId,
    }),
  backToList: () =>
    set({
      studioView: "notes",
      activeNoteId: null,
    }),
  backToDiagramList: () =>
    set({
      studioView: "diagrams",
      activeDiagramId: null,
    }),
  backToHome: () =>
    set({
      studioView: "home",
      activeNoteId: null,
      activeDiagramId: null,
      activeMarkId: null,
    }),
  setActiveMarkId: (markId) =>
    set({
      studioView: "notes",
      activeMarkId: markId,
    }),
  setNoteDocFilter: (documentId) => set({ noteDocFilter: documentId }),
  setMarkDocFilter: (documentId) => set({ markDocFilter: documentId }),
}));
