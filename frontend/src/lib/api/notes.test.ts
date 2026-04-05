import { beforeEach, describe, expect, it, vi } from "vitest";

import { listAllNotes, listNotes } from "@/lib/api/notes";

const fetchMock = vi.fn();

function createJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("notes api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("aggregates all note pages when fetchAll is enabled", async () => {
    fetchMock
      .mockResolvedValueOnce(
        createJsonResponse({
          notes: [{ note_id: "note-1", notebook_id: "nb-1", title: "A", document_ids: [], mark_count: 0, created_at: "2026-03-27T00:00:00Z", updated_at: "2026-03-27T00:00:00Z" }],
          total: 2,
          pagination: { total: 2, limit: 1, offset: 0, has_next: true, has_prev: false },
        })
      )
      .mockResolvedValueOnce(
        createJsonResponse({
          notes: [{ note_id: "note-2", notebook_id: "nb-1", title: "B", document_ids: [], mark_count: 0, created_at: "2026-03-27T00:00:00Z", updated_at: "2026-03-27T00:00:00Z" }],
          total: 2,
          pagination: { total: 2, limit: 1, offset: 1, has_next: false, has_prev: true },
        })
      );

    const result = await listAllNotes({ fetchAll: true, limit: 1 });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/notes?limit=1&offset=0", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/notes?limit=1&offset=1", expect.any(Object));
    expect(result.notes.map((item) => item.note_id)).toEqual(["note-1", "note-2"]);
    expect(result.total).toBe(2);
    expect(result.pagination.has_next).toBe(false);
  });

  it("clamps notebook note requests to the backend page max", async () => {
    fetchMock.mockResolvedValue(
      createJsonResponse({
        notes: [],
        total: 0,
        pagination: { total: 0, limit: 100, offset: 0, has_next: false, has_prev: false },
      })
    );

    await listNotes("nb-1", { limit: 500, offset: 0 });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/notebooks/nb-1/notes?limit=100&offset=0",
      expect.any(Object)
    );
  });
});