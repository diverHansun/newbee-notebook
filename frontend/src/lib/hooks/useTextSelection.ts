"use client";

import { RefObject, useEffect, useRef } from "react";

import { useReaderStore } from "@/stores/reader-store";

type UseTextSelectionOptions = {
  containerRef: RefObject<HTMLElement | null>;
  documentId: string;
};

export function useTextSelection({ containerRef, documentId }: UseTextSelectionOptions) {
  const isSelectingRef = useRef(false);
  const startedInContainerRef = useRef(false);
  const { setSelection, showMenu, hideMenu } = useReaderStore();

  useEffect(() => {
    const clearSelectionUi = () => {
      setSelection(null);
      hideMenu();
    };

    const isTargetInsideSelectionMenu = (target: EventTarget | null) => {
      if (!(target instanceof Node)) return false;
      const element = target instanceof Element ? target : target.parentElement;
      return Boolean(element?.closest("[data-selection-menu]"));
    };

    const isTargetInsideContainer = (target: EventTarget | null) => {
      const container = containerRef.current;
      return Boolean(container && target instanceof Node && container.contains(target));
    };

    const isSelectionBackward = (selection: Selection) => {
      if (!selection.anchorNode || !selection.focusNode) return false;
      if (selection.anchorNode === selection.focusNode) {
        return selection.focusOffset < selection.anchorOffset;
      }
      const position = selection.anchorNode.compareDocumentPosition(selection.focusNode);
      return Boolean(position & Node.DOCUMENT_POSITION_PRECEDING);
    };

    const getFocusCaretRect = (selection: Selection) => {
      if (!selection.focusNode) return null;
      try {
        const caretRange = document.createRange();
        caretRange.setStart(selection.focusNode, selection.focusOffset);
        caretRange.collapse(true);
        return caretRange.getClientRects()[0] || caretRange.getBoundingClientRect();
      } catch {
        return null;
      }
    };

    const getMenuPosition = (selection: Selection) => {
      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      const backward = isSelectionBackward(selection);
      const caretRect = backward ? getFocusCaretRect(selection) : null;

      const anchorTop = (caretRect?.top ?? rect.top) + window.scrollY;
      const menuTop = anchorTop - 44;
      const top = menuTop < window.scrollY + 12 ? rect.bottom + window.scrollY + 8 : menuTop;
      const left = backward
        ? (caretRect?.left ?? rect.left) + window.scrollX
        : rect.left + window.scrollX + rect.width / 2;

      return { top, left };
    };

    const showMenuFromCurrentSelection = () => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
        clearSelectionUi();
        return;
      }

      const text = selection.toString().trim();
      if (!text) {
        clearSelectionUi();
        return;
      }

      let range: Range;
      try {
        range = selection.getRangeAt(0);
      } catch {
        clearSelectionUi();
        return;
      }

      const container = containerRef.current;
      if (!container || !container.contains(range.commonAncestorContainer)) {
        clearSelectionUi();
        return;
      }

      setSelection({
        documentId,
        selectedText: text,
      });
      showMenu(getMenuPosition(selection));
    };

    const handleSelectionChange = () => {
      if (isSelectingRef.current) return;
      showMenuFromCurrentSelection();
    };

    const handleMouseDown = (event: MouseEvent) => {
      if (isTargetInsideSelectionMenu(event.target)) {
        return;
      }

      const startedInContainer = isTargetInsideContainer(event.target);
      startedInContainerRef.current = startedInContainer;
      isSelectingRef.current = startedInContainer;
      clearSelectionUi();
    };

    const handleMouseUp = () => {
      const shouldFinalizeSelection = startedInContainerRef.current || isSelectingRef.current;
      isSelectingRef.current = false;
      startedInContainerRef.current = false;

      if (!shouldFinalizeSelection) return;
      showMenuFromCurrentSelection();
    };

    document.addEventListener("selectionchange", handleSelectionChange);
    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("mouseup", handleMouseUp);
    window.addEventListener("scroll", hideMenu, true);

    return () => {
      document.removeEventListener("selectionchange", handleSelectionChange);
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("mouseup", handleMouseUp);
      window.removeEventListener("scroll", hideMenu, true);
    };
  }, [containerRef, documentId, hideMenu, setSelection, showMenu]);
}
