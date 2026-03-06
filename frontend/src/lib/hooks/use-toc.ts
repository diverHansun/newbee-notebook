"use client";

import { RefObject, useEffect, useState } from "react";
import { unified } from "unified";
import remarkParse from "remark-parse";
import { visit } from "unist-util-visit";

import { splitMarkdownIntoChunks } from "@/lib/reader/markdown-chunking";

const HEADING_SELECTOR = "h1[id], h2[id], h3[id], h4[id], h5[id], h6[id]";
const COMPACT_READER_WIDTH = 420;
const ACTIVE_HEADING_ANCHOR_PX = 32;
const ACTIVE_SYNC_INTERVAL_MS = 48;

export type TocItem = {
  id: string;
  text: string;
  level: number;
  chunkIndex: number;
  order: number;
};

function normalizeMarkdown(markdown: string): string {
  return markdown.replace(/\r\n?/g, "\n");
}

function normalizeHeadingText(raw: string): string {
  return raw
    .replace(/\s+#+\s*$/, "")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1")
    .trim();
}

function extractTextFromMdastNode(node: any): string {
  if (!node) return "";
  if (typeof node.value === "string") return node.value;
  if (!Array.isArray(node.children)) return "";
  return node.children.map((child: any) => extractTextFromMdastNode(child)).join("");
}

export function getCompactReaderWidthThreshold(): number {
  return COMPACT_READER_WIDTH;
}

export function extractTocItems(markdown: string): TocItem[] {
  const normalized = normalizeMarkdown(markdown || "");
  if (!normalized.trim()) return [];

  const chunks = splitMarkdownIntoChunks(normalized);
  const chunkLineEnds: number[] = [];
  let lineCursor = 0;
  for (const chunk of chunks) {
    const linesInChunk = chunk.split("\n").length;
    lineCursor += linesInChunk;
    chunkLineEnds.push(Math.max(0, lineCursor - 1));
  }

  const items: TocItem[] = [];
  const tree = unified().use(remarkParse).parse(normalized);

  visit(tree, "heading", (node: any) => {
    const lineIndex = Math.max(0, (node.position?.start?.line || 1) - 1);
    let chunkIndex = 0;
    while (chunkIndex < chunkLineEnds.length - 1 && lineIndex > chunkLineEnds[chunkIndex]) {
      chunkIndex += 1;
    }

    const level = Number(node.depth || 1);
    const text = normalizeHeadingText(extractTextFromMdastNode(node));
    if (!text) return;

    items.push({
      id: `toc-item-${items.length}`,
      text,
      level,
      chunkIndex,
      order: items.length,
    });
  });

  return items;
}

export function useActiveHeading(
  scrollContainerRef: RefObject<HTMLElement | null>,
  tocItems: TocItem[],
  enabled = true,
  refreshKey = 0
): string | null {
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !tocItems.length) {
      setActiveId(null);
      return;
    }
    setActiveId((prev) => prev || tocItems[0]?.id || null);
  }, [enabled, tocItems]);

  useEffect(() => {
    if (!enabled || !tocItems.length) return;
    const root = scrollContainerRef.current;
    if (!root) return;

    let headingOffsets: number[] = [];
    let rafId: number | null = null;
    let trailingTimerId: number | null = null;
    let lastSyncTime = 0;
    let needRebuild = false;

    const findActiveHeadingIndex = (offsets: number[], anchor: number): number => {
      let left = 0;
      let right = offsets.length - 1;
      let matched = 0;

      while (left <= right) {
        const middle = (left + right) >> 1;
        if ((offsets[middle] ?? 0) <= anchor) {
          matched = middle;
          left = middle + 1;
        } else {
          right = middle - 1;
        }
      }

      return matched;
    };

    const rebuildHeadingOffsets = () => {
      const headings = Array.from(root.querySelectorAll<HTMLElement>(HEADING_SELECTOR));
      if (!headings.length) {
        headingOffsets = [];
        return;
      }

      const rootRect = root.getBoundingClientRect();
      headingOffsets = headings.map(
        (heading) => heading.getBoundingClientRect().top - rootRect.top + root.scrollTop
      );
    };

    const updateActiveHeading = () => {
      if (!headingOffsets.length) {
        setActiveId((prev) => prev ?? tocItems[0]?.id ?? null);
        return;
      }

      const anchor = root.scrollTop + ACTIVE_HEADING_ANCHOR_PX;
      const headingIndex = findActiveHeadingIndex(headingOffsets, anchor);
      const activeItem = tocItems[Math.min(headingIndex, tocItems.length - 1)];
      const nextId = activeItem?.id || null;
      setActiveId((prev) => (prev === nextId ? prev : nextId));
    };

    const scheduleUpdate = (withRebuild = false) => {
      if (withRebuild) {
        needRebuild = true;
      }
      if (rafId !== null) return;
      rafId = window.requestAnimationFrame(() => {
        rafId = null;
        if (needRebuild) {
          rebuildHeadingOffsets();
          needRebuild = false;
        }
        updateActiveHeading();
      });
    };

    rebuildHeadingOffsets();
    updateActiveHeading();
    const onScroll = () => {
      const now = performance.now();
      if (now - lastSyncTime >= ACTIVE_SYNC_INTERVAL_MS) {
        lastSyncTime = now;
        scheduleUpdate(false);
        return;
      }
      if (trailingTimerId !== null) return;
      trailingTimerId = window.setTimeout(() => {
        trailingTimerId = null;
        lastSyncTime = performance.now();
        scheduleUpdate(false);
      }, ACTIVE_SYNC_INTERVAL_MS);
    };
    const onResize = () => scheduleUpdate(true);
    root.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);

    return () => {
      if (rafId !== null) {
        window.cancelAnimationFrame(rafId);
      }
      if (trailingTimerId !== null) {
        window.clearTimeout(trailingTimerId);
      }
      root.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
    };
  }, [enabled, refreshKey, scrollContainerRef, tocItems]);

  return activeId;
}
