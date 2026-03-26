import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
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
      ],
      pagination: {
        total: 1,
        limit: 20,
        offset: 0,
        has_next: false,
        has_prev: false,
      },
    });
    listSessionMessages.mockResolvedValue({ data: [] });
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
    const { result } = renderHook(() => useChatSession("nb-1"), {
      wrapper: createHookWrapper(),
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
});
