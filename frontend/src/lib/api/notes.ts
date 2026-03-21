import { apiFetch } from "@/lib/api/client";
import {
  Note,
  NoteCreateInput,
  NoteListResponse,
  NoteUpdateInput,
} from "@/lib/api/types";

export function listAllNotes(params?: {
  document_id?: string;
  sort_by?: "created_at" | "updated_at";
  order?: "asc" | "desc";
}) {
  const search = new URLSearchParams();
  if (params?.document_id) search.set("document_id", params.document_id);
  if (params?.sort_by) search.set("sort_by", params.sort_by);
  if (params?.order) search.set("order", params.order);

  const query = search.toString();
  return apiFetch<NoteListResponse>(query ? `/notes?${query}` : "/notes");
}

export function listNotes(notebookId: string, params?: { document_id?: string }) {
  const search = new URLSearchParams();
  if (params?.document_id) {
    search.set("document_id", params.document_id);
  }

  const query = search.toString();
  return apiFetch<NoteListResponse>(
    query ? `/notebooks/${notebookId}/notes?${query}` : `/notebooks/${notebookId}/notes`
  );
}

export function getNote(noteId: string) {
  return apiFetch<Note>(`/notes/${noteId}`);
}

export function createNote(input: NoteCreateInput) {
  return apiFetch<Note>("/notes", {
    method: "POST",
    body: input,
  });
}

export function updateNote(noteId: string, input: NoteUpdateInput) {
  return apiFetch<Note>(`/notes/${noteId}`, {
    method: "PATCH",
    body: input,
  });
}

export function deleteNote(noteId: string) {
  return apiFetch<void>(`/notes/${noteId}`, {
    method: "DELETE",
  });
}

export function addNoteDocument(noteId: string, documentId: string) {
  return apiFetch<void>(`/notes/${noteId}/documents`, {
    method: "POST",
    body: {
      document_id: documentId,
    },
  });
}

export function removeNoteDocument(noteId: string, documentId: string) {
  return apiFetch<void>(`/notes/${noteId}/documents/${documentId}`, {
    method: "DELETE",
  });
}
