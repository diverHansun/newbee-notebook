"use client";

import { RefObject, useEffect, useRef } from "react";

import { useReaderStore } from "@/stores/reader-store";

type UseTextSelectionOptions = {
  containerRef: RefObject<HTMLElement | null>;
  documentId: string;
};

export function useTextSelection({ containerRef, documentId }: UseTextSelectionOptions) {
  const timerRef = useRef<number | null>(null);
  const { setSelection, showMenu, hideMenu } = useReaderStore();

  useEffect(() => {
    const handler = () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }

      timerRef.current = window.setTimeout(() => {
        const selection = window.getSelection();
        if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
          setSelection(null);
          hideMenu();
          return;
        }

        const text = selection.toString().trim();
        if (!text) {
          setSelection(null);
          hideMenu();
          return;
        }

        const range = selection.getRangeAt(0);
        const container = containerRef.current;
        if (!container || !container.contains(range.commonAncestorContainer)) {
          setSelection(null);
          hideMenu();
          return;
        }

        const rect = range.getBoundingClientRect();
        const menuTop = rect.top + window.scrollY - 44;
        const top = menuTop < window.scrollY + 12 ? rect.bottom + window.scrollY + 8 : menuTop;
        const left = rect.left + window.scrollX + rect.width / 2;

        setSelection({
          documentId,
          selectedText: text,
        });
        showMenu({ top, left });
      }, 200);
    };

    document.addEventListener("selectionchange", handler);
    window.addEventListener("scroll", hideMenu, true);

    return () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }
      document.removeEventListener("selectionchange", handler);
      window.removeEventListener("scroll", hideMenu, true);
    };
  }, [containerRef, documentId, hideMenu, setSelection, showMenu]);
}
