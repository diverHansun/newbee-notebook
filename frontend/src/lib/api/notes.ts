import { apiFetch } from "@/lib/api/client";
import { MAX_API_PAGE_LIMIT } from "@/lib/api/pagination";
import {
  Note,
  NoteCreateInput,
  NoteListResponse,
  NoteUpdateInput,
} from "@/lib/api/types";

async function fetchAllNotesPages(
  fetchPage: (params: { limit: number; offset: number }) => Promise<NoteListResponse>,
  request: { limit?: number; offset?: number } = {}
): Promise<NoteListResponse> {
  const limit = Math.min(request.limit ?? MAX_API_PAGE_LIMIT, MAX_API_PAGE_LIMIT);
  const startOffset = request.offset ?? 0;
  const notes = [] as NoteListResponse["notes"];
  let offset = startOffset;
  let total = 0;

  while (true) {
    const page = await fetchPage({ limit, offset });
    notes.push(...page.notes);
    total = page.total;

    if (!page.pagination.has_next || page.notes.length === 0) {
      break;
    }

    offset += page.notes.length;
    if (offset >= total) {
      break;
    }
  }

  return {
    notes,
    total,
    pagination: {
      total,
      limit: notes.length,
      offset: startOffset,
      has_next: false,
      has_prev: startOffset > 0,
    },
  };
}

export function listAllNotes(params?: {
  document_id?: string;
  sort_by?: "created_at" | "updated_at";
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
  fetchAll?: boolean;
}): Promise<NoteListResponse> {
  if (params?.fetchAll) {
    return fetchAllNotesPages(
      ({ limit, offset }) => listAllNotes({ ...params, limit, offset, fetchAll: false }),
      {
        limit: params.limit ?? MAX_API_PAGE_LIMIT,
        offset: params.offset ?? 0,
      }
    );
  }

  const search = new URLSearchParams();
  if (params?.document_id) search.set("document_id", params.document_id);
  if (params?.sort_by) search.set("sort_by", params.sort_by);
  if (params?.order) search.set("order", params.order);
  search.set("limit", String(Math.min(params?.limit ?? 20, MAX_API_PAGE_LIMIT)));
  search.set("offset", String(params?.offset ?? 0));

  const query = search.toString();
  return apiFetch<NoteListResponse>(query ? `/notes?${query}` : "/notes");
}

export function listNotes(
  notebookId: string,
  params?: { document_id?: string; limit?: number; offset?: number; fetchAll?: boolean }
): Promise<NoteListResponse> {
  if (params?.fetchAll) {
    return fetchAllNotesPages(
      ({ limit, offset }) => listNotes(notebookId, { ...params, limit, offset, fetchAll: false }),
      {
        limit: params.limit ?? MAX_API_PAGE_LIMIT,
        offset: params.offset ?? 0,
      }
    );
  }

  const search = new URLSearchParams();
  if (params?.document_id) {
    search.set("document_id", params.document_id);
  }
  search.set("limit", String(Math.min(params?.limit ?? 20, MAX_API_PAGE_LIMIT)));
  search.set("offset", String(params?.offset ?? 0));

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
