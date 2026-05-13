import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mutateAsyncMock } = vi.hoisted(() => ({
  mutateAsyncMock: vi.fn(),
}));

vi.mock("@/lib/hooks/use-diagrams", () => ({
  useCreateDiagram: () => ({
    mutateAsync: mutateAsyncMock,
  }),
}));

vi.mock("@/components/studio/echarts-renderer", () => ({
  EChartsRenderer: ({ content }: { content: string }) => (
    <div data-testid="echarts-renderer-stub">{content}</div>
  ),
}));

import { InlineChartCard } from "@/components/chat/inline-chart-card";

const VALID_CONTENT = '{"title":{"text":"月度销售额"},"series":[{"type":"bar","data":[1,2,3]}]}';

describe("InlineChartCard", () => {
  beforeEach(() => {
    mutateAsyncMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("derives title from option.title.text", () => {
    render(<InlineChartCard rawContent={VALID_CONTENT} notebookId="nb-1" />);

    expect(screen.getByText("月度销售额")).toBeInTheDocument();
  });

  it("falls back to localized default title with timestamp when title.text is missing", () => {
    const noTitleContent = '{"series":[{"type":"bar","data":[1]}]}';
    render(<InlineChartCard rawContent={noTitleContent} notebookId="nb-1" />);

    const titleEl = screen.getByTitle(/ECharts 图表 - \d{4}-\d{2}-\d{2}/);
    expect(titleEl).toBeInTheDocument();
  });

  it("calls createDiagram with the expected payload on save click", async () => {
    mutateAsyncMock.mockResolvedValueOnce({
      diagram_id: "d-1",
      diagram_type: "echarts",
      format: "echarts_option",
    });
    const user = userEvent.setup();

    render(<InlineChartCard rawContent={VALID_CONTENT} notebookId="nb-1" />);
    await user.click(screen.getByTestId("inline-chart-save-button"));

    await waitFor(() => {
      expect(mutateAsyncMock).toHaveBeenCalledTimes(1);
    });
    const call = mutateAsyncMock.mock.calls[0][0];
    expect(call).toMatchObject({
      title: "月度销售额",
      diagram_type: "echarts",
      content: VALID_CONTENT,
    });
    expect(call).not.toHaveProperty("format");
  });

  it("becomes permanently disabled with check icon after successful save", async () => {
    mutateAsyncMock.mockResolvedValueOnce({});
    const user = userEvent.setup();

    render(<InlineChartCard rawContent={VALID_CONTENT} notebookId="nb-1" />);
    const button = screen.getByTestId("inline-chart-save-button");
    await user.click(button);

    await waitFor(() => {
      expect(button).toBeDisabled();
    });
    expect(button.getAttribute("aria-label")).toContain("已保存");
    expect(screen.getByTestId("inline-chart-card")).toHaveAttribute("data-save-status", "saved");
  });

  it("shows error and remains clickable when save fails", async () => {
    mutateAsyncMock.mockRejectedValueOnce(new Error("network down"));
    const user = userEvent.setup();

    render(<InlineChartCard rawContent={VALID_CONTENT} notebookId="nb-1" />);
    const button = screen.getByTestId("inline-chart-save-button");
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByTestId("inline-chart-error")).toHaveTextContent(/network down/);
    });
    expect(button).not.toBeDisabled();
  });

  it("does not call createDiagram on double-click while inflight", async () => {
    let resolveSave: (() => void) | null = null;
    mutateAsyncMock.mockImplementationOnce(
      () => new Promise<void>((resolve) => { resolveSave = () => resolve(); })
    );
    const user = userEvent.setup();

    render(<InlineChartCard rawContent={VALID_CONTENT} notebookId="nb-1" />);
    const button = screen.getByTestId("inline-chart-save-button");

    await user.click(button);
    await user.click(button); // second click while inflight

    expect(mutateAsyncMock).toHaveBeenCalledTimes(1);

    if (resolveSave) (resolveSave as () => void)();
  });

  it("renders loading state when content is not parseable JSON yet", () => {
    render(<InlineChartCard rawContent={'{"series":'} notebookId="nb-1" />);

    expect(screen.getByTestId("inline-chart-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("echarts-renderer-stub")).toBeNull();
    expect(screen.getByTestId("inline-chart-save-button")).toBeDisabled();
  });
});
