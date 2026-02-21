import { apiFetch } from "@/lib/api/client";
import { ApiListResponse, Session, SessionMessage } from "@/lib/api/types";

export function createSession(
  notebookId: string,
  input?: { title?: string; include_ec_context?: boolean }
) {
  return apiFetch<Session>(`/notebooks/${notebookId}/sessions`, {
    method: "POST",
    body: input || {},
  });
}

export function listSessions(notebookId: string, limit = 20, offset = 0) {
  return apiFetch<ApiListResponse<Session>>(
    `/notebooks/${notebookId}/sessions?limit=${limit}&offset=${offset}`
  );
}

export function getLatestSession(notebookId: string) {
  return apiFetch<Session>(`/notebooks/${notebookId}/sessions/latest`);
}

export function getSession(sessionId: string) {
  return apiFetch<Session>(`/sessions/${sessionId}`);
}

export function deleteSession(sessionId: string) {
  return apiFetch<void>(`/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export function listSessionMessages(
  sessionId: string,
  params?: {
    mode?: string;
    limit?: number;
    offset?: number;
  }
) {
  const search = new URLSearchParams();
  if (params?.mode) search.set("mode", params.mode);
  search.set("limit", String(params?.limit ?? 50));
  search.set("offset", String(params?.offset ?? 0));
  return apiFetch<ApiListResponse<SessionMessage>>(
    `/sessions/${sessionId}/messages?${search.toString()}`
  );
}
