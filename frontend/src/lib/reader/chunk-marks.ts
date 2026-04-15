export type ChunkOffset = {
  content: string;
  startChar: number;
};

export const MARK_ANCHOR_TEXT_MAX_LENGTH = 1000;

export function computeChunkOffsets(fullContent: string, chunks: string[]): ChunkOffset[] {
  let offset = 0;

  return chunks.map((chunk) => {
    const startChar = fullContent.indexOf(chunk, offset);
    const resolvedStartChar = startChar >= 0 ? startChar : offset;
    offset = resolvedStartChar + chunk.length;

    return {
      content: chunk,
      startChar: resolvedStartChar,
    };
  });
}

export function findChunkIndexByOffset(chunks: ChunkOffset[], charOffset: number): number {
  for (let index = 0; index < chunks.length; index += 1) {
    const current = chunks[index];
    const next = chunks[index + 1];
    const chunkEnd = next ? next.startChar : current.startChar + current.content.length;

    if (charOffset >= current.startChar && charOffset < chunkEnd) {
      return index;
    }
  }

  return Math.max(0, chunks.length - 1);
}

type ResolveMarkCharOffsetInput = {
  chunk: ChunkOffset;
  selectedText: string;
  range?: Range | null;
  chunkElement?: HTMLElement | null;
};

function collapseWhitespaceWithIndexMap(value: string): { text: string; indices: number[] } {
  const chars: string[] = [];
  const indices: number[] = [];
  let previousWasWhitespace = false;

  for (let index = 0; index < value.length; index += 1) {
    if (/\s/.test(value[index])) {
      if (!previousWasWhitespace) {
        chars.push(" ");
        indices.push(index);
      }
      previousWasWhitespace = true;
      continue;
    }

    chars.push(value[index]);
    indices.push(index);
    previousWasWhitespace = false;
  }

  return { text: chars.join(""), indices };
}

function findTextOffset(sourceText: string, selectedText: string): number | null {
  const exactOffset = sourceText.indexOf(selectedText);
  if (exactOffset >= 0) return exactOffset;

  const collapsedSource = collapseWhitespaceWithIndexMap(sourceText);
  const collapsedSelection = collapseWhitespaceWithIndexMap(selectedText);
  const collapsedOffset = collapsedSource.text.indexOf(collapsedSelection.text);
  if (collapsedOffset < 0) return null;

  return collapsedSource.indices[collapsedOffset] ?? null;
}

function findRangeStartOffset(chunkElement: HTMLElement, range: Range): number | null {
  if (!chunkElement.contains(range.startContainer)) {
    return null;
  }

  const walker = document.createTreeWalker(chunkElement, NodeFilter.SHOW_TEXT);
  let offset = 0;
  let textNode = walker.nextNode() as Text | null;

  while (textNode) {
    if (textNode === range.startContainer) {
      return offset + range.startOffset;
    }
    offset += textNode.textContent?.length ?? 0;
    textNode = walker.nextNode() as Text | null;
  }

  return null;
}

export function resolveMarkCharOffset({
  chunk,
  selectedText,
  range,
  chunkElement,
}: ResolveMarkCharOffsetInput): number | null {
  const normalizedSelectedText = selectedText.trim();
  if (!normalizedSelectedText) return null;

  if (chunkElement && range) {
    const domOffset = findRangeStartOffset(chunkElement, range);
    if (domOffset != null) {
      return chunk.startChar + domOffset;
    }
  }

  const sourceOffset = findTextOffset(chunk.content, normalizedSelectedText);
  if (sourceOffset != null) {
    return chunk.startChar + sourceOffset;
  }

  if (chunkElement?.textContent) {
    const renderedOffset = findTextOffset(chunkElement.textContent, normalizedSelectedText);
    if (renderedOffset != null) {
      return chunk.startChar + renderedOffset;
    }
  }

  return null;
}
