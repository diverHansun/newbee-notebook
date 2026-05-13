import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/chat/inline-chart-card", () => ({
  InlineChartCard: ({
    rawContent,
    notebookId,
  }: {
    rawContent: string;
    notebookId: string;
  }) => (
    <div data-testid="inline-chart-card" data-notebook-id={notebookId}>
      {rawContent}
    </div>
  ),
}));

import { MarkdownViewer } from "@/components/reader/markdown-viewer";

const ECHARTS_FENCE =
  '```echarts\n{"series":[{"type":"bar","data":[1,2,3]}]}\n```';

describe("MarkdownViewer inline ECharts", () => {
  it("mounts an InlineChartCard into echarts placeholders when enabled", async () => {
    render(
      <MarkdownViewer
        content={ECHARTS_FENCE}
        enableInlineCharts={true}
        inlineChartsNotebookId="nb-1"
      />
    );

    const card = await screen.findByTestId("inline-chart-card");
    expect(card).toHaveAttribute("data-notebook-id", "nb-1");
    expect(card).toHaveTextContent('"type":"bar"');
  });

  it("keeps echarts fences as plain code when inline charts are disabled", () => {
    render(<MarkdownViewer content={ECHARTS_FENCE} />);

    expect(screen.queryByTestId("inline-chart-card")).toBeNull();
    expect(screen.getByText(/"type":"bar"/)).toBeInTheDocument();
  });
});
