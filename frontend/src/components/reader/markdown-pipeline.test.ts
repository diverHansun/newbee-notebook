import { beforeEach, describe, expect, it } from "vitest";

import { renderMarkdownToHtml } from "@/components/reader/markdown-pipeline";
import {
  _resetInlineChartRegistryForTests,
  getInlineChartPayload,
} from "@/lib/diagram/inline-chart-registry";

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

describe("renderMarkdownToHtml inline echarts handling", () => {
  beforeEach(() => {
    _resetInlineChartRegistryForTests();
  });

  it("replaces ```echarts fenced blocks with placeholder div when enableInlineCharts=true", () => {
    const md = "intro\n\n```echarts\n{\"series\":[{\"type\":\"bar\",\"data\":[1,2,3]}]}\n```\n\nouter";
    const html = renderMarkdownToHtml(md, { enableInlineCharts: true });

    expect(html).toContain("data-chart-placeholder");
    expect(html).toContain('data-chart-type="echarts"');
    const idMatch = html.match(/data-payload-id="([^"]+)"/);
    expect(idMatch).not.toBeNull();
    const payloadId = idMatch![1];

    expect(getInlineChartPayload(payloadId)).toContain('"type":"bar"');
    expect(html).not.toContain("language-echarts");
  });

  it("leaves ```echarts blocks as code fences when enableInlineCharts is unset", () => {
    const md = "```echarts\n{\"series\":[{\"type\":\"line\"}]}\n```";
    const html = renderMarkdownToHtml(md, {});

    expect(html).not.toContain("data-chart-placeholder");
    expect(html).toContain("language-echarts");
  });

  it("does not touch ```mermaid fences even when enableInlineCharts=true", () => {
    const md = "```mermaid\nflowchart TD\nA --> B\n```";
    const html = renderMarkdownToHtml(md, { enableInlineCharts: true });

    expect(html).not.toContain("data-chart-placeholder");
    expect(html).toContain("language-mermaid");
  });

  it("handles multiple echarts blocks with distinct payload ids", () => {
    const md = "```echarts\n{\"series\":[{\"type\":\"bar\"}]}\n```\n\n```echarts\n{\"series\":[{\"type\":\"pie\"}]}\n```";
    const html = renderMarkdownToHtml(md, { enableInlineCharts: true });

    const matches = Array.from(html.matchAll(/data-payload-id="([^"]+)"/g));
    expect(matches).toHaveLength(2);
    expect(matches[0][1]).not.toBe(matches[1][1]);
    expect(getInlineChartPayload(matches[0][1])).toContain('"type":"bar"');
    expect(getInlineChartPayload(matches[1][1])).toContain('"type":"pie"');
  });
});
