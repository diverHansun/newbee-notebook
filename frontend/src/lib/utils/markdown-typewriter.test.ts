import { describe, expect, it } from "vitest";

import {
  buildMarkdownVisibleMap,
  sliceMarkdownByVisibleChars,
} from "@/lib/utils/markdown-typewriter";

describe("markdown typewriter visible map", () => {
  it("counts plain text as visible text", () => {
    const markdown = "Hello world";
    const map = buildMarkdownVisibleMap(markdown);

    expect(map.totalVisibleChars).toBe(11);
    expect(sliceMarkdownByVisibleChars(markdown, 5, map)).toBe("Hello");
    expect(sliceMarkdownByVisibleChars(markdown, map.totalVisibleChars, map)).toBe(markdown);
  });

  it("skips markdown syntax symbols while preserving full markdown at completion", () => {
    const markdown = "## Title\n**Bold** text";
    const map = buildMarkdownVisibleMap(markdown);

    expect(map.totalVisibleChars).toBe("Title\nBold text".length);
    expect(sliceMarkdownByVisibleChars(markdown, 5, map)).toBe("## Title");
    expect(sliceMarkdownByVisibleChars(markdown, 10, map)).toBe("## Title\n**Bold**");
    expect(sliceMarkdownByVisibleChars(markdown, map.totalVisibleChars, map)).toBe(markdown);
  });

  it("counts link label as visible text and skips url syntax", () => {
    const markdown = "Read [**Docs**](https://example.com) now";
    const map = buildMarkdownVisibleMap(markdown);

    expect(map.totalVisibleChars).toBe("Read Docs now".length);
    expect(sliceMarkdownByVisibleChars(markdown, 9, map)).toBe(
      "Read [**Docs**](https://example.com)"
    );
    expect(sliceMarkdownByVisibleChars(markdown, map.totalVisibleChars, map)).toBe(markdown);
  });
});
