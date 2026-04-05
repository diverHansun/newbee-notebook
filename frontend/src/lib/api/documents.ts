import { apiFetch } from "@/lib/api/client";
import { fetchAllPaginated, MAX_API_PAGE_LIMIT } from "@/lib/api/pagination";
import {
  ApiListResponse,
  DocumentContentResponse,
  DocumentItem,
  DocumentStatus,
  NotebookDocumentItem,
  NotebookDocumentsAddResponse,
  UploadDocumentsResponse,
} from "@/lib/api/types";

export function uploadDocumentsToLibrary(files: File[]) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file, file.name));
  return apiFetch<UploadDocumentsResponse>("/documents/library/upload", {
    method: "POST",
    body: formData,
  });
}

export function getDocument(documentId: string) {
  return apiFetch<DocumentItem>(`/documents/${documentId}`);
}

export function getDocumentContent(documentId: string, format: "markdown" | "text" = "markdown") {
  return apiFetch<DocumentContentResponse>(`/documents/${documentId}/content?format=${format}`);
}

export function listDocumentsInNotebook(
  notebookId: string,
  params?: { limit?: number; offset?: number; status?: DocumentStatus; fetchAll?: boolean }
): Promise<ApiListResponse<NotebookDocumentItem>> {
  if (params?.fetchAll) {
    return fetchAllPaginated<NotebookDocumentItem>(
      ({ limit, offset }) =>
        listDocumentsInNotebook(notebookId, { ...params, limit, offset, fetchAll: false }),
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
  return apiFetch<ApiListResponse<NotebookDocumentItem>>(
    `/notebooks/${notebookId}/documents?${search.toString()}`
  );
}

export function addDocumentsToNotebook(notebookId: string, documentIds: string[]) {
  return apiFetch<NotebookDocumentsAddResponse>(`/notebooks/${notebookId}/documents`, {
    method: "POST",
    body: {
      document_ids: documentIds,
    },
  });
}

export function removeDocumentFromNotebook(notebookId: string, documentId: string) {
  return apiFetch<void>(`/notebooks/${notebookId}/documents/${documentId}`, {
    method: "DELETE",
  });
}
