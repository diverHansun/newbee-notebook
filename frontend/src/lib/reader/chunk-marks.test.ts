import { describe, expect, it } from "vitest";

import { computeChunkOffsets, findChunkIndexByOffset } from "@/lib/reader/chunk-marks";

describe("chunk-marks", () => {
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
});
