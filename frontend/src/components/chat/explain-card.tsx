"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { ExplainCardState } from "@/stores/chat-store";
import { MarkdownViewer } from "@/components/reader/markdown-viewer";
import { useDraggable } from "@/lib/hooks/useDraggable";
import { useResizable } from "@/lib/hooks/useResizable";

type ExplainCardProps = {
  card: ExplainCardState | null;
};

const DEFAULT_WIDTH = 400;
const DEFAULT_HEIGHT = 380;

export function ExplainCard({ card }: ExplainCardProps) {
  const [collapsed, setCollapsed] = useState(true);
  const prevCardKeyRef = useRef<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null);

  /* ── track the Main panel section for fixed-position anchoring ── */
  useEffect(() => {
    setMounted(true);

    let rafId: number | null = null;
    const updateAnchor = () => {
      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        const el = document.getElementById("main-panel-section");
        if (el) setAnchorRect(el.getBoundingClientRect());
      });
    };

    updateAnchor();

    const mainEl = document.getElementById("main-panel-section");
    const ro = mainEl ? new ResizeObserver(updateAnchor) : null;
    if (mainEl && ro) ro.observe(mainEl);

    const group = document.getElementById("notebook-panels");
    const mo = group ? new MutationObserver(updateAnchor) : null;
    if (group && mo)
      mo.observe(group, { attributes: true, subtree: true, attributeFilter: ["style"] });

    window.addEventListener("resize", updateAnchor);

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      ro?.disconnect();
      mo?.disconnect();
      window.removeEventListener("resize", updateAnchor);
    };
  }, []);

  const { position, onPointerDown, isDragging, resetPosition } = useDraggable({
    initialPosition: { x: 0, y: 0 },
  });

  const { size, onResizePointerDown, isResizing } = useResizable({
    initialSize: { width: DEFAULT_WIDTH, height: DEFAULT_HEIGHT },
    minSize: { width: 300, height: 180 },
    maxSize: { width: 600, height: 500 },
  });

  useEffect(() => {
    if (!card?.visible) return;
    const key = `${card.mode}::${card.selectedText}`;
    if (key !== prevCardKeyRef.current) {
      prevCardKeyRef.current = key;
      setCollapsed(false);
      resetPosition({ x: 0, y: 0 });
    }
  }, [card?.visible, card?.mode, card?.selectedText, resetPosition]);

  const hasContent = card?.visible && (card.content || card.isStreaming);
  const modeLabel =
    card?.mode === "explain" ? "解释" : card?.mode === "conclude" ? "总结" : "解释/总结";
  const badgeClass =
    card?.mode === "explain"
      ? "badge-explain"
      : card?.mode === "conclude"
        ? "badge-conclude"
        : "badge-bee";

  if (!mounted) return null;

  /* fixed-position anchor: top-right of the Main panel */
  const anchorTop = anchorRect ? anchorRect.top + 8 : 60;
  const anchorRight = anchorRect
    ? window.innerWidth - anchorRect.right + 8
    : 8;

  const pill = (
    <div
      className="explain-card-pill"
      onClick={() => setCollapsed(false)}
      title="点击展开解释/总结面板"
      role="button"
      tabIndex={0}
      style={{ top: anchorTop, right: anchorRight }}
    >
      <span className={`badge ${badgeClass}`} style={{ fontSize: 11 }}>
        {modeLabel}
      </span>
      {hasContent && (
        <span className="explain-card-pill-hint">
          {card.isStreaming ? "生成中..." : "点击展开"}
        </span>
      )}
      {card?.isStreaming && <span className="streaming-dot" />}
    </div>
  );

  const expandedCard = (
    <aside
      className="explain-card"
      style={{
        top: anchorTop + position.y,
        right: anchorRight - position.x,
        width: size.width,
        height: size.height,
        transition:
          isDragging || isResizing ? "none" : "box-shadow 200ms ease-out",
      }}
    >
      <div className="explain-card-titlebar" onPointerDown={onPointerDown}>
        <div className="row" style={{ minWidth: 0, gap: 8 }}>
          <span className={`badge ${badgeClass}`}>{modeLabel}</span>
          {card?.selectedText && (
            <span
              style={{
                fontSize: 12,
                color: "hsl(var(--muted-foreground))",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                maxWidth: 160,
              }}
            >
              {card.selectedText}
            </span>
          )}
        </div>
        <button
          className="btn btn-ghost btn-icon btn-sm"
          type="button"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => setCollapsed(true)}
          title="收起"
        >
          ▲
        </button>
      </div>

      <div className="explain-card-body">
        {card?.content ? (
          <MarkdownViewer content={card.content} />
        ) : (
          <div
            className="muted"
            style={{ fontSize: 13, padding: "20px 0", textAlign: "center" }}
          >
            {card?.isStreaming
              ? "正在生成内容..."
              : "选中文档中的文本，点击「解释」或「总结」"}
          </div>
        )}
        {card?.isStreaming && (
          <div className="row" style={{ marginTop: 8, gap: 6 }}>
            <span className="streaming-dot" />
            <span style={{ fontSize: 12, color: "hsl(var(--bee-amber))" }}>
              生成中...
            </span>
          </div>
        )}
      </div>

      <div
        className="explain-card-resize-handle"
        onPointerDown={onResizePointerDown}
      />
    </aside>
  );

  return createPortal(collapsed ? pill : expandedCard, document.body);
}
