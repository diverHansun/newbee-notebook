import { act, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatPanel } from "@/components/chat/chat-panel";
import type { ChatMessage } from "@/stores/chat-store";
import { renderWithLang } from "@/test/test-utils";

let scrollIntoViewEvents: Array<{ testId: string | null; block: string | null }> = [];

vi.mock("@/components/chat/chat-input", () => ({
  ChatInput: () => <div data-testid="chat-input" />,
}));

vi.mock("@/components/chat/session-select", () => ({
  SessionSelect: () => <div data-testid="session-select" />,
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
  ConfirmDialog: () => null,
}));

vi.mock("@/components/chat/message-item", () => ({
  MessageItem: ({ message }: { message: ChatMessage }) => (
    <div
      data-testid="message-row"
      data-role={message.role}
      data-message-id={message.id}
    >
      {message.content || message.intermediateContent || message.id}
    </div>
  ),
}));

function buildMessage(
  id: string,
  role: ChatMessage["role"],
  content: string,
  overrides: Partial<ChatMessage> = {}
): ChatMessage {
  return {
    id,
    role,
    mode: "agent",
    content,
    createdAt: "2026-04-07T00:00:00.000Z",
    ...overrides,
  };
}

function buildProps(overrides: Partial<React.ComponentProps<typeof ChatPanel>> = {}) {
  return {
    notebookId: "nb-1",
    sessions: [],
    currentSessionId: null,
    messages: [] as ChatMessage[],
    mode: "agent" as const,
    isStreaming: false,
    onModeChange: vi.fn(),
    onSendMessage: vi.fn(),
    onCancel: vi.fn(),
    onSwitchSession: vi.fn(),
    onCreateSession: vi.fn(),
    onDeleteSession: vi.fn(),
    onOpenDocument: vi.fn(),
    onResolveConfirmation: vi.fn(),
    ...overrides,
  };
}

function installChatLayout(
  container: HTMLElement,
  {
    rowMetrics,
    spacerOffsetTop,
    scrollHeight = 1600,
  }: {
    rowMetrics: Record<string, { top: number; height: number }>;
    spacerOffsetTop: number;
    scrollHeight?: number;
  }
) {
  const list = container.querySelector(".chat-message-list") as HTMLDivElement | null;
  if (!list) {
    throw new Error("chat-message-list not found");
  }

  const scrollState =
    (list as HTMLDivElement & { __scrollState?: { top: number } }).__scrollState ??
    { top: 0 };
  (list as HTMLDivElement & { __scrollState?: { top: number } }).__scrollState = scrollState;

  Object.defineProperty(list, "clientHeight", {
    configurable: true,
    value: 600,
  });
  Object.defineProperty(list, "scrollHeight", {
    configurable: true,
    get: () => scrollHeight,
  });
  Object.defineProperty(list, "scrollTop", {
    configurable: true,
    get: () => scrollState.top,
    set: (value: number) => {
      scrollState.top = value;
    },
  });

  const existingScrollToMock =
    (list as HTMLDivElement & { __scrollToMock?: ReturnType<typeof vi.fn> }).__scrollToMock ?? null;
  const scrollToMock =
    existingScrollToMock ??
    vi.fn((options?: { top?: number }) => {
      if (typeof options?.top === "number") {
        scrollState.top = options.top;
      }
    });
  (list as HTMLDivElement & { __scrollToMock?: ReturnType<typeof vi.fn> }).__scrollToMock = scrollToMock;
  list.scrollTo = scrollToMock as unknown as typeof list.scrollTo;

  const rows = Array.from(container.querySelectorAll("[data-testid='message-row']")) as HTMLElement[];
  for (const row of rows) {
    const metrics = row.dataset.messageId ? rowMetrics[row.dataset.messageId] : undefined;
    if (!metrics) continue;
    Object.defineProperty(row, "offsetTop", {
      configurable: true,
      value: metrics.top,
    });
    Object.defineProperty(row, "offsetHeight", {
      configurable: true,
      value: metrics.height,
    });
  }

  const spacer = container.querySelector("[data-testid='chat-bottom-spacer']") as HTMLDivElement | null;
  if (!spacer) {
    throw new Error("chat-bottom-spacer not found");
  }
  Object.defineProperty(spacer, "offsetTop", {
    configurable: true,
    value: spacerOffsetTop,
  });

  const sentinel = container.querySelector("[data-testid='chat-end-sentinel']") as HTMLDivElement | null;
  if (!sentinel) {
    throw new Error("chat-end-sentinel not found");
  }

  return {
    list,
    scrollToMock,
    spacer,
    sentinel,
    get scrollTop() {
      return scrollState.top;
    },
  };
}

describe("ChatPanel scroll anchor", () => {
  beforeEach(() => {
    scrollIntoViewEvents = [];
    vi.useFakeTimers();
    const requestAnimationFrameMock = ((callback: FrameRequestCallback) => {
      return window.setTimeout(() => callback(16), 16);
    }) as typeof requestAnimationFrame;
    const cancelAnimationFrameMock = ((handle: number) => {
      window.clearTimeout(handle);
    }) as typeof cancelAnimationFrame;
    vi.stubGlobal("requestAnimationFrame", requestAnimationFrameMock);
    vi.stubGlobal("cancelAnimationFrame", cancelAnimationFrameMock);
    Object.defineProperty(window, "requestAnimationFrame", {
      configurable: true,
      value: requestAnimationFrameMock,
    });
    Object.defineProperty(window, "cancelAnimationFrame", {
      configurable: true,
      value: cancelAnimationFrameMock,
    });
    window.requestAnimationFrame = requestAnimationFrameMock;
    window.cancelAnimationFrame = cancelAnimationFrameMock;
    vi.spyOn(window, "getComputedStyle").mockImplementation(
      ((element: Element) => {
        if ((element as HTMLElement).classList?.contains("chat-message-list")) {
          return { paddingTop: "16px" } as CSSStyleDeclaration;
        }
        return { paddingTop: "0px" } as CSSStyleDeclaration;
      }) as typeof window.getComputedStyle
    );
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(function (this: HTMLElement, options?: ScrollIntoViewOptions) {
        scrollIntoViewEvents.push({
          testId: this.dataset.testid || this.getAttribute("data-testid"),
          block: typeof options === "object" ? (options.block ?? null) : null,
        });
      }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("anchors a newly sent user message to the natural top inset instead of the bottom", async () => {
    const baseMessages = [
      buildMessage("user-1", "user", "Old question"),
      buildMessage("assistant-1", "assistant", "Old answer"),
    ];
    const nextMessages = [
      ...baseMessages,
      buildMessage("user-2", "user", "New question"),
      buildMessage("assistant-2", "assistant", "", { status: "streaming" }),
    ];

    const { container, rerender } = renderWithLang(<ChatPanel {...buildProps({ messages: baseMessages })} />);

    rerender(<ChatPanel {...buildProps({ messages: nextMessages, isStreaming: true })} />);

    let layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 28 },
      },
      spacerOffsetTop: 520,
    });

    rerender(<ChatPanel {...buildProps({ messages: [...nextMessages], isStreaming: true })} />);
    layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 28 },
      },
      spacerOffsetTop: 520,
    });

    await act(async () => {
      vi.advanceTimersByTime(64);
    });

    expect(layout.scrollToMock).toHaveBeenCalledWith(
      expect.objectContaining({
        top: 404,
        behavior: "auto",
      })
    );
    expect(layout.spacer.style.minHeight).toBe("484px");
  });

  it("still enters send-anchor when assistant content arrives in the same render", async () => {
    const baseMessages = [
      buildMessage("user-1", "user", "Old question"),
      buildMessage("assistant-1", "assistant", "Old answer"),
    ];
    const immediateMessages = [
      ...baseMessages,
      buildMessage("user-2", "user", "New question"),
      buildMessage("assistant-2", "assistant", "Received", { status: "streaming" }),
    ];

    const { container, rerender } = renderWithLang(
      <ChatPanel {...buildProps({ messages: baseMessages })} />
    );

    rerender(<ChatPanel {...buildProps({ messages: immediateMessages, isStreaming: true })} />);

    let layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 44 },
      },
      spacerOffsetTop: 536,
    });

    rerender(<ChatPanel {...buildProps({ messages: [...immediateMessages], isStreaming: true })} />);
    layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 44 },
      },
      spacerOffsetTop: 536,
    });

    await act(async () => {
      vi.advanceTimersByTime(64);
    });

    expect(layout.scrollToMock).toHaveBeenCalledWith(
      expect.objectContaining({
        top: 404,
        behavior: "auto",
      })
    );
    expect(layout.spacer.style.minHeight).toBe("468px");
  });

  it("does not fall back to bottom-follow when assistant content starts during send-anchor mode", async () => {
    const anchoredMessages = [
      buildMessage("user-1", "user", "Old question"),
      buildMessage("assistant-1", "assistant", "Old answer"),
      buildMessage("user-2", "user", "New question"),
      buildMessage("assistant-2", "assistant", "", { status: "streaming" }),
    ];
    const contentMessages = [
      buildMessage("user-1", "user", "Old question"),
      buildMessage("assistant-1", "assistant", "Old answer"),
      buildMessage("user-2", "user", "New question"),
      buildMessage("assistant-2", "assistant", "Received", {
        status: "streaming",
      }),
    ];

    const { container, rerender } = renderWithLang(
      <ChatPanel {...buildProps({ messages: anchoredMessages, isStreaming: true })} />
    );

    let layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 28 },
      },
      spacerOffsetTop: 520,
    });

    await act(async () => {
      vi.runOnlyPendingTimers();
    });

    scrollIntoViewEvents = [];

    rerender(<ChatPanel {...buildProps({ messages: contentMessages, isStreaming: true })} />);

    layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 44 },
      },
      spacerOffsetTop: 536,
    });

    rerender(<ChatPanel {...buildProps({ messages: [...contentMessages], isStreaming: true })} />);
    layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 44 },
      },
      spacerOffsetTop: 536,
    });

    await act(async () => {
      vi.advanceTimersByTime(64);
    });

    expect(
      scrollIntoViewEvents.some(
        (event) => event.testId === "chat-end-sentinel" && event.block === "end"
      )
    ).toBe(false);
    expect(layout.scrollTop).toBe(404);
  });

  it("stops re-anchoring after explicit user scroll during streaming", async () => {
    const anchoredMessages = [
      buildMessage("user-1", "user", "Old question"),
      buildMessage("assistant-1", "assistant", "Old answer"),
      buildMessage("user-2", "user", "New question"),
      buildMessage("assistant-2", "assistant", "", { status: "streaming" }),
    ];
    const contentMessages = [
      buildMessage("user-1", "user", "Old question"),
      buildMessage("assistant-1", "assistant", "Old answer"),
      buildMessage("user-2", "user", "New question"),
      buildMessage("assistant-2", "assistant", "Received", { status: "streaming" }),
    ];

    const { container, rerender } = renderWithLang(
      <ChatPanel {...buildProps({ messages: anchoredMessages, isStreaming: true })} />
    );

    let layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 28 },
      },
      spacerOffsetTop: 520,
    });

    await act(async () => {
      vi.runOnlyPendingTimers();
    });

    rerender(<ChatPanel {...buildProps({ messages: [...anchoredMessages], isStreaming: true })} />);
    layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 28 },
      },
      spacerOffsetTop: 520,
    });

    await act(async () => {
      vi.advanceTimersByTime(64);
    });

    await act(async () => {
      vi.advanceTimersByTime(220);
    });

    fireEvent.wheel(layout.list);
    layout.list.scrollTop = 120;
    fireEvent.scroll(layout.list);

    layout.scrollToMock.mockClear();
    scrollIntoViewEvents = [];

    rerender(<ChatPanel {...buildProps({ messages: contentMessages, isStreaming: true })} />);
    layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 44 },
      },
      spacerOffsetTop: 536,
    });

    await act(async () => {
      vi.advanceTimersByTime(64);
    });

    expect(layout.scrollToMock).not.toHaveBeenCalled();
    expect(
      scrollIntoViewEvents.some(
        (event) => event.testId === "chat-end-sentinel" && event.block === "end"
      )
    ).toBe(false);
    expect(layout.scrollTop).toBe(120);
    expect(layout.spacer.style.minHeight).not.toBe("0px");
  });

  it("re-anchors on the next user send after browsing history", async () => {
    const anchoredMessages = [
      buildMessage("user-1", "user", "Old question"),
      buildMessage("assistant-1", "assistant", "Old answer"),
      buildMessage("user-2", "user", "New question"),
      buildMessage("assistant-2", "assistant", "", { status: "streaming" }),
    ];
    const nextTurnMessages = [
      buildMessage("user-1", "user", "Old question"),
      buildMessage("assistant-1", "assistant", "Old answer"),
      buildMessage("user-2", "user", "New question"),
      buildMessage("assistant-2", "assistant", "Received", { status: "done" }),
      buildMessage("user-3", "user", "Follow-up question"),
      buildMessage("assistant-3", "assistant", "", { status: "streaming" }),
    ];

    const { container, rerender } = renderWithLang(
      <ChatPanel {...buildProps({ messages: anchoredMessages, isStreaming: true })} />
    );

    let layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 28 },
      },
      spacerOffsetTop: 520,
    });

    await act(async () => {
      vi.runOnlyPendingTimers();
    });

    fireEvent.wheel(layout.list);
    layout.list.scrollTop = 120;
    fireEvent.scroll(layout.list);

    layout.scrollToMock.mockClear();

    rerender(<ChatPanel {...buildProps({ messages: nextTurnMessages, isStreaming: true })} />);
    layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 44 },
        "user-3": { top: 760, height: 52 },
        "assistant-3": { top: 836, height: 28 },
      },
      spacerOffsetTop: 864,
    });

    rerender(<ChatPanel {...buildProps({ messages: [...nextTurnMessages], isStreaming: true })} />);
    layout = installChatLayout(container, {
      rowMetrics: {
        "user-1": { top: 40, height: 40 },
        "assistant-1": { top: 100, height: 100 },
        "user-2": { top: 420, height: 48 },
        "assistant-2": { top: 492, height: 44 },
        "user-3": { top: 760, height: 52 },
        "assistant-3": { top: 836, height: 28 },
      },
      spacerOffsetTop: 864,
    });

    await act(async () => {
      vi.advanceTimersByTime(64);
    });

    expect(layout.scrollToMock).toHaveBeenCalledWith(
      expect.objectContaining({
        top: 744,
        behavior: "auto",
      })
    );
  });
});
