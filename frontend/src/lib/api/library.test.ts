import { beforeEach, describe, expect, it, vi } from "vitest";

import { listLibraryDocuments } from "@/lib/api/library";

const fetchMock = vi.fn();

function createJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function emptyPage(total = 0) {
  return {
    data: [],
    pagination: { total, limit: 100, offset: 0, has_next: false, has_prev: false },
  };
}

describe("listLibraryDocuments", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("omits content_type when contentTypes is undefined or empty", async () => {
    fetchMock.mockResolvedValueOnce(createJsonResponse(emptyPage()));
    await listLibraryDocuments();
    expect(fetchMock.mock.calls[0][0]).not.toContain("content_type");

    fetchMock.mockResolvedValueOnce(createJsonResponse(emptyPage()));
    await listLibraryDocuments({ contentTypes: [] });
    expect(fetchMock.mock.calls[1][0]).not.toContain("content_type");
  });

  it("serializes contentTypes as repeated query parameters", async () => {
    fetchMock.mockResolvedValueOnce(createJsonResponse(emptyPage()));
    await listLibraryDocuments({ contentTypes: ["pdf", "docx"] });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("content_type=pdf");
    expect(url).toContain("content_type=docx");
  });

  it("combines content_type with status filter", async () => {
    fetchMock.mockResolvedValueOnce(createJsonResponse(emptyPage()));
    await listLibraryDocuments({ status: "completed", contentTypes: ["xlsx", "csv"] });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("status=completed");
    expect(url).toContain("content_type=xlsx");
    expect(url).toContain("content_type=csv");
  });

  it("propagates contentTypes through fetchAll pagination", async () => {
    fetchMock
      .mockResolvedValueOnce(
        createJsonResponse({
          data: [{ document_id: "d1" }],
          pagination: { total: 2, limit: 1, offset: 0, has_next: true, has_prev: false },
        })
      )
      .mockResolvedValueOnce(
        createJsonResponse({
          data: [{ document_id: "d2" }],
          pagination: { total: 2, limit: 1, offset: 1, has_next: false, has_prev: true },
        })
      );

    await listLibraryDocuments({ fetchAll: true, limit: 1, contentTypes: ["pdf"] });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect((fetchMock.mock.calls[0][0] as string)).toContain("content_type=pdf");
    expect((fetchMock.mock.calls[1][0] as string)).toContain("content_type=pdf");
  });
});
