import { describe, expect, it } from "vitest";

import {
  MARK_ANCHOR_TEXT_MAX_LENGTH,
  computeChunkOffsets,
  findChunkIndexByOffset,
  resolveMarkCharOffset,
} from "@/lib/reader/chunk-marks";

describe("chunk-marks", () => {
  it("uses a 1000 character bookmark anchor limit", () => {
    expect(MARK_ANCHOR_TEXT_MAX_LENGTH).toBe(1000);
  });

  it("computes stable chunk offsets from the original markdown", () => {
    const content = "Alpha\n\nBeta\n\nGamma";
    const chunks = ["Alpha\n\n", "Beta\n\n", "Gamma"];

    expect(computeChunkOffsets(content, chunks)).toEqual([
      { content: "Alpha\n\n", startChar: 0 },
      { content: "Beta\n\n", startChar: 7 },
      { content: "Gamma", startChar: 13 },
    ]);
  });

  it("finds the chunk index for a mark offset", () => {
    const chunks = [
      { content: "Alpha\n\n", startChar: 0 },
      { content: "Beta\n\n", startChar: 7 },
      { content: "Gamma", startChar: 13 },
    ];

    expect(findChunkIndexByOffset(chunks, 0)).toBe(0);
    expect(findChunkIndexByOffset(chunks, 8)).toBe(1);
    expect(findChunkIndexByOffset(chunks, 17)).toBe(2);
  });

  it("returns null when selected text cannot be located in the chunk", () => {
    const offset = resolveMarkCharOffset({
      chunk: { content: "Alpha beta", startChar: 20 },
      selectedText: "Gamma",
    });

    expect(offset).toBeNull();
  });

  it("resolves offsets when rendered selection collapses markdown whitespace", () => {
    const offset = resolveMarkCharOffset({
      chunk: { content: "Alpha\n\nBeta", startChar: 20 },
      selectedText: "Alpha Beta",
    });

    expect(offset).toBe(20);
  });
});
