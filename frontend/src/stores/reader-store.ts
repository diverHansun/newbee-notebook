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
  selection: SelectionState | null;
  isMenuVisible: boolean;
  menuPosition: MenuPosition | null;
  openDocument: (documentId: string) => void;
  closeDocument: () => void;
  setSelection: (selection: SelectionState | null) => void;
  showMenu: (position: MenuPosition) => void;
  hideMenu: () => void;
};

export const useReaderStore = create<ReaderState>((set) => ({
  currentDocumentId: null,
  selection: null,
  isMenuVisible: false,
  menuPosition: null,
  openDocument: (documentId) =>
    set({
      currentDocumentId: documentId,
      selection: null,
      isMenuVisible: false,
      menuPosition: null,
    }),
  closeDocument: () =>
    set({
      currentDocumentId: null,
      selection: null,
      isMenuVisible: false,
      menuPosition: null,
    }),
  setSelection: (selection) => set({ selection }),
  showMenu: (position) => set({ isMenuVisible: true, menuPosition: position }),
  hideMenu: () => set({ isMenuVisible: false, menuPosition: null }),
}));
