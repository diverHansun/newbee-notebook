import { apiFetch } from "@/lib/api/client";
import { fetchAllPaginated, MAX_API_PAGE_LIMIT } from "@/lib/api/pagination";
import { ApiListResponse, DocumentItem, DocumentStatus, LibraryInfo } from "@/lib/api/types";

export function getLibraryInfo() {
  return apiFetch<LibraryInfo>("/library");
}

export function listLibraryDocuments(params?: {
  limit?: number;
  offset?: number;
  status?: DocumentStatus;
  fetchAll?: boolean;
}): Promise<ApiListResponse<DocumentItem>> {
  if (params?.fetchAll) {
    return fetchAllPaginated<DocumentItem>(
      ({ limit, offset }) => listLibraryDocuments({ ...params, limit, offset, fetchAll: false }),
      {
        limit: params.limit ?? MAX_API_PAGE_LIMIT,
        offset: params.offset ?? 0,
      }
    );
  }

  const search = new URLSearchParams();
  search.set("limit", String(Math.min(params?.limit ?? 20, MAX_API_PAGE_LIMIT)));
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
