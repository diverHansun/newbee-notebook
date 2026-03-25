"use client";

import { create } from "zustand";

type SelectionState = {
  documentId: string;
  selectedText: string;
};

type MenuPosition = {
  top: number;
  left: number;
};

type ReaderState = {
  currentDocumentId: string | null;
  activeMarkId: string | null;
  markScrollTrigger: number;
  selection: SelectionState | null;
  isSelecting: boolean;
  isTocOpen: boolean;
  isMenuVisible: boolean;
  menuPosition: MenuPosition | null;
  openDocument: (documentId: string, markId?: string | null) => void;
  closeDocument: () => void;
  setActiveMarkId: (markId: string | null) => void;
  setSelection: (selection: SelectionState | null) => void;
  setIsSelecting: (value: boolean) => void;
  setTocOpen: (open: boolean) => void;
  toggleToc: () => void;
  showMenu: (position: MenuPosition) => void;
  hideMenu: () => void;
};

export const useReaderStore = create<ReaderState>((set) => ({
  currentDocumentId: null,
  activeMarkId: null,
  markScrollTrigger: 0,
  selection: null,
  isSelecting: false,
  isTocOpen: true,
  isMenuVisible: false,
  menuPosition: null,
  openDocument: (documentId, markId = null) =>
    set((state) => ({
      currentDocumentId: documentId,
      activeMarkId: markId,
      markScrollTrigger: markId != null ? state.markScrollTrigger + 1 : state.markScrollTrigger,
      selection: null,
      isSelecting: false,
      isMenuVisible: false,
      menuPosition: null,
    })),
  closeDocument: () =>
    set({
      currentDocumentId: null,
      activeMarkId: null,
      selection: null,
      isSelecting: false,
      isMenuVisible: false,
      menuPosition: null,
    }),
  setActiveMarkId: (markId) =>
    set((state) => ({
      activeMarkId: markId,
      markScrollTrigger: markId != null ? state.markScrollTrigger + 1 : state.markScrollTrigger,
    })),
  setSelection: (selection) => set({ selection }),
  setIsSelecting: (value) => set({ isSelecting: value }),
  setTocOpen: (open) => set({ isTocOpen: open }),
  toggleToc: () => set((state) => ({ isTocOpen: !state.isTocOpen })),
  showMenu: (position) => set({ isMenuVisible: true, menuPosition: position }),
  hideMenu: () => set({ isMenuVisible: false, menuPosition: null }),
}));
