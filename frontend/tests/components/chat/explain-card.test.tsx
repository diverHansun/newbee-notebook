import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ExplainCard } from "@/components/chat/explain-card";
import type { ExplainCardState } from "@/stores/chat-store";
import { renderWithLang } from "@/test/test-utils";

vi.mock("@/components/reader/markdown-viewer", () => ({
  MarkdownViewer: ({ content }: { content: string }) => (
    <div data-testid="markdown-viewer">{content}</div>
  ),
}));

function buildCard(overrides: Partial<ExplainCardState> = {}): ExplainCardState {
  return {
    visible: true,
    mode: "explain",
    selectedText: "Selected text",
    content: "",
    isStreaming: false,
    error: null,
    lastInteractionKey: "explain::Selected text",
    ...overrides,
  };
}

describe("ExplainCard", () => {
  it("opens the empty state from the default pill", async () => {
    renderWithLang(<ExplainCard card={null} />, { lang: "en" });

    await userEvent.click(screen.getByRole("button", { name: /explain \/ summarize/i }));

    expect(screen.getByText("Nothing yet")).toBeInTheDocument();
    expect(screen.getByText(/Select text in the document/)).toBeInTheDocument();
  });

  it("shows the loader while waiting for the first token", async () => {
    renderWithLang(<ExplainCard card={buildCard({ isStreaming: true })} />, { lang: "en" });

    expect(await screen.findByRole("status", { name: "Generating..." })).toBeInTheDocument();
    expect(screen.getByLabelText("Selected text")).toBeInTheDocument();
  });

  it("renders stream errors separately and keeps partial content readable", async () => {
    const onRetry = vi.fn();
    renderWithLang(
      <ExplainCard
        card={buildCard({
          content: "Partial answer",
          error: { code: "E_EXPLAIN", message: "Explain failed", retryable: true },
        })}
        onRetry={onRetry}
      />,
      { lang: "en" }
    );

    expect(await screen.findByRole("alert")).toHaveAttribute("data-error-code", "E_EXPLAIN");
    expect(screen.getByText("Explain failed")).toBeInTheDocument();
    expect(screen.getByTestId("markdown-viewer")).toHaveTextContent("Partial answer");

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
