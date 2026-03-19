"use client";

import { useReaderStore } from "@/stores/reader-store";
import { useEffect, useRef } from "react";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type SelectionMenuProps = {
  onExplain: (payload: { documentId: string; selectedText: string }) => void;
  onConclude: (payload: { documentId: string; selectedText: string }) => void;
  onMark: (payload: { documentId: string; selectedText: string }) => void;
};

export function SelectionMenu({ onExplain, onConclude, onMark }: SelectionMenuProps) {
  const { t } = useLang();
  const { selection, isMenuVisible, menuPosition, hideMenu } = useReaderStore();
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isMenuVisible) return;
    const onClickOutside = (event: MouseEvent) => {
      if (!menuRef.current) return;
      if (event.target instanceof Node && !menuRef.current.contains(event.target)) {
        hideMenu();
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [hideMenu, isMenuVisible]);

  if (!isMenuVisible || !menuPosition || !selection) return null;

  return (
    <div
      ref={menuRef}
      data-selection-menu="true"
      className="selection-menu"
      style={{
        left: menuPosition.left,
        top: menuPosition.top,
        transform: "translateX(-50%)",
      }}
    >
      <button
        className="btn btn-ghost btn-sm"
        type="button"
        onClick={() => {
          hideMenu();
          onExplain({
            documentId: selection.documentId,
            selectedText: selection.selectedText,
          });
        }}
      >
        💡 {t(uiStrings.selectionMenu.explain)}
      </button>
      <button
        className="btn btn-ghost btn-sm"
        type="button"
        onClick={() => {
          hideMenu();
          onConclude({
            documentId: selection.documentId,
            selectedText: selection.selectedText,
          });
        }}
      >
        📝 {t(uiStrings.selectionMenu.conclude)}
      </button>
      <button
        className="btn btn-ghost btn-sm"
        type="button"
        onClick={() => {
          hideMenu();
          onMark({
            documentId: selection.documentId,
            selectedText: selection.selectedText,
          });
        }}
      >
        🔖 {t(uiStrings.selectionMenu.bookmark)}
      </button>
    </div>
  );
}
