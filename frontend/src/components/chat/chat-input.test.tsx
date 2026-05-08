import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatInput } from "@/components/chat/chat-input";
import { renderWithLang } from "@/test/test-utils";

const uploadChatImage = vi.fn();

vi.mock("@/lib/api/chat-images", () => ({
  uploadChatImage: (...args: unknown[]) => uploadChatImage(...args),
}));

vi.mock("@/components/chat/source-selector", () => ({
  SourceSelector: () => null,
}));

vi.mock("@/components/ui/segmented-control", () => ({
  SegmentedControl: ({
    value,
    onChange,
  }: {
    value: "agent" | "ask";
    onChange: (value: "agent" | "ask") => void;
  }) => (
    <button type="button" onClick={() => onChange(value === "agent" ? "ask" : "agent")}>
      Toggle mode
    </button>
  ),
}));

describe("ChatInput", () => {
  beforeEach(() => {
    uploadChatImage.mockReset();
    uploadChatImage.mockResolvedValue({
      image_id: "img-1",
      mime_type: "image/png",
      size_bytes: 128,
      width: 64,
      height: 64,
      thumbnail_url: "/api/v1/chat/images/img-1/thumbnail",
      preview_url: "/api/v1/chat/images/img-1/thumbnail",
    });
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:preview"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
  });

  it("shows slash command hint and completes the note command", async () => {
    const user = userEvent.setup();
    const onModeChange = vi.fn();

    renderWithLang(
      <ChatInput
        notebookId="nb-1"
        currentSessionId="session-1"
        mode="ask"
        isStreaming={false}
        sourceDocIds={null}
        onSourceDocIdsChange={() => {}}
        onModeChange={onModeChange}
        onEnsureSession={async () => "session-1"}
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

  it("shows diagram slash command and completes /diagram", async () => {
    const user = userEvent.setup();
    const onModeChange = vi.fn();

    renderWithLang(
      <ChatInput
        notebookId="nb-1"
        currentSessionId="session-1"
        mode="ask"
        isStreaming={false}
        sourceDocIds={null}
        onSourceDocIdsChange={() => {}}
        onModeChange={onModeChange}
        onEnsureSession={async () => "session-1"}
        onSend={() => {}}
        onCancel={() => {}}
      />
    );

    const input = screen.getByPlaceholderText("Ask a question (document search)...");
    await user.type(input, "/d");

    expect(
      screen.getByRole("button", { name: /generate a diagram \(mind map \/ flowchart \/ sequence\)/i })
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /generate a diagram \(mind map \/ flowchart \/ sequence\)/i })
    );

    expect(input).toHaveValue("/diagram ");
    expect(onModeChange).toHaveBeenCalledWith("agent");
  });

  it("shows video slash command and completes /video", async () => {
    const user = userEvent.setup();
    const onModeChange = vi.fn();

    renderWithLang(
      <ChatInput
        notebookId="nb-1"
        currentSessionId="session-1"
        mode="ask"
        isStreaming={false}
        sourceDocIds={null}
        onSourceDocIdsChange={() => {}}
        onModeChange={onModeChange}
        onEnsureSession={async () => "session-1"}
        onSend={() => {}}
        onCancel={() => {}}
      />
    );

    const input = screen.getByPlaceholderText("Ask a question (document search)...");
    await user.type(input, "/v");

    expect(screen.getByRole("button", { name: /summarize and manage video content/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /summarize and manage video content/i }));

    expect(input).toHaveValue("/video ");
    expect(onModeChange).toHaveBeenCalledWith("agent");
  });

  it("uploads one selected image at a time and sends ready image ids with text", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const { container } = renderWithLang(
      <ChatInput
        notebookId="nb-1"
        currentSessionId="session-1"
        mode="agent"
        isStreaming={false}
        sourceDocIds={null}
        onSourceDocIdsChange={() => {}}
        onModeChange={() => {}}
        onEnsureSession={async () => "session-1"}
        onSend={onSend}
        onCancel={() => {}}
      />
    );

    const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]');
    expect(fileInput).not.toBeNull();
    expect(fileInput).not.toHaveAttribute("multiple");

    await user.upload(fileInput!, new File(["png"], "diagram.png", { type: "image/png" }));

    await waitFor(() => {
      expect(uploadChatImage).toHaveBeenCalledWith("session-1", expect.any(File));
      expect(screen.getByRole("img", { name: "Uploaded image preview" })).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("Type a message (agent + tools)..."), "read this");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(onSend).toHaveBeenCalledWith("read this", "agent", ["img-1"]);
  });

  it("keeps uploaded images when switching between agent and ask mode", async () => {
    const user = userEvent.setup();
    const onModeChange = vi.fn();
    const { container } = renderWithLang(
      <ChatInput
        notebookId="nb-1"
        currentSessionId="session-1"
        mode="agent"
        isStreaming={false}
        sourceDocIds={null}
        onSourceDocIdsChange={() => {}}
        onModeChange={onModeChange}
        onEnsureSession={async () => "session-1"}
        onSend={() => {}}
        onCancel={() => {}}
      />
    );

    await user.upload(
      container.querySelector<HTMLInputElement>('input[type="file"]')!,
      new File(["png"], "diagram.png", { type: "image/png" })
    );

    await waitFor(() => {
      expect(screen.getByRole("img", { name: "Uploaded image preview" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Toggle mode" }));

    expect(onModeChange).toHaveBeenCalledWith("ask");
    expect(screen.getByRole("img", { name: "Uploaded image preview" })).toBeInTheDocument();
  });

  it("disables policy switching until a session exists", () => {
    renderWithLang(
      <ChatInput
        notebookId="nb-1"
        currentSessionId={null}
        mode="agent"
        isStreaming={false}
        sourceDocIds={null}
        policy={{
          notebook_id: "nb-1",
          session_id: null,
          policy: "default",
          source: "default",
        }}
        onSourceDocIdsChange={() => {}}
        onPolicyChange={() => {}}
        onModeChange={() => {}}
        onEnsureSession={async () => "session-1"}
        onSend={() => {}}
        onCancel={() => {}}
      />
    );

    expect(screen.getByRole("button", { name: "Agent permission policy" })).toBeDisabled();
  });
});
