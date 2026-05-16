"use client";

import { memo, RefObject, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { InlineChartCard } from "@/components/chat/inline-chart-card";
import { renderMarkdownToHtml } from "@/components/reader/markdown-pipeline";
import {
  disposeInlineChartPayload,
  getInlineChartPayload,
} from "@/lib/diagram/inline-chart-registry";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import {
  getInitialVisibleChunkCount,
  LARGE_DOC_THRESHOLD_CHARS,
  splitMarkdownIntoChunks,
} from "@/lib/reader/markdown-chunking";

const CHUNK_LOAD_STEP = 1;
const MIN_ROOT_MARGIN_PX = 640;
const MAX_ROOT_MARGIN_PX = 1400;
const PREFETCH_AHEAD_CHUNKS = 2;
const IDLE_TASK_TIMEOUT_MS = 180;

type IdleDeadlineLike = {
  didTimeout: boolean;
  timeRemaining: () => number;
};

type IdleRequestWindow = Window &
  typeof globalThis & {
    requestIdleCallback?: (
      callback: (deadline: IdleDeadlineLike) => void,
      options?: { timeout?: number }
    ) => number;
    cancelIdleCallback?: (handle: number) => void;
  };

type ScheduledTask = {
  kind: "idle" | "timeout";
  id: number;
};

function scheduleDeferredTask(fn: () => void, timeout = IDLE_TASK_TIMEOUT_MS): ScheduledTask | null {
  if (typeof window === "undefined") return null;
  const idleWindow = window as IdleRequestWindow;
  if (typeof idleWindow.requestIdleCallback === "function") {
    return {
      kind: "idle",
      id: idleWindow.requestIdleCallback(() => fn(), { timeout }),
    };
  }

  return {
    kind: "timeout",
    id: window.setTimeout(fn, 24),
  };
}

function cancelDeferredTask(task: ScheduledTask | null): void {
  if (!task || typeof window === "undefined") return;
  if (task.kind === "timeout") {
    window.clearTimeout(task.id);
    return;
  }
  const idleWindow = window as IdleRequestWindow;
  if (typeof idleWindow.cancelIdleCallback === "function") {
    idleWindow.cancelIdleCallback(task.id);
  }
}

type MarkdownViewerProps = {
  content: string;
  documentId?: string;
  className?: string;
  containerRef?: RefObject<HTMLDivElement | null>;
  scrollRootRef?: RefObject<HTMLElement | null>;
  freezeLazyLoad?: boolean;
  visibleChunkCount?: number;
  onVisibleChunkCountChange?: (count: number) => void;
  /**
   * Opt-in flag enabled only for the assistant reply to a `/diagram` user
   * message. When true, ```echarts``` fences are rendered as interactive
   * `InlineChartCard` components instead of plain code blocks.
   */
  enableInlineCharts?: boolean;
  /** Required when `enableInlineCharts` is true so cards can save to Studio. */
  inlineChartsNotebookId?: string;
};

type InlineChartHtmlPart =
  | { kind: "html"; html: string }
  | { kind: "chart"; payloadId: string; rawContent: string };

type RenderedChunk = {
  html: string;
  parts: InlineChartHtmlPart[] | null;
};

type InlineChartMatch = {
  payloadId: string;
  index: number;
  length: number;
};

const INLINE_ECHARTS_PLACEHOLDER_HTML_PATTERN =
  /<div(?=[^>]*\bdata-chart-placeholder(?:=(?:""|''))?)(?=[^>]*\bdata-chart-type="echarts")(?=[^>]*\bdata-payload-id="([^"]+)")[^>]*><\/div>/g;

function splitInlineChartHtml(html: string): InlineChartHtmlPart[] | null {
  const matches: InlineChartMatch[] = [];
  for (const match of html.matchAll(INLINE_ECHARTS_PLACEHOLDER_HTML_PATTERN)) {
    const payloadId = match[1];
    if (!payloadId || match.index === undefined) continue;
    matches.push({ payloadId, index: match.index, length: match[0].length });
  }

  if (matches.length === 0) return null;

  const parts: InlineChartHtmlPart[] = [];
  let cursor = 0;
  for (const match of matches) {
    if (match.index > cursor) {
      parts.push({ kind: "html", html: html.slice(cursor, match.index) });
    }
    const rawContent = getInlineChartPayload(match.payloadId);
    if (rawContent == null) {
      parts.push({ kind: "html", html: html.slice(match.index, match.index + match.length) });
    } else {
      parts.push({ kind: "chart", payloadId: match.payloadId, rawContent });
    }
    cursor = match.index + match.length;
  }
  if (cursor < html.length) {
    parts.push({ kind: "html", html: html.slice(cursor) });
  }
  return parts;
}

function getDynamicRootMargin(contentChars: number, totalChunks: number): string {
  if (contentChars <= LARGE_DOC_THRESHOLD_CHARS || totalChunks <= 1) {
    return `${MIN_ROOT_MARGIN_PX}px 0px`;
  }

  const chunkAvgChars = contentChars / Math.max(totalChunks, 1);
  const chunkComplexity = Math.max(1, Math.floor(chunkAvgChars / 80));
  const contentFactor = Math.floor(
    Math.log2(Math.max(1, contentChars / LARGE_DOC_THRESHOLD_CHARS) + 1) * 320
  );

  const marginPx = Math.max(
    MIN_ROOT_MARGIN_PX,
    Math.min(MAX_ROOT_MARGIN_PX, MIN_ROOT_MARGIN_PX + chunkComplexity * 8 + contentFactor)
  );

  return `${marginPx}px 0px`;
}

export const MarkdownViewer = memo(function MarkdownViewer({
  content,
  documentId,
  className,
  containerRef,
  scrollRootRef,
  freezeLazyLoad = false,
  visibleChunkCount,
  onVisibleChunkCountChange,
  enableInlineCharts = false,
  inlineChartsNotebookId,
}: MarkdownViewerProps) {
  const { t } = useLang();
  const fallbackRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const htmlCacheRef = useRef<Map<number, string>>(new Map());
  const visibleChunkCountRef = useRef(1);
  const expandTaskRef = useRef<ScheduledTask | null>(null);
  const prefetchTaskRef = useRef<ScheduledTask | null>(null);
  const ref = containerRef || fallbackRef;
  const chunks = useMemo(() => splitMarkdownIntoChunks(content), [content]);
  const rootMargin = useMemo(
    () => getDynamicRootMargin(content.length, chunks.length),
    [chunks.length, content.length]
  );
  const [internalVisibleChunkCount, setInternalVisibleChunkCount] = useState(() =>
    getInitialVisibleChunkCount(chunks.length)
  );
  const isControlledVisibleChunkCount = typeof visibleChunkCount === "number";
  const resolvedVisibleChunkCount = isControlledVisibleChunkCount
    ? Math.max(1, Math.min(chunks.length, visibleChunkCount || 1))
    : internalVisibleChunkCount;

  const setVisibleChunkCount = useCallback(
    (next: number) => {
      const normalized = Math.max(1, Math.min(chunks.length, next));
      if (!isControlledVisibleChunkCount) {
        setInternalVisibleChunkCount(normalized);
      }
      onVisibleChunkCountChange?.(normalized);
    },
    [chunks.length, isControlledVisibleChunkCount, onVisibleChunkCountChange]
  );

  useEffect(() => {
    visibleChunkCountRef.current = resolvedVisibleChunkCount;
  }, [resolvedVisibleChunkCount]);

  useEffect(() => {
    cancelDeferredTask(expandTaskRef.current);
    expandTaskRef.current = null;
    cancelDeferredTask(prefetchTaskRef.current);
    prefetchTaskRef.current = null;
    htmlCacheRef.current.clear();
    const initialVisibleChunkCount = getInitialVisibleChunkCount(chunks.length);
    if (isControlledVisibleChunkCount) {
      onVisibleChunkCountChange?.(initialVisibleChunkCount);
    } else {
      setInternalVisibleChunkCount(initialVisibleChunkCount);
    }
  }, [chunks.length, content, documentId, enableInlineCharts, isControlledVisibleChunkCount, onVisibleChunkCountChange]);

  const hasMoreChunks = resolvedVisibleChunkCount < chunks.length;

  const scheduleChunkExpand = useCallback(() => {
    if (expandTaskRef.current) return;
    expandTaskRef.current = scheduleDeferredTask(() => {
      expandTaskRef.current = null;
      if (freezeLazyLoad) return;
      setVisibleChunkCount(visibleChunkCountRef.current + CHUNK_LOAD_STEP);
    });
  }, [freezeLazyLoad, setVisibleChunkCount]);

  useEffect(() => {
    if (!hasMoreChunks) return;
    const cache = htmlCacheRef.current;
    const start = resolvedVisibleChunkCount;
    const end = Math.min(chunks.length, resolvedVisibleChunkCount + PREFETCH_AHEAD_CHUNKS);

    cancelDeferredTask(prefetchTaskRef.current);
    prefetchTaskRef.current = scheduleDeferredTask(() => {
      prefetchTaskRef.current = null;
      for (let idx = start; idx < end; idx += 1) {
        if (cache.has(idx)) continue;
        cache.set(idx, renderMarkdownToHtml(chunks[idx] || "", { documentId, enableInlineCharts }));
      }
    });

    return () => {
      cancelDeferredTask(prefetchTaskRef.current);
      prefetchTaskRef.current = null;
    };
  }, [chunks, documentId, enableInlineCharts, hasMoreChunks, resolvedVisibleChunkCount]);

  useEffect(() => {
    if (!hasMoreChunks) return;
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        scheduleChunkExpand();
      },
      { root: scrollRootRef?.current ?? null, rootMargin }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [
    hasMoreChunks,
    rootMargin,
    scheduleChunkExpand,
    scrollRootRef,
  ]);

  useEffect(() => {
    return () => {
      cancelDeferredTask(expandTaskRef.current);
      expandTaskRef.current = null;
      cancelDeferredTask(prefetchTaskRef.current);
      prefetchTaskRef.current = null;
    };
  }, []);

  const htmlChunks = useMemo(() => {
    const output: string[] = [];
    const cache = htmlCacheRef.current;

    for (let idx = 0; idx < resolvedVisibleChunkCount; idx += 1) {
      const chunk = chunks[idx] || "";
      let html = cache.get(idx);
      if (!html) {
        html = renderMarkdownToHtml(chunk, { documentId, enableInlineCharts });
        cache.set(idx, html);
      }
      output.push(html);
    }
    return output;
  }, [chunks, documentId, enableInlineCharts, resolvedVisibleChunkCount]);

  const renderedChunks = useMemo<RenderedChunk[]>(() => {
    if (!enableInlineCharts || !inlineChartsNotebookId) {
      return htmlChunks.map((html) => ({ html, parts: null }));
    }
    return htmlChunks.map((html) => ({
      html,
      parts: splitInlineChartHtml(html),
    }));
  }, [enableInlineCharts, htmlChunks, inlineChartsNotebookId]);

  const inlinePayloadIds = useMemo(
    () =>
      renderedChunks.flatMap((chunk) =>
        (chunk.parts || [])
          .filter((part): part is Extract<InlineChartHtmlPart, { kind: "chart" }> => part.kind === "chart")
          .map((part) => part.payloadId)
      ),
    [renderedChunks]
  );

  useEffect(() => {
    return () => {
      inlinePayloadIds.forEach((payloadId) => disposeInlineChartPayload(payloadId));
    };
  }, [inlinePayloadIds]);

  return (
    <div ref={ref} className={`markdown-content ${className || ""}`}>
      {renderedChunks.map((chunk, idx) => (
        <section
          key={`chunk-${documentId ?? "doc"}-${idx}`}
          className="markdown-chunk"
          data-chunk-index={idx}
          {...(chunk.parts == null ? { dangerouslySetInnerHTML: { __html: chunk.html } } : {})}
        >
          {chunk.parts?.map((part, partIndex) => {
            if (part.kind === "html") {
              return (
                <div
                  key={`html-${partIndex}`}
                  style={{ display: "contents" }}
                  dangerouslySetInnerHTML={{ __html: part.html }}
                />
              );
            }
            return (
              <InlineChartCard
                key={part.payloadId}
                rawContent={part.rawContent}
                notebookId={inlineChartsNotebookId!}
              />
            );
          })}
        </section>
      ))}
      {hasMoreChunks ? (
        <div ref={sentinelRef} className="markdown-load-more">
          {t(uiStrings.reader.moreContentLoading)}
        </div>
      ) : null}
    </div>
  );
});
