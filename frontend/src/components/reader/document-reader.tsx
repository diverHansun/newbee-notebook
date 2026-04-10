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
import {
  MARK_ANCHOR_TEXT_MAX_LENGTH,
  computeChunkOffsets,
  findChunkIndexByOffset,
  resolveMarkCharOffset,
} from "@/lib/reader/chunk-marks";
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

type MarkFeedback = {
  kind: "success" | "warning" | "error";
  message: string;
};

export function DocumentReader({
  documentId,
  onBack,
  onExplain,
  onConclude,
}: DocumentReaderProps) {
  const { t, ti, lang } = useLang();
  const queryClient = useQueryClient();
  const viewerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const readerBodyRef = useRef<HTMLDivElement>(null);
  const isSelecting = useReaderStore((state) => state.isSelecting);
  const activeMarkId = useReaderStore((state) => state.activeMarkId);
  const markScrollTrigger = useReaderStore((state) => state.markScrollTrigger);
  const setReaderActiveMarkId = useReaderStore((state) => state.setActiveMarkId);
  const isTocOpen = useReaderStore((state) => state.isTocOpen);
  const setTocOpen = useReaderStore((state) => state.setTocOpen);
  const toggleToc = useReaderStore((state) => state.toggleToc);
  const setStudioActiveMarkId = useStudioStore((state) => state.setActiveMarkId);
  const [isCompactReader, setIsCompactReader] = useState(false);
  const [visibleChunkCount, setVisibleChunkCount] = useState(1);
  const [markFeedback, setMarkFeedback] = useState<MarkFeedback | null>(null);
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
  const markAnchorTextMaxLengthLabel = useMemo(
    () =>
      new Intl.NumberFormat(lang === "en" ? "en-US" : "zh-CN").format(
        MARK_ANCHOR_TEXT_MAX_LENGTH
      ),
    [lang]
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
      const anchorText = selectedText.trim();
      if (!anchorText) return;
      if (anchorText.length > MARK_ANCHOR_TEXT_MAX_LENGTH) {
        setMarkFeedback({
          kind: "warning",
          message: ti(uiStrings.reader.bookmarkSelectionTooLong, {
            max: markAnchorTextMaxLengthLabel,
          }),
        });
        return;
      }

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

      const charOffset = resolveMarkCharOffset({
        chunk,
        selectedText: anchorText,
        range,
        chunkElement,
      });
      if (charOffset == null) {
        setMarkFeedback({
          kind: "warning",
          message: t(uiStrings.reader.bookmarkPositionUnavailable),
        });
        return;
      }

      try {
        const mark = await createMarkMutation.mutateAsync({
          anchorText,
          charOffset,
          contextText: anchorText,
        });
        // Wait for query cache to contain the new mark before activating,
        // so the scroll-to-mark effect can find it immediately.
        await queryClient.invalidateQueries({ queryKey: ["marks", "document", documentId] });
        await queryClient.invalidateQueries({ queryKey: ["marks", "notebook"] });
        setReaderActiveMarkId(mark.mark_id);
        setStudioActiveMarkId(mark.mark_id);
        setMarkFeedback({
          kind: "success",
          message: t(uiStrings.reader.bookmarkCreated),
        });
      } catch (error) {
        setMarkFeedback(
          error instanceof ApiError && error.errorCode === "E_MARK_ANCHOR_TOO_LONG"
            ? {
                kind: "warning",
                message: ti(uiStrings.reader.bookmarkSelectionTooLong, {
                  max: markAnchorTextMaxLengthLabel,
                }),
              }
            : {
                kind: "error",
                message: t(uiStrings.reader.bookmarkCreateFailed),
              }
        );
      }
    },
    [
      chunkOffsets,
      createMarkMutation,
      documentId,
      markAnchorTextMaxLengthLabel,
      queryClient,
      setReaderActiveMarkId,
      setStudioActiveMarkId,
      t,
      ti,
    ]
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
  }, [activeMarkId, markScrollTrigger, chunkOffsets, marksQuery.data?.marks, totalChunkCount, visibleChunkCount]);

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
      <div ref={readerBodyRef} className="reader-body-layout" style={{ flex: 1, position: "relative" }}>
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
        {markFeedback ? (
          <div
            role="status"
            aria-live="polite"
            className={`reader-toast reader-toast-${markFeedback.kind}`}
          >
            {markFeedback.message}
          </div>
        ) : null}
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
 * Find anchor_text in the rendered DOM of a chunk and wrap matching segments
 * in <mark> elements. Handles text that spans across multiple inline elements
 * (e.g. <strong>, <em>, <code>) by wrapping each text node segment individually.
 */
function highlightTextInChunk(
  chunkEl: HTMLElement,
  anchorText: string,
): { cleanup: () => void; scrollIntoView: (container: HTMLElement | null) => void } | null {
  if (!anchorText.trim()) return null;

  // Step 1: Collect all text nodes and build a concatenated string with offset tracking
  const textEntries: { node: Text; start: number; end: number }[] = [];
  const walker = document.createTreeWalker(chunkEl, NodeFilter.SHOW_TEXT);
  let cumOffset = 0;
  let textNode: Text | null;
  while ((textNode = walker.nextNode() as Text | null)) {
    const len = textNode.length;
    textEntries.push({ node: textNode, start: cumOffset, end: cumOffset + len });
    cumOffset += len;
  }
  if (textEntries.length === 0) return null;

  // Step 2: Search for anchorText in the concatenated text
  // Selection.toString() may differ from DOM text in two ways:
  //   a) \n / \t rendered as spaces
  //   b) paragraph boundaries produce extra spaces (e.g. "foo.  Bar" vs "foo. Bar")
  // We collapse all whitespace runs to a single space for matching, then map
  // collapsed positions back to original positions for wrapping.
  const concatenated = textEntries.map((e) => e.node.textContent ?? "").join("");

  const collapseWs = (s: string): { collapsed: string; origIndices: number[] } => {
    const chars: string[] = [];
    const indices: number[] = [];
    let prevSpace = false;
    for (let i = 0; i < s.length; i++) {
      const isSpace = /\s/.test(s[i]);
      if (isSpace) {
        if (!prevSpace) { chars.push(" "); indices.push(i); }
        prevSpace = true;
      } else {
        chars.push(s[i]); indices.push(i);
        prevSpace = false;
      }
    }
    return { collapsed: chars.join(""), origIndices: indices };
  };

  const { collapsed: collapsedConcat, origIndices } = collapseWs(concatenated);
  const { collapsed: collapsedAnchor } = collapseWs(anchorText);
  const collapsedMatchStart = collapsedConcat.indexOf(collapsedAnchor);
  if (collapsedMatchStart < 0) return null;
  const collapsedMatchEnd = collapsedMatchStart + collapsedAnchor.length;

  // Map back to original concatenated positions
  const matchStart = origIndices[collapsedMatchStart];
  const matchEnd =
    collapsedMatchEnd < origIndices.length
      ? origIndices[collapsedMatchEnd]
      : concatenated.length;

  // Step 3: Wrap each overlapping text node segment in a <mark> element
  const createdMarks: HTMLElement[] = [];
  for (const entry of textEntries) {
    if (entry.end <= matchStart || entry.start >= matchEnd) continue;

    const localStart = Math.max(matchStart, entry.start) - entry.start;
    const localEnd = Math.min(matchEnd, entry.end) - entry.start;

    let target: Text = entry.node;
    if (localStart > 0) {
      target = target.splitText(localStart);
    }
    if (localEnd - localStart < target.length) {
      target.splitText(localEnd - localStart);
    }

    const markEl = document.createElement("mark");
    markEl.className = "mark-text-highlight";
    target.parentNode!.insertBefore(markEl, target);
    markEl.appendChild(target);
    createdMarks.push(markEl);
  }

  if (createdMarks.length === 0) return null;

  const cleanup = () => {
    for (const markEl of createdMarks) {
      if (!markEl.isConnected) continue;
      const parent = markEl.parentNode;
      if (!parent) continue;
      while (markEl.firstChild) parent.insertBefore(markEl.firstChild, markEl);
      parent.removeChild(markEl);
    }
    chunkEl.normalize();
  };

  const scrollIntoView = (container: HTMLElement | null) => {
    const first = createdMarks[0];
    if (!first?.isConnected) return;
    if (!container) {
      first.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const rect = first.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const scrollTarget =
      container.scrollTop + rect.top - containerRect.top - containerRect.height / 2 + rect.height / 2;
    container.scrollTo({ top: scrollTarget, behavior: "smooth" });
  };

  return { cleanup, scrollIntoView };
}
