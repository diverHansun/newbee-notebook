"use client";

import { create } from "zustand";

export type MainViewMode = "chat" | "reader";

type UiState = {
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  mainView: MainViewMode;
  setMainView: (mode: MainViewMode) => void;
  toggleLeft: () => void;
  toggleRight: () => void;
};

export const useUiStore = create<UiState>((set) => ({
  leftCollapsed: false,
  rightCollapsed: false,
  mainView: "chat",
  setMainView: (mode) => set({ mainView: mode }),
  toggleLeft: () => set((state) => ({ leftCollapsed: !state.leftCollapsed })),
  toggleRight: () => set((state) => ({ rightCollapsed: !state.rightCollapsed })),
}));
