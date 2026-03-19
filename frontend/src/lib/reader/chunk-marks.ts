export type ChunkOffset = {
  content: string;
  startChar: number;
};

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
