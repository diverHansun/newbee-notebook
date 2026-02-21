import { apiFetch } from "@/lib/api/client";
import { ApiListResponse, DocumentItem, DocumentStatus, LibraryInfo } from "@/lib/api/types";

export function getLibraryInfo() {
  return apiFetch<LibraryInfo>("/library");
}

export function listLibraryDocuments(params?: {
  limit?: number;
  offset?: number;
  status?: DocumentStatus;
}) {
  const search = new URLSearchParams();
  search.set("limit", String(params?.limit ?? 20));
  search.set("offset", String(params?.offset ?? 0));
  if (params?.status) search.set("status", params.status);
  return apiFetch<ApiListResponse<DocumentItem>>(`/library/documents?${search.toString()}`);
}

export function deleteLibraryDocument(documentId: string, force = false) {
  const suffix = force ? "?force=true" : "";
  return apiFetch<{ message: string; document_id: string }>(`/library/documents/${documentId}${suffix}`, {
    method: "DELETE",
  });
}
