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
    expect(screen.getByText("Update note metadata.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Allow once" }));
    await user.click(screen.getByRole("button", { name: "Reject" }));

    expect(onResolveConfirmation).toHaveBeenNthCalledWith(1, "req-1", "once");
    expect(onResolveConfirmation).toHaveBeenNthCalledWith(2, "req-1", "reject");
  });

  it("shows permission request instead of a running tool row while waiting for approval", () => {
    const message: ChatMessage = {
      ...assistantMessage,
      content: "",
      toolSteps: [
        {
          id: "tool-bash",
          toolName: "bash",
          status: "running",
        },
      ],
      thinkingStage: "retrieving",
    };

    renderWithLang(<MessageItem message={message} onOpenDocument={() => {}} />);

    expect(screen.getByText("Update note metadata.")).toBeInTheDocument();
    expect(screen.queryByText("Run shell...")).toBeNull();
    expect(screen.queryByText("Retrieving knowledge base...")).toBeNull();
  });

  it("hides collapsed confirmed permission status after approval", () => {
    const message: ChatMessage = {
      ...assistantMessage,
      pendingConfirmation: {
        ...assistantMessage.pendingConfirmation!,
        status: "collapsed",
        resolvedFrom: "confirmed",
      },
    };

    renderWithLang(<MessageItem message={message} onOpenDocument={() => {}} />);

    expect(screen.queryByText(/Confirmed/i)).toBeNull();
    expect(screen.queryByText(/Confirm action/i)).toBeNull();
  });

  it("renders bash tool progress as shell for users", () => {
    const message: ChatMessage = {
      ...assistantMessage,
      content: "",
      pendingConfirmation: undefined,
      toolSteps: [
        {
          id: "tool-bash",
          toolName: "bash",
          status: "running",
        },
      ],
      thinkingStage: null,
    };

    renderWithLang(<MessageItem message={message} onOpenDocument={() => {}} />);

    expect(screen.getByText("Run shell...")).toBeInTheDocument();
    expect(screen.queryByText("Run bash...")).toBeNull();
  });

  it("renders bash nonzero exits as shell warnings instead of failed tool calls", () => {
    const message: ChatMessage = {
      ...assistantMessage,
      content: "",
      pendingConfirmation: undefined,
      toolSteps: [
        {
          id: "tool-bash",
          toolName: "bash",
          status: "warning",
          errorCode: "nonzero_exit",
          exitCode: 1,
        },
      ],
      thinkingStage: null,
    };

    renderWithLang(<MessageItem message={message} onOpenDocument={() => {}} />);

    expect(screen.getByText("Shell exited 1")).toBeInTheDocument();
    expect(screen.queryByText("Error")).toBeNull();
  });

  it("keeps intermediate block hidden once final content stream has started", () => {
    const message: ChatMessage = {
      ...assistantMessage,
      content: "",
      finalContentStarted: true,
      intermediateContent: "thinking...",
      pendingConfirmation: undefined,
      toolSteps: [],
    };

    const { container } = renderWithLang(
      <MessageItem message={message} onOpenDocument={() => {}} />
    );

    expect(container.querySelector("[data-testid='assistant-intermediate-current']")).toBeNull();
    expect(container.querySelector("[data-testid='assistant-message-body']")).not.toBeNull();
  });

  it("does not render streaming status text when assistant is generating final content", () => {
    const message: ChatMessage = {
      ...assistantMessage,
      content: "Partial reply",
      pendingConfirmation: undefined,
      toolSteps: [],
      thinkingStage: null,
    };

    renderWithLang(<MessageItem message={message} onOpenDocument={() => {}} />);

    expect(screen.queryByText("Generating...")).toBeNull();
  });

  it("localizes image generation tool step label in Chinese", () => {
    const message: ChatMessage = {
      ...assistantMessage,
      content: "",
      pendingConfirmation: undefined,
      toolSteps: [
        {
          id: "tool-1",
          toolName: "image_generate",
          status: "running",
        },
      ],
      thinkingStage: null,
    };

    renderWithLang(<MessageItem message={message} onOpenDocument={() => {}} />, {
      lang: "zh",
    });

    expect(screen.getAllByText("生成图片...").length).toBeGreaterThan(0);
  });

  it("shows pending image glass card as soon as image tool starts running", () => {
    const message: ChatMessage = {
      ...assistantMessage,
      content: "",
      pendingConfirmation: undefined,
      toolSteps: [
        {
          id: "tool-pending",
          toolName: "image_generate",
          status: "running",
        },
      ],
      images: [],
      thinkingStage: null,
    };

    renderWithLang(<MessageItem message={message} onOpenDocument={() => {}} />, {
      lang: "zh",
    });

    expect(screen.getByTestId("generated-image-card-pending")).toBeInTheDocument();
  });

  it("keeps spinner visible when streaming has whitespace-only content even if finalContentStarted is true", () => {
    const message: ChatMessage = {
      ...assistantMessage,
      content: " \n",
      finalContentStarted: true,
      pendingConfirmation: undefined,
      toolSteps: [],
      thinkingStage: "retrieving",
    };

    renderWithLang(<MessageItem message={message} onOpenDocument={() => {}} />, {
      lang: "zh",
    });

    expect(screen.getByText("正在检索知识库...")).toBeInTheDocument();
  });

  it("strips markdown image placeholders from assistant content when generated images are present", () => {
    const message: ChatMessage = {
      ...assistantMessage,
      content:
        "已为您生成一张软萌小猫插画：\n\n![软萌小猫插画](generated_image_url)\n\n这只小猫有着圆润可爱的外形。",
      status: "done",
      pendingConfirmation: undefined,
      toolSteps: [],
      images: [
        {
          imageId: "img-cleanup-1",
          storageKey: "generated-images/demo/img-cleanup-1.png",
          prompt: "软萌小猫插画",
          provider: "qwen",
          model: "qwen-image-2.0-pro",
          width: 1024,
          height: 1024,
        },
      ],
    };

    renderWithLang(<MessageItem message={message} onOpenDocument={() => {}} />, {
      lang: "zh",
    });

    expect(
      screen.getByText((text) => {
        return (
          text.includes("已为您生成一张软萌小猫插画：") &&
          text.includes("这只小猫有着圆润可爱的外形。")
        );
      })
    ).toBeInTheDocument();
    expect(screen.queryByText(/generated_image_url/i)).toBeNull();
  });

  it("renders uploaded user image thumbnails separately from generated image cards", () => {
    const message: ChatMessage = {
      id: "user-1",
      role: "user",
      mode: "ask",
      content: "看看这张图",
      status: "done",
      createdAt: "2026-03-19T00:00:00.000Z",
      imageIds: ["img-upload-1", "img-upload-2"],
    };

    renderWithLang(<MessageItem message={message} onOpenDocument={() => {}} />, {
      lang: "zh",
    });

    const thumbnails = screen.getAllByRole("img", { name: "上传图片缩略图" });
    expect(thumbnails).toHaveLength(2);
    expect(thumbnails[0]).toHaveAttribute("src", "/api/v1/chat/images/img-upload-1/thumbnail");
    expect(thumbnails[1]).toHaveAttribute("src", "/api/v1/chat/images/img-upload-2/thumbnail");
    expect(screen.queryByTestId("generated-image-list")).toBeNull();
  });
});
