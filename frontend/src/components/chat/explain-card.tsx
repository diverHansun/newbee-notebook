"use client";

import { useEffect, useRef, useState } from "react";

import { MarkdownViewer } from "@/components/reader/markdown-viewer";
import { useDraggable } from "@/lib/hooks/useDraggable";
import { useLang } from "@/lib/hooks/useLang";
import { useResizable } from "@/lib/hooks/useResizable";
import { uiStrings } from "@/lib/i18n/strings";
import type { ExplainCardError, ExplainCardState } from "@/stores/chat-store";

type ExplainCardProps = {
  card: ExplainCardState | null;
  onRetry?: () => void;
};

const DEFAULT_WIDTH = 520;
const DEFAULT_HEIGHT = 680;

function SelectedTextQuote({ label, text }: { label: string; text: string }) {
  if (!text) return null;
  return (
    <div className="explain-card-quote" aria-label={label}>
      <span className="explain-card-quote-label">{label}</span>
      <blockquote className="explain-card-quote-body">{text}</blockquote>
    </div>
  );
}

function Loader({ label }: { label: string }) {
  return (
    <div className="explain-card-loader" role="status" aria-label={label}>
      <span className="explain-card-loader-dot" aria-hidden="true" />
    </div>
  );
}

function EmptyState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="explain-card-empty">
      <p className="explain-card-empty-title">{title}</p>
      <p className="explain-card-empty-hint">{hint}</p>
    </div>
  );
}

function ErrorBlock({
  error,
  onRetry,
  retryLabel,
  title,
}: {
  error: ExplainCardError;
  onRetry?: () => void;
  retryLabel: string;
  title: string;
}) {
  return (
    <div className="explain-card-error" role="alert" data-error-code={error.code}>
      <div className="explain-card-error-title">{title}</div>
      <p className="explain-card-error-message">{error.message}</p>
      {error.retryable && onRetry && (
        <button type="button" className="btn btn-ghost btn-sm" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}

const DEFAULT_ANCHOR_TOP = 60;
const DEFAULT_ANCHOR_RIGHT = 8;
const ANCHOR_MARGIN = 8;

function readMainPanelAnchor(): { top: number; right: number } {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return { top: DEFAULT_ANCHOR_TOP, right: DEFAULT_ANCHOR_RIGHT };
  }
  const el = document.getElementById("main-panel-section");
  if (!el) return { top: DEFAULT_ANCHOR_TOP, right: DEFAULT_ANCHOR_RIGHT };
  const rect = el.getBoundingClientRect();
  return {
    top: rect.top + ANCHOR_MARGIN,
    right: Math.max(ANCHOR_MARGIN, window.innerWidth - rect.right + ANCHOR_MARGIN),
  };
}

export function ExplainCard({ card, onRetry }: ExplainCardProps) {
  const { t } = useLang();
  const [collapsed, setCollapsed] = useState(true);
  const [anchor, setAnchor] = useState<{ top: number; right: number }>({
    top: DEFAULT_ANCHOR_TOP,
    right: DEFAULT_ANCHOR_RIGHT,
  });
  const prevCardKeyRef = useRef<string | null>(null);

  const { position, onPointerDown, isDragging, resetPosition } = useDraggable({
    initialPosition: { x: 0, y: 0 },
  });

  const { size, onResizePointerDown, isResizing } = useResizable({
    initialSize: { width: DEFAULT_WIDTH, height: DEFAULT_HEIGHT },
    minSize: { width: 380, height: 400 },
    maxSize: { width: 720, height: 900 },
  });

  useEffect(() => {
    if (!card?.visible) return;
    const key = card.lastInteractionKey || `${card.mode}::${card.selectedText}`;
    if (key !== prevCardKeyRef.current) {
      prevCardKeyRef.current = key;
      setCollapsed(false);
      resetPosition({ x: 0, y: 0 });
      setAnchor(readMainPanelAnchor());
    }
  }, [card?.visible, card?.lastInteractionKey, card?.mode, card?.selectedText, resetPosition]);

  useEffect(() => {
    if (collapsed) return;
    setAnchor(readMainPanelAnchor());
    const onResize = () => setAnchor(readMainPanelAnchor());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [collapsed]);

  const modeLabel =
    card?.mode === "explain"
      ? t(uiStrings.explainCard.titleExplain)
      : card?.mode === "conclude"
        ? t(uiStrings.explainCard.titleConclude)
        : t(uiStrings.explainCard.titleDefault);
  const pillMode = card?.mode ?? "default";
  const hasContent = card?.visible && (card.content || card.isStreaming || card.error);
  const interactionKey = card?.lastInteractionKey ?? "empty";

  const expand = () => {
    resetPosition({ x: 0, y: 0 });
    setCollapsed(false);
  };

  const renderBody = () => {
    const content = card?.content ?? "";
    const selectedText = card?.selectedText ?? "";
    const quote = (
      <SelectedTextQuote
        label={t(uiStrings.explainCard.quotedTextLabel)}
        text={selectedText}
      />
    );

    if (card?.error) {
      return (
        <>
          {quote}
          <ErrorBlock
            error={card.error}
            onRetry={onRetry}
            retryLabel={t(uiStrings.explainCard.errorRetry)}
            title={t(uiStrings.explainCard.errorTitle)}
          />
          {content && (
            <div className="explain-card-content">
              <MarkdownViewer content={content} />
            </div>
          )}
        </>
      );
    }

    if (!content && card?.isStreaming) {
      return (
        <>
          {quote}
          <Loader label={t(uiStrings.explainCard.loading)} />
        </>
      );
    }

    if (!content) {
      return (
        <EmptyState
          title={t(uiStrings.explainCard.emptyTitle)}
          hint={t(uiStrings.explainCard.emptyHint)}
        />
      );
    }

    return (
      <>
        {quote}
        <div className="explain-card-content">
          <MarkdownViewer content={content} />
        </div>
      </>
    );
  };

  if (collapsed) {
    return (
      <div
        className="explain-card-pill"
        onClick={expand}
        title={t(uiStrings.explainCard.expandTitle)}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            expand();
          }
        }}
      >
        <span className="explain-card-pill-label" data-mode={pillMode}>
          {modeLabel}
        </span>
        {hasContent && (
          <span className="explain-card-pill-hint">
            {card.isStreaming
              ? t(uiStrings.explainCard.loading)
              : t(uiStrings.explainCard.clickToExpand)}
          </span>
        )}
        {card?.isStreaming && <span className="explain-card-pill-dot" aria-hidden="true" />}
      </div>
    );
  }

  return (
    <aside
      className="explain-card"
      style={{
        top: anchor.top,
        right: anchor.right,
        width: size.width,
        height: size.height,
        maxWidth: `calc(100vw - ${anchor.right + 8}px)`,
        maxHeight: `calc(100vh - ${anchor.top + 8}px)`,
        transform: `translate(${position.x}px, ${position.y}px)`,
        transition: isDragging || isResizing ? "none" : "box-shadow 200ms ease-out",
      }}
      aria-label={modeLabel}
    >
      <div className="explain-card-titlebar" onPointerDown={onPointerDown}>
        <div className="explain-card-title" data-mode={pillMode}>
          <span className="explain-card-mode-dot" aria-hidden="true" />
          <span className="explain-card-mode-text">{modeLabel}</span>
        </div>
        <button
          className="btn btn-ghost btn-icon btn-sm"
          type="button"
          onPointerDown={(event) => event.stopPropagation()}
          onClick={() => setCollapsed(true)}
          title={t(uiStrings.explainCard.collapseTitle)}
          aria-label={t(uiStrings.explainCard.collapseTitle)}
        >
          <span aria-hidden="true">-</span>
        </button>
      </div>

      <div className="explain-card-body" key={interactionKey}>
        {renderBody()}
      </div>

      <div
        className="explain-card-resize-handle"
        onPointerDown={onResizePointerDown}
        aria-hidden="true"
      />
    </aside>
  );
}
