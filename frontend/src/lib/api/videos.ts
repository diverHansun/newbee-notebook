import { ApiError, buildError } from "@/lib/api/client";
import {
  ApiErrorPayload,
  VideoInfo,
  VideoStreamEvent,
  VideoSummarizeRequest,
  VideoSummary,
  VideoSummaryListResponse,
} from "@/lib/api/types";
import { parseNamedSseStream } from "@/lib/utils/sse-parser";

type StreamOptions = {
  signal?: AbortSignal;
  onEvent: (event: VideoStreamEvent) => void;
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

function mapVideoStreamEvent(
  eventName: string,
  payload: Record<string, unknown>
): VideoStreamEvent {
  if (eventName === "done") {
    return {
      type: "done",
      summary_id: String(payload.summary_id ?? ""),
      status: String(payload.status ?? ""),
      reused: Boolean(payload.reused),
    };
  }

  if (eventName === "error") {
    return {
      type: "error",
      message: String(payload.message ?? "Unknown video stream error"),
      video_id: payload.video_id ? String(payload.video_id) : undefined,
    };
  }

  if (
    eventName === "start" ||
    eventName === "subtitle" ||
    eventName === "asr" ||
    eventName === "summarize"
  ) {
    return {
      type: eventName,
      video_id: String(payload.video_id ?? ""),
    };
  }

  throw new ApiError(500, "E_VIDEO_STREAM_EVENT", `Unsupported video stream event: ${eventName}`);
}

export function listAllVideoSummaries() {
  return fetchJson<VideoSummaryListResponse>("/videos");
}

export function listVideoSummaries(notebookId: string) {
  const search = new URLSearchParams({ notebook_id: notebookId });
  return fetchJson<VideoSummaryListResponse>(`/videos?${search.toString()}`);
}

export function getVideoSummary(summaryId: string) {
  return fetchJson<VideoSummary>(`/videos/${summaryId}`);
}

export function deleteVideoSummary(summaryId: string) {
  return fetchJson<void>(`/videos/${summaryId}`, {
    method: "DELETE",
  });
}

export function associateVideoSummary(summaryId: string, notebookId: string) {
  return fetchJson<void>(`/videos/${summaryId}/notebook`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ notebook_id: notebookId }),
  });
}

export function disassociateVideoSummary(summaryId: string) {
  return fetchJson<void>(`/videos/${summaryId}/notebook`, {
    method: "DELETE",
  });
}

export function getVideoInfo(urlOrBvid: string) {
  const search = new URLSearchParams({ url_or_bvid: urlOrBvid });
  return fetchJson<VideoInfo>(`/videos/info?${search.toString()}`);
}

export async function summarizeVideoStream(
  request: VideoSummarizeRequest,
  options: StreamOptions
): Promise<void> {
  const response = await fetch("/api/v1/videos/summarize", {
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

  await parseNamedSseStream(response.body, {
    signal: options.signal,
    mapEvent: mapVideoStreamEvent,
    onEvent: options.onEvent,
  });
}
