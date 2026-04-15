import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useChatSession } from "@/lib/hooks/useChatSession";
import { useChatStore } from "@/stores/chat-store";
import { createHookWrapper } from "@/test/test-utils";

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

describe("useChatSession explain session creation", () => {
  const createdSession = {
    session_id: "session-new",
    notebook_id: "nb-1",
    title: null,
    message_count: 0,
    include_ec_context: false,
    created_at: "2026-04-06T00:00:00.000Z",
    updated_at: "2026-04-06T00:00:00.000Z",
  };

  beforeEach(() => {
    useChatStore.setState({
      currentSessionId: null,
      messages: [],
      isStreaming: false,
      currentMode: "agent",
      streamingMessageId: null,
      explainCard: null,
    });

    listSessions.mockReset();
    listSessionMessages.mockReset();
    createSession.mockReset();
    deleteSession.mockReset();
    chatOnce.mockReset();
    startStream.mockReset();
    cancelStream.mockReset();

    listSessions.mockResolvedValueOnce({
      data: [],
      pagination: {
        total: 0,
        limit: 50,
        offset: 0,
        has_next: false,
        has_prev: false,
      },
    });
    listSessions.mockResolvedValue({
      data: [createdSession],
      pagination: {
        total: 1,
        limit: 50,
        offset: 0,
        has_next: false,
        has_prev: false,
      },
    });
    listSessionMessages.mockResolvedValue({ data: [] });
    createSession.mockResolvedValue(createdSession);
    startStream.mockImplementation(
      async (_notebookId: string, _request: unknown, callbacks?: { onEvent?: (event: unknown) => void; onDone?: () => void }) => {
        callbacks?.onEvent?.({ type: "content", delta: "Explained." });
        callbacks?.onEvent?.({ type: "done" });
        callbacks?.onDone?.();
      }
    );
  });

  it("creates a session automatically before running explain", async () => {
    const wrapper = createHookWrapper("en");
    const { result } = renderHook(() => useChatSession("nb-1"), { wrapper });

    await waitFor(() => {
      expect(listSessions).toHaveBeenCalledWith("nb-1", 50, 0);
    });

    await act(async () => {
      await result.current.sendMessage("Explain selection", "explain", {
        document_id: "doc-1",
        selected_text: "Selected text",
      });
    });

    await waitFor(() => {
      expect(createSession).toHaveBeenCalledWith("nb-1", { title: undefined });
      expect(result.current.currentSessionId).toBe("session-new");
      expect(result.current.explainCard?.content).toBe("Explained.");
      expect(result.current.explainCard?.isStreaming).toBe(false);
    });

    expect(startStream).toHaveBeenCalledTimes(1);
    expect(startStream.mock.calls[0]?.[1]).toMatchObject({
      message: "Explain selection",
      mode: "explain",
      session_id: "session-new",
      context: {
        document_id: "doc-1",
        selected_text: "Selected text",
      },
    });
  });
});