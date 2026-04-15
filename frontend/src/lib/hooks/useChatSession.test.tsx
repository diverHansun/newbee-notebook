import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useChatSession } from "@/lib/hooks/useChatSession";
import { LanguageContext } from "@/lib/i18n/language-context";
import { useChatStore } from "@/stores/chat-store";
import { createQueryClient } from "@/test/test-utils";

const listSessions = vi.fn();
const listSessionMessages = vi.fn();
const createSession = vi.fn();
const deleteSession = vi.fn();
const chatOnce = vi.fn();
const startStream = vi.fn();
const cancelStream = vi.fn();

vi.mock("@/lib/api/sessions", () => ({
  listSessions: (...args: unknown[]) => listSessions(...args),
  listSessionMessages: (...args: unknown[]) => listSessionMessages(...args),
  createSession: (...args: unknown[]) => createSession(...args),
  deleteSession: (...args: unknown[]) => deleteSession(...args),
}));

vi.mock("@/lib/api/chat", () => ({
  chatOnce: (...args: unknown[]) => chatOnce(...args),
}));

vi.mock("@/lib/hooks/useChatStream", () => ({
  useChatStream: () => ({
    isStreaming: false,
    startStream: (...args: unknown[]) => startStream(...args),
    cancelStream: (...args: unknown[]) => cancelStream(...args),
  }),
}));

function createWrapper() {
  const queryClient = createQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>
        {children}
      </LanguageContext.Provider>
    </QueryClientProvider>
  );
  return { queryClient, wrapper };
}

describe("useChatSession", () => {
  beforeEach(() => {
    useChatStore.setState({
      currentSessionId: null,
      messages: [],
      isStreaming: false,
      currentMode: "agent",
      streamingMessageId: null,
      explainCard: null,
    });
    listSessions.mockResolvedValue({
      data: [
        {
          session_id: "session-1",
          notebook_id: "nb-1",
          title: "Session 1",
          message_count: 0,
          include_ec_context: false,
          created_at: "2026-03-19T00:00:00.000Z",
          updated_at: "2026-03-19T00:00:00.000Z",
        },
        {
          session_id: "session-2",
          notebook_id: "nb-1",
          title: "Session 2",
          message_count: 0,
          include_ec_context: false,
          created_at: "2026-03-19T00:01:00.000Z",
          updated_at: "2026-03-19T00:01:00.000Z",
        },
      ],
      pagination: {
        total: 2,
        limit: 20,
        offset: 0,
        has_next: false,
        has_prev: false,
      },
    });
    listSessionMessages.mockImplementation(async (sessionId: string) => {
      if (sessionId === "session-1") {
        return { data: [] };
      }
      if (sessionId === "session-2") {
        return { data: [] };
      }
      return { data: [] };
    });
    createSession.mockReset();
    deleteSession.mockReset();
    chatOnce.mockReset();
    cancelStream.mockReset();
    startStream.mockImplementation(
      async (_notebookId: string, _request: unknown, callbacks?: { onEvent?: (event: unknown) => void }) => {
        callbacks?.onEvent?.({ type: "start", message_id: 123 });
        callbacks?.onEvent?.({
          type: "confirmation_request",
          request_id: "req-1",
          tool_name: "update_note",
          action_type: "update",
          target_type: "note",
          args_summary: { note_id: "note-1" },
          description: "Update note metadata.",
        } as never);
      }
    );
  });

  it("stores pending confirmation when the stream emits a confirmation request", async () => {
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useChatSession("nb-1"), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.currentSessionId).toBe("session-1");
    });

    await act(async () => {
      await result.current.sendMessage("Update the note", "agent");
    });

    await waitFor(() => {
      const assistantMessage = result.current.messages.find((item) => item.role === "assistant");
      expect(assistantMessage?.pendingConfirmation?.requestId).toBe("req-1");
      expect(assistantMessage?.pendingConfirmation?.argsSummary.note_id).toBe("note-1");
      expect(assistantMessage?.pendingConfirmation?.status).toBe("pending");
    });
  });

  it("requests up to 50 sessions for the chat session picker", async () => {
    const { wrapper } = createWrapper();

    renderHook(() => useChatSession("nb-1"), {
      wrapper,
    });

    await waitFor(() => {
      expect(listSessions).toHaveBeenCalledWith("nb-1", 50, 0);
    });
  });

  it("invalidates the shared video summary list after a /video command finishes", async () => {
    startStream.mockImplementationOnce(
      async (_notebookId: string, _request: unknown, callbacks?: { onEvent?: (event: unknown) => void }) => {
        callbacks?.onEvent?.({ type: "start", message_id: 456 });
        callbacks?.onEvent?.({ type: "done" });
      }
    );

    const { queryClient, wrapper } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useChatSession("nb-1"), { wrapper });

    await waitFor(() => {
      expect(result.current.currentSessionId).toBe("session-1");
    });

    await act(async () => {
      await result.current.sendMessage("/video summarize BV1", "agent");
    });

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["video-summaries", "all"],
      });
    });
  });

  it("keeps local streaming messages when switching away and back to the active session", async () => {
    let resolveStream: (() => void) | undefined;
    startStream.mockImplementationOnce(
      async (_notebookId: string, _request: unknown, callbacks?: { onEvent?: (event: unknown) => void }) => {
        callbacks?.onEvent?.({ type: "start", message_id: 789 });
        await new Promise<void>((resolve) => {
          resolveStream = resolve;
        });
      }
    );

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useChatSession("nb-1"), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.currentSessionId).toBe("session-1");
    });

    act(() => {
      void result.current.sendMessage("What is Jungian psychology?", "agent");
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0]?.role).toBe("user");
      expect(result.current.messages[1]?.role).toBe("assistant");
      expect(result.current.messages[0]?.content).toBe("What is Jungian psychology?");
      expect(result.current.messages[1]?.status).toBe("streaming");
    });

    act(() => {
      result.current.switchSession("session-2");
    });

    await waitFor(() => {
      expect(result.current.currentSessionId).toBe("session-2");
    });

    expect(result.current.messages).toHaveLength(0);

    act(() => {
      result.current.switchSession("session-1");
    });

    await waitFor(() => {
      expect(result.current.currentSessionId).toBe("session-1");
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0]?.role).toBe("user");
      expect(result.current.messages[1]?.role).toBe("assistant");
      expect(result.current.messages[0]?.content).toBe("What is Jungian psychology?");
      expect(result.current.messages[1]?.status).toBe("streaming");
    });

    resolveStream?.();
  });

  it("uses typewriter progression for final content and completes after drain", async () => {
    startStream.mockImplementationOnce(
      async (_notebookId: string, _request: unknown, callbacks?: { onEvent?: (event: unknown) => void }) => {
        callbacks?.onEvent?.({ type: "start", message_id: 321 });
        callbacks?.onEvent?.({ type: "content", delta: "**Hi**" });
        callbacks?.onEvent?.({ type: "done" });
      }
    );

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useChatSession("nb-1"), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.currentSessionId).toBe("session-1");
    });

    vi.useFakeTimers();
    const requestAnimationFrameMock = ((callback: FrameRequestCallback) => {
      return window.setTimeout(() => callback(window.performance.now()), 16);
    }) as typeof requestAnimationFrame;
    const cancelAnimationFrameMock = ((handle: number) => {
      window.clearTimeout(handle);
    }) as typeof cancelAnimationFrame;
    vi.stubGlobal("requestAnimationFrame", requestAnimationFrameMock);
    vi.stubGlobal("cancelAnimationFrame", cancelAnimationFrameMock);

    await act(async () => {
      await result.current.sendMessage("Say hi", "agent");
    });

    await act(async () => {
      vi.advanceTimersByTime(40);
    });

    const assistantStreaming = result.current.messages.find((item) => item.role === "assistant");
    expect(assistantStreaming?.status).toBe("streaming");
    expect(assistantStreaming?.content).not.toBe("**Hi**");

    await act(async () => {
      vi.advanceTimersByTime(500);
    });

    const assistantDone = result.current.messages.find((item) => item.role === "assistant");
    expect(assistantDone?.content).toBe("**Hi**");
    expect(assistantDone?.status).toBe("done");
    expect(assistantDone?.finalContentStarted).toBe(false);

    vi.useRealTimers();
  });
});
