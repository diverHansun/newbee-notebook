import { describe, expect, it } from "vitest";

import { renderMarkdownToHtml } from "@/components/reader/markdown-pipeline";

describe("renderMarkdownToHtml", () => {
  it("normalizes standalone textcircled math markers before KaTeX rendering", () => {
    const html = renderMarkdownToHtml("$\\textcircled{1}$ 荣…Ⅱ. $\\textcircled{2}$ 李…");

    expect(html).toContain("①");
    expect(html).toContain("②");
    expect(html).not.toContain("\\textcircled");
    expect(html).not.toContain('class="katex"');
  });

  it("preserves real math while normalizing textcircled markers", () => {
    const html = renderMarkdownToHtml("公式 $a+b$ 与标记 $\\textcircled{1}$");

    expect(html).toContain('class="katex"');
    expect(html).toContain("①");
    expect(html).not.toContain("\\textcircled");
  });

  it("keeps inline code examples unchanged when they contain textcircled", () => {
    const html = renderMarkdownToHtml("示例：`\\\\textcircled{1}`");

    expect(html).toContain("\\textcircled{1}");
    expect(html).not.toContain("①");
  });

  it("keeps fenced code blocks unchanged when they contain textcircled", () => {
    const html = renderMarkdownToHtml("```tex\n\\\\textcircled{2}\n```");

    expect(html).toContain("\\textcircled{2}");
    expect(html).not.toContain("②");
  });
});
