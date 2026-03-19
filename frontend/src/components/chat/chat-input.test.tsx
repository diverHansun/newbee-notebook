import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChatInput } from "@/components/chat/chat-input";
import { renderWithLang } from "@/test/test-utils";

vi.mock("@/components/chat/source-selector", () => ({
  SourceSelector: () => null,
}));

vi.mock("@/components/ui/segmented-control", () => ({
  SegmentedControl: () => null,
}));

describe("ChatInput", () => {
  it("shows slash command hint and completes the note command", async () => {
    const user = userEvent.setup();
    const onModeChange = vi.fn();

    renderWithLang(
      <ChatInput
        notebookId="nb-1"
        mode="ask"
        isStreaming={false}
        askBlocked={false}
        sourceDocIds={null}
        onSourceDocIdsChange={() => {}}
        onModeChange={onModeChange}
        onSend={() => {}}
        onCancel={() => {}}
      />
    );

    const input = screen.getByPlaceholderText("Ask a question (document search)...");
    await user.type(input, "/n");

    expect(screen.getByRole("button", { name: /notes & marks management/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /notes & marks management/i }));

    expect(input).toHaveValue("/note ");
    expect(onModeChange).toHaveBeenCalledWith("agent");
  });
});
