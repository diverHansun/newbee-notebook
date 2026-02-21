import { apiFetch } from "@/lib/api/client";
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
  params?: { limit?: number; offset?: number; status?: DocumentStatus }
) {
  const search = new URLSearchParams();
  search.set("limit", String(params?.limit ?? 20));
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
