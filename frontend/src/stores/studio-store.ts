"use client";

import { create } from "zustand";

export type StudioView = "home" | "notes" | "note-detail";

type StudioState = {
  studioView: StudioView;
  activeNoteId: string | null;
  activeMarkId: string | null;
  docFilter: string | null;
  navigateTo: (view: StudioView) => void;
  openNoteEditor: (noteId: string) => void;
  backToList: () => void;
  backToHome: () => void;
  setActiveMarkId: (markId: string | null) => void;
  setDocFilter: (documentId: string | null) => void;
};

export const useStudioStore = create<StudioState>((set) => ({
  studioView: "home",
  activeNoteId: null,
  activeMarkId: null,
  docFilter: null,
  navigateTo: (view) => set({ studioView: view }),
  openNoteEditor: (noteId) =>
    set({
      studioView: "note-detail",
      activeNoteId: noteId,
    }),
  backToList: () =>
    set({
      studioView: "notes",
      activeNoteId: null,
    }),
  backToHome: () =>
    set({
      studioView: "home",
      activeNoteId: null,
      activeMarkId: null,
    }),
  setActiveMarkId: (markId) =>
    set({
      studioView: "notes",
      activeMarkId: markId,
    }),
  setDocFilter: (documentId) => set({ docFilter: documentId }),
}));
