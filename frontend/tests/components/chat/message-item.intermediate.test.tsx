import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MessageItem } from "@/components/chat/message-item";
import { renderWithLang } from "@/test/test-utils";
import { type ChatMessage } from "@/stores/chat-store";

vi.mock("@/components/reader/markdown-viewer", () => ({
  MarkdownViewer: ({ content }: { content: string }) => <div data-testid="markdown-viewer">{content}</div>,
}));

describe("MessageItem intermediate assistant layout", () => {
  it("renders assistant intermediate text with tool steps and no avatar labels", () => {
    const message: ChatMessage = {
      id: "assistant-1",
      role: "assistant",
      mode: "agent",
      content: "",
      intermediateContent: "Let me check first.",
      intermediateGeneration: 1,
      thinkingStage: "retrieving",
      status: "streaming",
      createdAt: "2026-04-07T00:00:00.000Z",
      toolSteps: [
        {
          id: "call-1",
          toolName: "knowledge_base",
          status: "running",
        },
      ],
    };

    const { container } = renderWithLang(
      <MessageItem message={message} onOpenDocument={() => {}} />,
      { lang: "en" }
    );

    expect(screen.getByTestId("assistant-lane")).toBeInTheDocument();
    expect(screen.getByTestId("assistant-intermediate-current")).toHaveTextContent("Let me check first.");
    expect(container.querySelector(".tool-steps-indicator")).not.toBeNull();
    expect(screen.queryByText(/^AI$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^U$/)).not.toBeInTheDocument();
  });

  it("renders exiting intermediate text above the final assistant body", () => {
    const message: ChatMessage = {
      id: "assistant-2",
      role: "assistant",
      mode: "agent",
      content: "Here is the final answer.",
      exitingIntermediateContent: "Let me check first.",
      status: "streaming",
      createdAt: "2026-04-07T00:00:01.000Z",
    };

    renderWithLang(<MessageItem message={message} onOpenDocument={() => {}} />, { lang: "en" });

    expect(screen.getByTestId("assistant-intermediate-exiting")).toHaveTextContent("Let me check first.");
    expect(screen.getByTestId("assistant-message-body")).toHaveTextContent("Here is the final answer.");
    expect(screen.getByTestId("markdown-viewer")).toHaveTextContent("Here is the final answer.");
  });
});
