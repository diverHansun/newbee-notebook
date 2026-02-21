"use client";

import { RefObject, useMemo, useRef } from "react";

import { renderMarkdownToHtml } from "@/components/reader/markdown-pipeline";

type MarkdownViewerProps = {
  content: string;
  className?: string;
  containerRef?: RefObject<HTMLDivElement | null>;
};

export function MarkdownViewer({ content, className, containerRef }: MarkdownViewerProps) {
  const fallbackRef = useRef<HTMLDivElement>(null);
  const html = useMemo(() => renderMarkdownToHtml(content), [content]);
  const ref = containerRef || fallbackRef;

  return (
    <div
      ref={ref}
      className={`markdown-content ${className || ""}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
