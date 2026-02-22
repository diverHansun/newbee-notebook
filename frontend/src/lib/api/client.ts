import { ApiErrorPayload } from "@/lib/api/types";

export class ApiError extends Error {
  status: number;
  errorCode: string;
  details?: Record<string, unknown>;

  constructor(status: number, errorCode: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = errorCode;
    this.details = details;
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: BodyInit | object | null;
};

export function buildError(status: number, payload: ApiErrorPayload | null): ApiError {
  if (!payload) {
    return new ApiError(status, "E_HTTP", `HTTP ${status}`);
  }

  if (payload.error_code || payload.message) {
    return new ApiError(
      status,
      payload.error_code || "E_HTTP",
      payload.message || `HTTP ${status}`,
      payload.details
    );
  }

  if (typeof payload.detail === "string") {
    return new ApiError(status, "E_HTTP_DETAIL", payload.detail);
  }

  if (payload.detail && typeof payload.detail === "object") {
    const detailObj = payload.detail as Record<string, unknown>;
    return new ApiError(
      status,
      String(detailObj.error_code || "E_HTTP_DETAIL"),
      String(detailObj.message || `HTTP ${status}`),
      (detailObj.details as Record<string, unknown>) || undefined
    );
  }

  return new ApiError(status, "E_HTTP", `HTTP ${status}`);
}

function isBodyLike(body: unknown): body is BodyInit {
  return (
    body instanceof FormData ||
    body instanceof URLSearchParams ||
    body instanceof Blob ||
    body instanceof ReadableStream ||
    typeof body === "string" ||
    body instanceof ArrayBuffer
  );
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  let body: BodyInit | undefined;

  if (options.body == null) {
    body = undefined;
  } else if (isBodyLike(options.body)) {
    body = options.body;
  } else {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers,
    body,
  });

  if (!response.ok) {
    let payload: ApiErrorPayload | null = null;
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      payload = null;
    }
    throw buildError(response.status, payload);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return (await response.text()) as T;
}
