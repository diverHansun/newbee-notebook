"use client";

import { create } from "zustand";

export type StudioView =
  | "home"
  | "notes"
  | "note-detail"
  | "diagrams"
  | "diagram-detail"
  | "videos"
  | "video-detail";

export type VideoFilterMode = "all" | "notebook";

type StudioState = {
  studioView: StudioView;
  activeNoteId: string | null;
  activeDiagramId: string | null;
  activeVideoId: string | null;
  activeMarkId: string | null;
  videoFilterMode: VideoFilterMode;
  /** Filter notes by associated document ID (null = show all) */
  noteDocFilter: string | null;
  /** Filter marks by document ID within current notebook (null = show all) */
  markDocFilter: string | null;
  navigateTo: (view: StudioView) => void;
  openNoteEditor: (noteId: string) => void;
  openDiagramDetail: (diagramId: string) => void;
  openVideoDetail: (videoId: string) => void;
  backToList: () => void;
  backToDiagramList: () => void;
  backToVideoList: () => void;
  backToHome: () => void;
  setActiveMarkId: (markId: string | null) => void;
  setVideoFilterMode: (mode: VideoFilterMode) => void;
  setNoteDocFilter: (documentId: string | null) => void;
  setMarkDocFilter: (documentId: string | null) => void;
};

export const useStudioStore = create<StudioState>((set) => ({
  studioView: "home",
  activeNoteId: null,
  activeDiagramId: null,
  activeVideoId: null,
  activeMarkId: null,
  videoFilterMode: "all",
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
  openVideoDetail: (videoId) =>
    set({
      studioView: "video-detail",
      activeVideoId: videoId,
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
  backToVideoList: () =>
    set({
      studioView: "videos",
      activeVideoId: null,
    }),
  backToHome: () =>
    set({
      studioView: "home",
      activeNoteId: null,
      activeDiagramId: null,
      activeVideoId: null,
      activeMarkId: null,
    }),
  setActiveMarkId: (markId) =>
    set({
      studioView: "notes",
      activeMarkId: markId,
    }),
  setVideoFilterMode: (mode) => set({ videoFilterMode: mode }),
  setNoteDocFilter: (documentId) => set({ noteDocFilter: documentId }),
  setMarkDocFilter: (documentId) => set({ markDocFilter: documentId }),
}));
