import { ApiError, apiFetch, buildError } from "@/lib/api/client";
import { ApiErrorPayload, ChatRequest, ChatResponse, SseEvent } from "@/lib/api/types";
import { parseSseStream } from "@/lib/utils/sse-parser";

type ConfirmActionRequest = {
  request_id: string;
  approved: boolean;
};

type ConfirmActionResponse = {
  status: "resolved";
};

type StreamOptions = {
  signal?: AbortSignal;
  onEvent: (event: SseEvent) => void;
};

async function throwIfNotOk(response: Response): Promise<void> {
  if (response.ok) return;

  let payload: ApiErrorPayload | null = null;
  try {
    payload = (await response.json()) as ApiErrorPayload;
  } catch {
    payload = null;
  }

  throw buildError(response.status, payload);
}

export function chatOnce(notebookId: string, request: ChatRequest) {
  return apiFetch<ChatResponse>(`/chat/notebooks/${notebookId}/chat`, {
    method: "POST",
    body: request,
  });
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

  await throwIfNotOk(response);

  if (!response.body) {
    throw new ApiError(500, "E_STREAM_BODY", "Stream body is empty");
  }

  await parseSseStream(response.body, {
    signal: options.signal,
    onEvent: options.onEvent,
  });
}

export function cancelChatStream(messageId: number) {
  return apiFetch<void>(`/chat/stream/${messageId}/cancel`, {
    method: "POST",
  });
}

export function confirmChatAction(sessionId: string, request: ConfirmActionRequest) {
  return apiFetch<ConfirmActionResponse>(`/chat/${sessionId}/confirm`, {
    method: "POST",
    body: request,
  });
}
