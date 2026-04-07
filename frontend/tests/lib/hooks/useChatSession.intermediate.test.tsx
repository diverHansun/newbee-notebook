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

describe("useChatSession intermediate content flow", () => {
  const session = {
    session_id: "session-1",
    notebook_id: "nb-1",
    title: "Session 1",
    message_count: 0,
    include_ec_context: false,
    created_at: "2026-04-07T00:00:00.000Z",
    updated_at: "2026-04-07T00:00:00.000Z",
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

    listSessions.mockResolvedValue({
      data: [session],
      pagination: {
        total: 1,
        limit: 50,
        offset: 0,
        has_next: false,
        has_prev: false,
      },
    });
    listSessionMessages.mockResolvedValue({ data: [] });
    cancelStream.mockResolvedValue(undefined);
  });

  it("rotates intermediate content across reasoning rounds and clears it when final content starts", async () => {
    let callbacks:
      | {
          onEvent?: (event: any) => void;
          onDone?: () => void;
        }
      | undefined;

    startStream.mockImplementation(
      async (_notebookId: string, _request: unknown, streamCallbacks?: typeof callbacks) => {
        callbacks = streamCallbacks;
      }
    );

    const wrapper = createHookWrapper("en");
    const { result } = renderHook(() => useChatSession("nb-1"), { wrapper });

    await waitFor(() => {
      expect(listSessions).toHaveBeenCalledWith("nb-1", 50, 0);
      expect(result.current.currentSessionId).toBe("session-1");
    });

    await act(async () => {
      await result.current.sendMessage("What is doc 1?", "ask");
    });

    await act(async () => {
      callbacks?.onEvent?.({ type: "start", message_id: 101 });
      callbacks?.onEvent?.({ type: "phase", stage: "reasoning" });
      callbacks?.onEvent?.({ type: "thinking", stage: "reasoning" });
      callbacks?.onEvent?.({ type: "intermediate_content", delta: "Let me check first." });
      callbacks?.onEvent?.({
        type: "tool_call",
        tool_name: "knowledge_base",
        tool_call_id: "call-1",
        tool_input: { query: "What is doc 1?" },
      });
      callbacks?.onEvent?.({
        type: "tool_result",
        tool_name: "knowledge_base",
        tool_call_id: "call-1",
        success: true,
        content_preview: "Doc 1 says hello.",
        quality_meta: { quality_band: "high" },
      });
    });

    let assistantMessage = result.current.messages.find((message) => message.role === "assistant");
    expect(assistantMessage?.intermediateContent).toBe("Let me check first.");
    expect(assistantMessage?.thinkingStage).toBe("reasoning");
    expect(assistantMessage?.toolSteps).toHaveLength(1);

    await act(async () => {
      callbacks?.onEvent?.({ type: "phase", stage: "reasoning" });
    });

    assistantMessage = result.current.messages.find((message) => message.role === "assistant");
    expect(assistantMessage?.intermediateContent).toBe("Let me check first.");

    await act(async () => {
      callbacks?.onEvent?.({
        type: "intermediate_content",
        delta: "I will verify it once more.",
      });
      callbacks?.onEvent?.({ type: "phase", stage: "synthesizing" });
      callbacks?.onEvent?.({ type: "content", delta: "Here is the final answer." });
    });

    assistantMessage = result.current.messages.find((message) => message.role === "assistant");
    expect(assistantMessage?.content).toBe("Here is the final answer.");
    expect(assistantMessage?.intermediateContent).toBeUndefined();
    expect(assistantMessage?.exitingIntermediateContent).toBe("I will verify it once more.");
    expect(assistantMessage?.intermediateGeneration).toBe(2);

    await act(async () => {
      callbacks?.onEvent?.({ type: "done" });
      callbacks?.onDone?.();
    });

    assistantMessage = result.current.messages.find((message) => message.role === "assistant");
    expect(assistantMessage?.status).toBe("done");
    expect(assistantMessage?.exitingIntermediateContent).toBeNull();
  });

  it("drops intermediate-only assistant messages when the stream is cancelled", async () => {
    let callbacks:
      | {
          onEvent?: (event: any) => void;
        }
      | undefined;

    startStream.mockImplementation(
      async (_notebookId: string, _request: unknown, streamCallbacks?: typeof callbacks) => {
        callbacks = streamCallbacks;
      }
    );

    const wrapper = createHookWrapper("en");
    const { result } = renderHook(() => useChatSession("nb-1"), { wrapper });

    await waitFor(() => {
      expect(result.current.currentSessionId).toBe("session-1");
    });

    await act(async () => {
      await result.current.sendMessage("What is doc 1?", "ask");
    });

    await act(async () => {
      callbacks?.onEvent?.({ type: "phase", stage: "reasoning" });
      callbacks?.onEvent?.({ type: "intermediate_content", delta: "Let me check first." });
    });

    expect(result.current.messages.filter((message) => message.role === "assistant")).toHaveLength(1);

    await act(async () => {
      await result.current.cancelStream();
    });

    expect(cancelStream).toHaveBeenCalledTimes(1);
    expect(result.current.messages.some((message) => message.role === "assistant")).toBe(false);
  });
});
