"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type NotebookContextMenuProps = {
  x: number;
  y: number;
  onEdit: () => void;
  onDelete: () => void;
  onClose: () => void;
};

const MENU_WIDTH = 160;
const MENU_HEIGHT = 80;

export function NotebookContextMenu({ x, y, onEdit, onDelete, onClose }: NotebookContextMenuProps) {
  const { t } = useLang();
  const menuRef = useRef<HTMLDivElement>(null);

  const menuLeft = Math.min(x, window.innerWidth - MENU_WIDTH - 8);
  const menuTop = Math.min(y, window.innerHeight - MENU_HEIGHT - 8);

  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    function handleScroll() {
      onClose();
    }

    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("scroll", handleScroll, true);

    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("scroll", handleScroll, true);
    };
  }, [onClose]);

  return createPortal(
    <div
      ref={menuRef}
      className="notebook-context-menu"
      style={{ left: menuLeft, top: menuTop }}
    >
      <button
        className="notebook-context-menu-item"
        type="button"
        onClick={() => { onEdit(); onClose(); }}
      >
        {t(uiStrings.notebooksPage.contextMenuEdit)}
      </button>
      <button
        className="notebook-context-menu-item notebook-context-menu-item--danger"
        type="button"
        onClick={() => { onDelete(); onClose(); }}
      >
        {t(uiStrings.common.delete)}
      </button>
    </div>,
    document.body,
  );
}
