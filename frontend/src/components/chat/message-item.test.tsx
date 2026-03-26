import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MessageItem } from "@/components/chat/message-item";
import type { ChatMessage } from "@/stores/chat-store";
import { renderWithLang } from "@/test/test-utils";

vi.mock("@/components/reader/markdown-viewer", () => ({
  MarkdownViewer: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock("@/components/chat/sources-card", () => ({
  DocumentReferencesCard: () => null,
}));

const assistantMessage: ChatMessage = {
  id: "assistant-1",
  role: "assistant",
  mode: "agent",
  content: "Working on it.",
  status: "streaming",
  createdAt: "2026-03-19T00:00:00.000Z",
  pendingConfirmation: {
    requestId: "req-1",
    toolName: "update_note",
    actionType: "update",
    targetType: "note",
    argsSummary: {
      note_id: "note-1",
    },
    description: "Update note metadata.",
    status: "pending",
    expiresAt: Date.parse("2026-03-19T00:03:00.000Z"),
  },
};

describe("MessageItem", () => {
  it("renders inline confirmation actions for assistant messages", async () => {
    const user = userEvent.setup();
    const onResolveConfirmation = vi.fn();

    renderWithLang(
      <MessageItem
        message={assistantMessage}
        onOpenDocument={() => {}}
        onResolveConfirmation={onResolveConfirmation}
      />
    );

    expect(screen.getByText("Working on it.")).toBeInTheDocument();
    expect(screen.getByText("Update note")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Confirm" }));
    await user.click(screen.getByRole("button", { name: "Reject" }));

    expect(onResolveConfirmation).toHaveBeenNthCalledWith(1, "req-1", true);
    expect(onResolveConfirmation).toHaveBeenNthCalledWith(2, "req-1", false);
  });
});
