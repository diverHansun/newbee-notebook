import { ApiError } from "@/lib/api/client";
import { ChatRequest, ChatResponse, SseEvent } from "@/lib/api/types";
import { parseSseStream } from "@/lib/utils/sse-parser";

type StreamOptions = {
  signal?: AbortSignal;
  onEvent: (event: SseEvent) => void;
};

export async function chatOnce(notebookId: string, request: ChatRequest) {
  const response = await fetch(`/api/v1/chat/notebooks/${notebookId}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let errorPayload: any = null;
    try {
      errorPayload = await response.json();
    } catch {
      errorPayload = null;
    }
    throw new ApiError(
      response.status,
      errorPayload?.error_code || "E_CHAT",
      errorPayload?.message || String(errorPayload?.detail || "Chat request failed"),
      errorPayload?.details
    );
  }

  return (await response.json()) as ChatResponse;
}

export async function chatStream(
  notebookId: string,
  request: ChatRequest,
  options: StreamOptions
): Promise<void> {
  const response = await fetch(`/api/v1/chat/notebooks/${notebookId}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
    signal: options.signal,
  });

  if (!response.ok) {
    let errorPayload: any = null;
    try {
      errorPayload = await response.json();
    } catch {
      errorPayload = null;
    }
    throw new ApiError(
      response.status,
      errorPayload?.error_code || "E_CHAT_STREAM",
      errorPayload?.message || String(errorPayload?.detail || "Chat stream request failed"),
      errorPayload?.details
    );
  }

  if (!response.body) {
    throw new ApiError(500, "E_STREAM_BODY", "Stream body is empty");
  }

  await parseSseStream(response.body, {
    signal: options.signal,
    onEvent: options.onEvent,
  });
}

export function cancelChatStream(messageId: number) {
  return fetch(`/api/v1/chat/stream/${messageId}/cancel`, {
    method: "POST",
  });
}
