import { ApiError, buildError } from "@/lib/api/client";
import {
  ApiErrorPayload,
  BilibiliAuthStatus,
  BilibiliQrLoginEvent,
} from "@/lib/api/types";
import { parseNamedSseStream } from "@/lib/utils/sse-parser";

type StreamOptions = {
  signal?: AbortSignal;
  onEvent: (event: BilibiliQrLoginEvent) => void;
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

async function fetchJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, init);
  await throwIfNotOk(response);

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function mapQrEvent(
  eventName: string,
  payload: Record<string, unknown>
): BilibiliQrLoginEvent {
  if (eventName === "qr_generated") {
    return {
      type: "qr_generated",
      qr_url: payload.qr_url ? String(payload.qr_url) : undefined,
      image_base64: payload.image_base64 ? String(payload.image_base64) : undefined,
    };
  }

  if (eventName === "scanned" || eventName === "done" || eventName === "timeout") {
    return {
      type: eventName,
    };
  }

  if (eventName === "error") {
    return {
      type: "error",
      message: String(payload.message ?? "Unknown bilibili auth error"),
    };
  }

  throw new ApiError(500, "E_BILIBILI_AUTH_EVENT", `Unsupported bilibili auth event: ${eventName}`);
}

export function getBilibiliAuthStatus() {
  return fetchJson<BilibiliAuthStatus>("/bilibili/auth/status");
}

export function logoutBilibili() {
  return fetchJson<void>("/bilibili/auth/logout", {
    method: "POST",
  });
}

export async function streamBilibiliQrLogin(options: StreamOptions): Promise<void> {
  const response = await fetch("/api/v1/bilibili/auth/qr", {
    method: "GET",
    headers: {
      Accept: "text/event-stream",
    },
    signal: options.signal,
  });

  await throwIfNotOk(response);
  if (!response.body) {
    throw new ApiError(500, "E_STREAM_BODY", "Stream body is empty");
  }

  await parseNamedSseStream(response.body, {
    signal: options.signal,
    mapEvent: mapQrEvent,
    onEvent: options.onEvent,
  });
}
