import { beforeEach, describe, expect, it, vi } from "vitest";

import { exportNotebook, listAllNotebooks } from "@/lib/api/notebooks";
import { ApiError } from "@/lib/api/client";

const fetchMock = vi.fn();

function createJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("notebooks api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("aggregates all notebooks when fetchAll helper is used", async () => {
    fetchMock
      .mockResolvedValueOnce(
        createJsonResponse({
          data: [{ notebook_id: "nb-1", title: "One", description: null, session_count: 1, document_count: 1, created_at: "2026-04-15T00:00:00Z", updated_at: "2026-04-15T00:00:00Z" }],
          pagination: { total: 2, limit: 1, offset: 0, has_next: true, has_prev: false },
        })
      )
      .mockResolvedValueOnce(
        createJsonResponse({
          data: [{ notebook_id: "nb-2", title: "Two", description: null, session_count: 1, document_count: 1, created_at: "2026-04-15T00:00:00Z", updated_at: "2026-04-15T00:00:00Z" }],
          pagination: { total: 2, limit: 1, offset: 1, has_next: false, has_prev: true },
        })
      );

    const result = await listAllNotebooks({ limit: 1 });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/notebooks?limit=1&offset=0", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/notebooks?limit=1&offset=1", expect.any(Object));
    expect(result.data.map((item) => item.notebook_id)).toEqual(["nb-1", "nb-2"]);
  });

  it("exports notebook zip and parses filename from content-disposition", async () => {
    fetchMock.mockResolvedValue(
      new Response("zip-bytes", {
        status: 200,
        headers: {
          "Content-Type": "application/zip",
          "Content-Disposition": "attachment; filename*=UTF-8''Notebook%20A-export-2026-04-15.zip",
        },
      })
    );

    const result = await exportNotebook("nb-1", ["notes", "marks"]);

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/notebooks/nb-1/export?types=notes%2Cmarks");
    expect(result.filename).toBe("Notebook A-export-2026-04-15.zip");
    expect(result.blob).toBeInstanceOf(Blob);
  });

  it("throws ApiError when notebook export fails", async () => {
    fetchMock.mockResolvedValue(
      createJsonResponse({ detail: "Notebook not found" }, 404)
    );

    await expect(exportNotebook("missing")).rejects.toBeInstanceOf(ApiError);
  });
});
