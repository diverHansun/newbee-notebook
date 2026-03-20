"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { MarkdownViewer } from "@/components/reader/markdown-viewer";
import { SelectionMenu } from "@/components/reader/selection-menu";
import { TocSidebar } from "@/components/reader/toc-sidebar";
import { createMark, listMarksByDocument } from "@/lib/api/marks";
import { getDocument, getDocumentContent } from "@/lib/api/documents";
import { ApiError } from "@/lib/api/client";
import {
  extractTocItems,
  getCompactReaderWidthThreshold,
  type TocItem,
} from "@/lib/hooks/use-toc";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import { computeChunkOffsets, findChunkIndexByOffset } from "@/lib/reader/chunk-marks";
import {
  getInitialVisibleChunkCount,
  splitMarkdownIntoChunks,
} from "@/lib/reader/markdown-chunking";
import { useTextSelection } from "@/lib/hooks/useTextSelection";
import { useReaderStore } from "@/stores/reader-store";
import { useStudioStore } from "@/stores/studio-store";

type DocumentReaderProps = {
  documentId: string;
  onBack: () => void;
  onExplain: (payload: { documentId: string; selectedText: string }) => void;
  onConclude: (payload: { documentId: string; selectedText: string }) => void;
};

export function DocumentReader({
  documentId,
  onBack,
  onExplain,
  onConclude,
}: DocumentReaderProps) {
  const { t, ti } = useLang();
  const queryClient = useQueryClient();
  const viewerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const readerBodyRef = useRef<HTMLDivElement>(null);
  const isSelecting = useReaderStore((state) => state.isSelecting);
  const activeMarkId = useReaderStore((state) => state.activeMarkId);
  const setReaderActiveMarkId = useReaderStore((state) => state.setActiveMarkId);
  const isTocOpen = useReaderStore((state) => state.isTocOpen);
  const setTocOpen = useReaderStore((state) => state.setTocOpen);
  const toggleToc = useReaderStore((state) => state.toggleToc);
  const setStudioActiveMarkId = useStudioStore((state) => state.setActiveMarkId);
  const [isCompactReader, setIsCompactReader] = useState(false);
  const [visibleChunkCount, setVisibleChunkCount] = useState(1);
  const [markFeedback, setMarkFeedback] = useState<string | null>(null);
  const activeHighlightCleanupRef = useRef<(() => void) | null>(null);
  const activeMarkIdRef = useRef<string | null>(null);

  const documentQuery = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => getDocument(documentId),
    refetchInterval: (query) => {
      const doc = query.state.data;
      if (!doc) return false;
      if (doc.status === "uploaded" || doc.status === "pending" || doc.status === "processing") {
        return 3000;
      }
      if ((doc.status === "converted" || doc.status === "completed") && !doc.content_path) {
        return 3000;
      }
      return false;
    },
  });

  const status = documentQuery.data?.status;
  const canReadByStatus = status === "completed" || status === "converted";

  const contentQuery = useQuery({
    queryKey: ["document-content", documentId],
    queryFn: () => getDocumentContent(documentId, "markdown"),
    enabled: Boolean(documentId) && canReadByStatus,
  });

  useTextSelection({
    containerRef: viewerRef,
    documentId,
  });

  const markdownContent = contentQuery.data?.content || "";
  const tocItems = useMemo(() => extractTocItems(markdownContent), [markdownContent]);
  const shouldShowToc = tocItems.length > 0;
  const effectiveTocOpen = shouldShowToc && isTocOpen && !isCompactReader;
  const markdownChunks = useMemo(() => splitMarkdownIntoChunks(markdownContent), [markdownContent]);
  const chunkOffsets = useMemo(
    () => computeChunkOffsets(markdownContent, markdownChunks),
    [markdownChunks, markdownContent]
  );
  const totalChunkCount = markdownChunks.length;
  const initialVisibleChunkCount = useMemo(
    () => getInitialVisibleChunkCount(totalChunkCount),
    [totalChunkCount]
  );
  const marksQuery = useQuery({
    queryKey: ["marks", "document", documentId],
    queryFn: () => listMarksByDocument(documentId),
    enabled: Boolean(documentId) && canReadByStatus,
  });

  const createMarkMutation = useMutation({
    mutationFn: (input: { anchorText: string; charOffset: number; contextText?: string }) =>
      createMark(documentId, {
        anchor_text: input.anchorText,
        char_offset: input.charOffset,
        context_text: input.contextText,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["marks", "document", documentId] });
      void queryClient.invalidateQueries({ queryKey: ["marks", "notebook"] });
    },
  });

  useEffect(() => {
    setVisibleChunkCount(initialVisibleChunkCount);
  }, [documentId, markdownContent, initialVisibleChunkCount]);

  useEffect(() => {
    if (!markFeedback) return;
    const timerId = window.setTimeout(() => setMarkFeedback(null), 2500);
    return () => window.clearTimeout(timerId);
  }, [markFeedback]);

  useEffect(() => {
    if (typeof ResizeObserver === "undefined") return;
    const target = readerBodyRef.current;
    if (!target) return;

    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width || 0;
      setIsCompactReader(width > 0 && width < getCompactReaderWidthThreshold());
    });
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (isCompactReader && isTocOpen) {
      setTocOpen(false);
    }
  }, [isCompactReader, isTocOpen, setTocOpen]);

  const scrollToHeadingByOrder = (order: number) => {
    const attemptScroll = (attempt = 0) => {
      const headings = viewerRef.current?.querySelectorAll<HTMLElement>("h1[id], h2[id], h3[id], h4[id], h5[id], h6[id]");
      const target = headings?.[order] || null;

      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }

      if (attempt < 10) {
        window.requestAnimationFrame(() => attemptScroll(attempt + 1));
      }
    };

    attemptScroll();
  };

  const onTocItemClick = (item: TocItem) => {
    const neededChunkCount = Math.min(totalChunkCount, item.chunkIndex + 1);
    setVisibleChunkCount((prev) => (prev < neededChunkCount ? neededChunkCount : prev));
    scrollToHeadingByOrder(item.order);
  };

  const onVisibleChunkCountChange = useCallback((next: number) => {
    setVisibleChunkCount((prev) => (prev === next ? prev : next));
  }, []);

  const handleMark = useCallback(
    async ({ documentId: selectedDocumentId, selectedText }: { documentId: string; selectedText: string }) => {
      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0) return;

      const range = selection.getRangeAt(0);
      const startNode =
        range.startContainer instanceof Element
          ? range.startContainer
          : range.startContainer.parentElement;
      const chunkElement = startNode?.closest<HTMLElement>("[data-chunk-index]");
      const chunkIndex = Number(chunkElement?.dataset.chunkIndex ?? "0");
      const chunk = chunkOffsets[chunkIndex];
      if (!chunk) return;

      const positionInChunk = chunk.content.indexOf(selectedText);
      const charOffset = chunk.startChar + Math.max(0, positionInChunk);

      try {
        const mark = await createMarkMutation.mutateAsync({
          anchorText: selectedText,
          charOffset,
          contextText: selectedText,
        });
        setReaderActiveMarkId(mark.mark_id);
        setStudioActiveMarkId(mark.mark_id);
        setMarkFeedback(t(uiStrings.reader.bookmarkCreated));
      } catch {
        setMarkFeedback(t(uiStrings.reader.bookmarkCreateFailed));
      }
    },
    [chunkOffsets, createMarkMutation, setReaderActiveMarkId, setStudioActiveMarkId, t]
  );

  useEffect(() => {
    const container = viewerRef.current;
    if (!container) return;

    const marks = marksQuery.data?.marks ?? [];
    const sections = Array.from(container.querySelectorAll<HTMLElement>("[data-chunk-index]"));

    sections.forEach((section) => {
      const chunkIndex = Number(section.dataset.chunkIndex ?? "-1");
      const chunk = chunkOffsets[chunkIndex];
      const existingButton = section.querySelector<HTMLButtonElement>(":scope > .mark-anchor-button");

      if (!chunk) {
        existingButton?.remove();
        section.removeAttribute("data-mark-ids");
        section.removeAttribute("data-active-mark");
        return;
      }

      const nextChunk = chunkOffsets[chunkIndex + 1];
      const chunkEnd = nextChunk ? nextChunk.startChar : chunk.startChar + chunk.content.length;
      const marksInChunk = marks.filter(
        (mark) => mark.char_offset >= chunk.startChar && mark.char_offset < chunkEnd
      );

      if (marksInChunk.length === 0) {
        section.removeAttribute("data-mark-ids");
        section.removeAttribute("data-active-mark");
        existingButton?.remove();
        return;
      }

      const markIds = marksInChunk.map((mark) => mark.mark_id);
      section.dataset.markIds = markIds.join(",");
      if (activeMarkId && markIds.includes(activeMarkId)) {
        section.dataset.activeMark = "true";
      } else {
        section.removeAttribute("data-active-mark");
      }

      const button = existingButton ?? document.createElement("button");
      button.type = "button";
      button.className = "mark-anchor-button";
      button.dataset.markIds = markIds.join(",");
      button.title = marksInChunk.map((mark) => mark.anchor_text).join(" | ");
      button.setAttribute("aria-label", t(uiStrings.marks.title));
      button.textContent = "🔖";
      button.onclick = (event) => {
        event.preventDefault();
        event.stopPropagation();
        const primaryMarkId = markIds[0];
        setReaderActiveMarkId(primaryMarkId);
        setStudioActiveMarkId(primaryMarkId);
      };

      if (!existingButton) {
        section.prepend(button);
      }
    });
  }, [activeMarkId, chunkOffsets, marksQuery.data?.marks, setReaderActiveMarkId, setStudioActiveMarkId, t, visibleChunkCount]);

  // Keep activeMarkIdRef in sync for stable closure in pointerdown handler
  useEffect(() => {
    activeMarkIdRef.current = activeMarkId;
  }, [activeMarkId]);

  // Clean up text highlight whenever activeMarkId changes
  useEffect(() => {
    return () => {
      activeHighlightCleanupRef.current?.();
      activeHighlightCleanupRef.current = null;
    };
  }, [activeMarkId]);

  // Precise scroll-to-text + transient highlight
  useEffect(() => {
    if (!activeMarkId || !marksQuery.data?.marks?.length) return;
    const targetMark = marksQuery.data.marks.find((item) => item.mark_id === activeMarkId);
    if (!targetMark) return;

    const chunkIndex = findChunkIndexByOffset(chunkOffsets, targetMark.char_offset);
    const requiredVisibleChunks = Math.min(totalChunkCount, chunkIndex + 1);
    if (visibleChunkCount < requiredVisibleChunks) {
      setVisibleChunkCount(requiredVisibleChunks);
      return;
    }

    let attempt = 0;
    const scrollToMark = () => {
      const chunkEl = viewerRef.current?.querySelector<HTMLElement>(
        `[data-chunk-index="${chunkIndex}"]`
      );
      if (!chunkEl) {
        if (attempt < 10) {
          attempt += 1;
          window.requestAnimationFrame(scrollToMark);
        }
        return;
      }

      // Clean up previous highlight before creating a new one
      activeHighlightCleanupRef.current?.();
      activeHighlightCleanupRef.current = null;

      const result = highlightTextInChunk(chunkEl, targetMark.anchor_text);
      if (result) {
        activeHighlightCleanupRef.current = result.cleanup;
        result.scrollIntoView(scrollContainerRef.current);
      } else {
        chunkEl.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    };

    scrollToMark();
  }, [activeMarkId, chunkOffsets, marksQuery.data?.marks, totalChunkCount, visibleChunkCount]);

  // Clear active mark when user clicks anywhere in the reader (except on the mark itself)
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (!activeMarkIdRef.current) return;
      const target = event.target as Element;
      if (target.closest(".mark-anchor-button") || target.closest(".mark-text-highlight")) return;
      setReaderActiveMarkId(null);
    };

    container.addEventListener("pointerdown", handlePointerDown);
    return () => container.removeEventListener("pointerdown", handlePointerDown);
  }, [setReaderActiveMarkId]);

  const renderBody = () => {
    if (documentQuery.isLoading) {
      return (
        <div className="stack-sm" style={{ padding: 24 }}>
          <div className="skeleton" style={{ height: 24, width: "40%" }} />
          <div className="skeleton" style={{ height: 16, width: "80%" }} />
          <div className="skeleton" style={{ height: 16, width: "60%" }} />
          <div className="skeleton" style={{ height: 16, width: "70%" }} />
        </div>
      );
    }

    if (documentQuery.isError) {
      return (
        <div className="empty-state">
          <span>{t(uiStrings.reader.loadFailed)}</span>
          <button className="btn btn-sm" type="button" onClick={() => documentQuery.refetch()}>
            {t(uiStrings.reader.retry)}
          </button>
        </div>
      );
    }

    if (!canReadByStatus) {
      const hint = statusHint(status, t);
      return (
        <div className="empty-state">
          <span className={`badge ${statusBadgeClass(status || "unknown")}`}>
            {status || "unknown"}
          </span>
          <span>{hint}</span>
        </div>
      );
    }

    if (contentQuery.isLoading) {
      return (
        <div className="stack-sm" style={{ padding: 24 }}>
          <div className="skeleton" style={{ height: 20, width: "50%" }} />
          <div className="skeleton" style={{ height: 14, width: "90%" }} />
          <div className="skeleton" style={{ height: 14, width: "75%" }} />
          <div className="skeleton" style={{ height: 14, width: "85%" }} />
          <div className="skeleton" style={{ height: 14, width: "65%" }} />
        </div>
      );
    }

    if (contentQuery.isError) {
      const err = contentQuery.error as ApiError;
      const friendlyMsg = contentErrorMessage(err, status, t, ti);
      return (
        <div className="empty-state">
          <span>{friendlyMsg}</span>
          <button className="btn btn-sm" type="button" onClick={() => contentQuery.refetch()}>
            {t(uiStrings.reader.retry)}
          </button>
        </div>
      );
    }

    return (
      <div style={{ padding: "8px 24px 24px" }}>
        {markFeedback ? (
          <div className="badge badge-default" style={{ marginBottom: 12 }}>
            {markFeedback}
          </div>
        ) : null}
        <MarkdownViewer
          content={markdownContent}
          documentId={documentId}
          containerRef={viewerRef}
          scrollRootRef={scrollContainerRef}
          freezeLazyLoad={isSelecting}
          visibleChunkCount={visibleChunkCount}
          onVisibleChunkCountChange={onVisibleChunkCountChange}
        />
      </div>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div
        className="row-between"
        style={{
          padding: "8px 16px",
          borderBottom: "1px solid hsl(var(--border))",
          flexShrink: 0,
        }}
      >
        <div className="row">
          <button className="btn btn-ghost btn-sm" type="button" onClick={onBack}>
            {t(uiStrings.reader.backToChat)}
          </button>
          <strong style={{ fontSize: 14, fontWeight: 600 }}>
            {documentQuery.data?.title || t(uiStrings.reader.documentFallbackTitle)}
          </strong>
        </div>
        {shouldShowToc ? (
          <button
            className="btn btn-ghost btn-sm"
            type="button"
            aria-pressed={effectiveTocOpen}
            onClick={toggleToc}
          >
            {t(uiStrings.reader.tocToggle)}
          </button>
        ) : null}
      </div>

      {/* Content */}
      <div ref={readerBodyRef} className="reader-body-layout" style={{ flex: 1 }}>
        {shouldShowToc ? (
          <TocSidebar
            items={tocItems}
            isOpen={effectiveTocOpen}
            title={t(uiStrings.reader.tocTitle)}
            scrollContainerRef={scrollContainerRef}
            activeTrackingEnabled={effectiveTocOpen}
            refreshKey={visibleChunkCount}
            onItemClick={onTocItemClick}
          />
        ) : null}
        <div ref={scrollContainerRef} className="reader-content-scroll">
          {renderBody()}
        </div>
      </div>

      <SelectionMenu onExplain={onExplain} onConclude={onConclude} onMark={handleMark} />
    </div>
  );
}

function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    uploaded: "badge-default",
    pending: "badge-default",
    processing: "badge-processing",
    converted: "badge-converted",
    completed: "badge-completed",
    failed: "badge-failed",
  };
  return map[status] || "badge-default";
}

function statusHint(status: string | undefined, t: ReturnType<typeof useLang>["t"]): string {
  switch (status) {
    case "processing":
      return t(uiStrings.reader.processing);
    case "pending":
    case "uploaded":
      return t(uiStrings.reader.pending);
    case "failed":
      return t(uiStrings.reader.failed);
    default:
      return t(uiStrings.reader.notReady);
  }
}

function contentErrorMessage(
  err: ApiError,
  status: string | undefined,
  t: ReturnType<typeof useLang>["t"],
  ti: ReturnType<typeof useLang>["ti"]
): string {
  if (err.errorCode === "E4001" && status === "converted") {
    return t(uiStrings.reader.convertedBlocked);
  }
  if (
    err.errorCode === "E_HTTP_DETAIL" &&
    err.message?.toLowerCase().includes("content not available")
  ) {
    return t(uiStrings.reader.contentPathMissing);
  }
  if (err.errorCode === "E4001") {
    return t(uiStrings.reader.processing);
  }
  return ti(uiStrings.reader.contentLoadFailedWithCode, {
    errorCode: err.errorCode || "E_UNKNOWN",
    message: err.message || "Unknown error",
  });
}

/**
 * Find anchor_text in the rendered DOM of a chunk and wrap it in a <mark> element.
 * Returns cleanup + scrollIntoView helpers, or null if text not found / wrapping fails.
 */
function highlightTextInChunk(
  chunkEl: HTMLElement,
  anchorText: string,
): { cleanup: () => void; scrollIntoView: (container: HTMLElement | null) => void } | null {
  // Use first 30 chars as the search snippet (avoids multi-element boundary issues)
  const searchSnippet = anchorText.slice(0, 30).trim();
  if (!searchSnippet) return null;

  const walker = document.createTreeWalker(chunkEl, NodeFilter.SHOW_TEXT);
  let textNode: Text | null;

  while ((textNode = walker.nextNode() as Text | null)) {
    const content = textNode.textContent ?? "";
    const idx = content.indexOf(searchSnippet);
    if (idx < 0) continue;

    try {
      const range = document.createRange();
      range.setStart(textNode, idx);
      range.setEnd(textNode, Math.min(idx + anchorText.length, content.length));

      const markEl = document.createElement("mark");
      markEl.className = "mark-text-highlight";
      range.surroundContents(markEl);

      const cleanup = () => {
        if (!markEl.isConnected) return;
        const parent = markEl.parentNode;
        if (!parent) return;
        while (markEl.firstChild) parent.insertBefore(markEl.firstChild, markEl);
        parent.removeChild(markEl);
        if ("normalize" in parent) (parent as Element).normalize();
      };

      const scrollIntoView = (container: HTMLElement | null) => {
        if (!container) {
          markEl.scrollIntoView({ behavior: "smooth", block: "center" });
          return;
        }
        const rect = markEl.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        const scrollTarget =
          container.scrollTop + rect.top - containerRect.top - containerRect.height / 2 + rect.height / 2;
        container.scrollTo({ top: scrollTarget, behavior: "smooth" });
      };

      return { cleanup, scrollIntoView };
    } catch {
      // surroundContents failed (range spans element boundaries) — fall back to chunk scroll
      return null;
    }
  }

  return null;
}
