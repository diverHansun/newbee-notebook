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
const getEffectivePolicy = vi.fn();
const updatePolicyPreference = vi.fn();
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

vi.mock("@/lib/api/policy", () => ({
  getEffectivePolicy: (...args: unknown[]) => getEffectivePolicy(...args),
  updatePolicyPreference: (...args: unknown[]) => updatePolicyPreference(...args),
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
    getEffectivePolicy.mockReset();
    updatePolicyPreference.mockReset();
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
    getEffectivePolicy.mockResolvedValue({
      notebook_id: "nb-1",
      session_id: "session-new",
      policy: "default",
      source: "default",
    });
    updatePolicyPreference.mockImplementation(
      async (_notebookId: string, update: { policy: string; scope: string; session_id?: string }) => ({
        notebook_id: "nb-1",
        session_id: update.session_id ?? "session-new",
        policy: update.policy,
        source: "default",
      })
    );
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
      expect(result.current.explainCard?.error).toBeNull();
      expect(result.current.explainCard?.lastInteractionKey).toBe("explain::Selected text");
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

  it("stores explain stream errors separately from markdown content", async () => {
    startStream.mockImplementationOnce(
      async (_notebookId: string, _request: unknown, callbacks?: { onEvent?: (event: unknown) => void }) => {
        callbacks?.onEvent?.({ type: "content", delta: "Partial answer" });
        callbacks?.onEvent?.({
          type: "error",
          error_code: "E_EXPLAIN",
          message: "Explain failed",
        });
      }
    );

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
      expect(result.current.explainCard?.content).toBe("Partial answer");
      expect(result.current.explainCard?.content).not.toContain("[E_EXPLAIN]");
      expect(result.current.explainCard?.error).toEqual({
        code: "E_EXPLAIN",
        message: "Explain failed",
        retryable: true,
      });
      expect(result.current.explainCard?.isStreaming).toBe(false);
    });
  });

  it("retries the most recent explain request after clearing the error", async () => {
    startStream
      .mockImplementationOnce(
        async (_notebookId: string, _request: unknown, callbacks?: { onEvent?: (event: unknown) => void }) => {
          callbacks?.onEvent?.({
            type: "error",
            error_code: "E_EXPLAIN",
            message: "Explain failed",
          });
        }
      )
      .mockImplementationOnce(
        async (_notebookId: string, _request: unknown, callbacks?: { onEvent?: (event: unknown) => void; onDone?: () => void }) => {
          callbacks?.onEvent?.({ type: "content", delta: "Recovered." });
          callbacks?.onEvent?.({ type: "done" });
          callbacks?.onDone?.();
        }
      );

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
      expect(result.current.explainCard?.error?.code).toBe("E_EXPLAIN");
    });

    await act(async () => {
      await result.current.retryExplainCard();
    });

    await waitFor(() => {
      expect(startStream).toHaveBeenCalledTimes(2);
      expect(startStream.mock.calls[1]?.[1]).toMatchObject(startStream.mock.calls[0]?.[1]);
      expect(result.current.explainCard?.content).toBe("Recovered.");
      expect(result.current.explainCard?.error).toBeNull();
      expect(result.current.explainCard?.isStreaming).toBe(false);
    });
  });
});
