"use client";

export const LARGE_DOC_THRESHOLD_CHARS = 80_000;
export const TARGET_CHUNK_CHARS = 18_000;

export function splitMarkdownIntoChunks(content: string): string[] {
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

    // Keep chunk upper-bound controlled when long uninterrupted blocks appear.
    if (currentSize >= TARGET_CHUNK_CHARS * 1.6) {
      flush();
    }
  }

  flush();
  return chunks.length ? chunks : [content];
}

export function getInitialVisibleChunkCount(totalChunks: number): number {
  if (totalChunks <= 1) return 1;
  if (totalChunks <= 3) return 2;
  return 3;
}
