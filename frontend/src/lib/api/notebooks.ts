import { apiFetch, buildError } from "@/lib/api/client";
import { fetchAllPaginated, MAX_API_PAGE_LIMIT } from "@/lib/api/pagination";
import { ApiListResponse, Notebook } from "@/lib/api/types";

export function listNotebooks(limit = 20, offset = 0) {
  return apiFetch<ApiListResponse<Notebook>>(`/notebooks?limit=${limit}&offset=${offset}`);
}

export function listAllNotebooks(params?: { limit?: number; offset?: number }) {
  return fetchAllPaginated<Notebook>(
    ({ limit, offset }) => listNotebooks(limit, offset),
    {
      limit: Math.min(params?.limit ?? MAX_API_PAGE_LIMIT, MAX_API_PAGE_LIMIT),
      offset: params?.offset ?? 0,
    }
  );
}

export type ExportNotebookResult = {
  blob: Blob;
  filename: string | null;
};

function parseDownloadFilename(contentDisposition: string | null): string | null {
  if (!contentDisposition) return null;

  const utf8Match = contentDisposition.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const asciiMatch = contentDisposition.match(/filename\s*=\s*"?([^\";]+)"?/i);
  if (asciiMatch?.[1]) {
    return asciiMatch[1].trim();
  }

  return null;
}

export async function exportNotebook(
  notebookId: string,
  types?: string[]
): Promise<ExportNotebookResult> {
  const params = new URLSearchParams();
  if (types && types.length > 0) {
    params.set("types", types.join(","));
  }
  const query = params.toString();
  const path = query
    ? `/api/v1/notebooks/${notebookId}/export?${query}`
    : `/api/v1/notebooks/${notebookId}/export`;

  const response = await fetch(path);
  if (!response.ok) {
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw buildError(response.status, payload);
  }

  return {
    blob: await response.blob(),
    filename: parseDownloadFilename(response.headers.get("content-disposition")),
  };
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

export function updateNotebook(notebookId: string, input: { title?: string; description?: string | null }) {
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
