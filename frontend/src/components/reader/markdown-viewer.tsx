"use client";

import { RefObject, useEffect, useMemo, useRef, useState } from "react";

import { renderMarkdownToHtml } from "@/components/reader/markdown-pipeline";

const LARGE_DOC_THRESHOLD_CHARS = 120_000;
const TARGET_CHUNK_CHARS = 24_000;
const CHUNK_LOAD_STEP = 1;

type MarkdownViewerProps = {
  content: string;
  documentId?: string;
  className?: string;
  containerRef?: RefObject<HTMLDivElement | null>;
};

function splitMarkdownIntoChunks(content: string): string[] {
  if (!content) return [""];
  if (content.length <= LARGE_DOC_THRESHOLD_CHARS) {
    return [content];
  }

  const lines = content.split(/\r?\n/);
  const chunks: string[] = [];
  let current: string[] = [];
  let currentSize = 0;

  const flush = () => {
    if (!current.length) return;
    chunks.push(current.join("\n"));
    current = [];
    currentSize = 0;
  };

  for (const line of lines) {
    const size = line.length + 1;
    const boundary = /^#{1,6}\s/.test(line) || line.trim() === "";
    if (currentSize >= TARGET_CHUNK_CHARS && boundary) {
      flush();
    }
    current.push(line);
    currentSize += size;

    // Avoid an oversized chunk when no heading/blank-line boundary appears for a long time.
    if (currentSize >= TARGET_CHUNK_CHARS * 1.6) {
      flush();
    }
  }
  flush();

  return chunks.length ? chunks : [content];
}

function getInitialVisibleChunkCount(totalChunks: number): number {
  if (totalChunks <= 1) return 1;
  if (totalChunks <= 3) return 2;
  return 3;
}

export function MarkdownViewer({ content, documentId, className, containerRef }: MarkdownViewerProps) {
  const fallbackRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const htmlCacheRef = useRef<Map<number, string>>(new Map());
  const ref = containerRef || fallbackRef;
  const chunks = useMemo(() => splitMarkdownIntoChunks(content), [content]);
  const [visibleChunkCount, setVisibleChunkCount] = useState(() =>
    getInitialVisibleChunkCount(chunks.length)
  );

  useEffect(() => {
    htmlCacheRef.current.clear();
    setVisibleChunkCount(getInitialVisibleChunkCount(chunks.length));
  }, [chunks.length, content, documentId]);

  const hasMoreChunks = visibleChunkCount < chunks.length;

  useEffect(() => {
    if (!hasMoreChunks) return;
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        setVisibleChunkCount((prev) => Math.min(prev + CHUNK_LOAD_STEP, chunks.length));
      },
      { root: null, rootMargin: "600px 0px" }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [chunks.length, hasMoreChunks]);

  const htmlChunks = useMemo(() => {
    const output: string[] = [];
    const cache = htmlCacheRef.current;

    for (let idx = 0; idx < visibleChunkCount; idx += 1) {
      const chunk = chunks[idx] || "";
      let html = cache.get(idx);
      if (!html) {
        html = renderMarkdownToHtml(chunk, { documentId });
        cache.set(idx, html);
      }
      output.push(html);
    }
    return output;
  }, [chunks, documentId, visibleChunkCount]);

  return (
    <div ref={ref} className={`markdown-content ${className || ""}`}>
      {htmlChunks.map((html, idx) => (
        <section key={idx} className="markdown-chunk" dangerouslySetInnerHTML={{ __html: html }} />
      ))}
      {hasMoreChunks ? (
        <div ref={sentinelRef} className="markdown-load-more">
          正在加载更多内容...
        </div>
      ) : null}
    </div>
  );
}
