import { apiFetch } from "@/lib/api/client";
import { ApiListResponse, Notebook } from "@/lib/api/types";

export function listNotebooks(limit = 20, offset = 0) {
  return apiFetch<ApiListResponse<Notebook>>(`/notebooks?limit=${limit}&offset=${offset}`);
}

export function getNotebook(notebookId: string) {
  return apiFetch<Notebook>(`/notebooks/${notebookId}`);
}

export function createNotebook(input: { title: string; description?: string }) {
  return apiFetch<Notebook>("/notebooks", {
    method: "POST",
    body: {
      title: input.title,
      description: input.description || null,
    },
  });
}

export function updateNotebook(notebookId: string, input: { title?: string; description?: string }) {
  return apiFetch<Notebook>(`/notebooks/${notebookId}`, {
    method: "PATCH",
    body: input,
  });
}

export function deleteNotebook(notebookId: string) {
  return apiFetch<void>(`/notebooks/${notebookId}`, {
    method: "DELETE",
  });
}
