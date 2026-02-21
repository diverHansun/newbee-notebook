"use client";

import { useCallback, useRef, useState } from "react";

import { chatStream, cancelChatStream } from "@/lib/api/chat";
import { ChatRequest, SseEvent } from "@/lib/api/types";

type StreamCallbacks = {
  onEvent?: (event: SseEvent) => void;
  onError?: (error: unknown) => void;
  onDone?: () => void;
};

export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messageIdRef = useRef<number | null>(null);

  const startStream = useCallback(
    async (notebookId: string, request: ChatRequest, callbacks?: StreamCallbacks) => {
      if (abortRef.current) {
        abortRef.current.abort();
      }

      const controller = new AbortController();
      abortRef.current = controller;
      messageIdRef.current = null;
      setIsStreaming(true);

      try {
        await chatStream(notebookId, request, {
          signal: controller.signal,
          onEvent: (event) => {
            if (event.type === "start") {
              messageIdRef.current = event.message_id;
            }
            callbacks?.onEvent?.(event);
          },
        });
        callbacks?.onDone?.();
      } catch (error) {
        if (!controller.signal.aborted) {
          callbacks?.onError?.(error);
        }
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
        setIsStreaming(false);
      }
    },
    []
  );

  const cancelStream = useCallback(async () => {
    const activeController = abortRef.current;
    if (activeController) {
      activeController.abort();
      abortRef.current = null;
    }
    const messageId = messageIdRef.current;
    messageIdRef.current = null;
    setIsStreaming(false);

    if (messageId) {
      try {
        await cancelChatStream(messageId);
      } catch {
        // Best-effort cancel endpoint.
      }
    }
  }, []);

  return {
    isStreaming,
    startStream,
    cancelStream,
  };
}
