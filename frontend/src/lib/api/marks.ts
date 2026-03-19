import { apiFetch } from "@/lib/api/client";
import { Mark, MarkCreateInput, MarkListResponse } from "@/lib/api/types";

export function listMarksByDocument(documentId: string) {
  return apiFetch<MarkListResponse>(`/documents/${documentId}/marks`);
}

export function listMarksByNotebook(notebookId: string, params?: { document_id?: string }) {
  const search = new URLSearchParams();
  if (params?.document_id) {
    search.set("document_id", params.document_id);
  }

  const query = search.toString();
  return apiFetch<MarkListResponse>(
    query ? `/notebooks/${notebookId}/marks?${query}` : `/notebooks/${notebookId}/marks`
  );
}

export function createMark(documentId: string, input: MarkCreateInput) {
  return apiFetch<Mark>(`/documents/${documentId}/marks`, {
    method: "POST",
    body: input,
  });
}

export function deleteMark(markId: string) {
  return apiFetch<void>(`/marks/${markId}`, {
    method: "DELETE",
  });
}
