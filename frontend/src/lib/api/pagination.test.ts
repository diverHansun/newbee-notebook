import { describe, expect, it, vi } from "vitest";

import { fetchAllPaginated, MAX_API_PAGE_LIMIT } from "@/lib/api/pagination";

describe("fetchAllPaginated", () => {
  it("aggregates multiple backend pages into one result", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({
        data: Array.from({ length: 100 }, (_, index) => ({ id: index + 1 })),
        pagination: {
          total: 150,
          limit: 100,
          offset: 0,
          has_next: true,
          has_prev: false,
        },
      })
      .mockResolvedValueOnce({
        data: Array.from({ length: 50 }, (_, index) => ({ id: index + 101 })),
        pagination: {
          total: 150,
          limit: 100,
          offset: 100,
          has_next: false,
          has_prev: true,
        },
      });

    const result = await fetchAllPaginated(fetchPage);

    expect(fetchPage).toHaveBeenNthCalledWith(1, { limit: MAX_API_PAGE_LIMIT, offset: 0 });
    expect(fetchPage).toHaveBeenNthCalledWith(2, { limit: MAX_API_PAGE_LIMIT, offset: 100 });
    expect(result.data).toHaveLength(150);
    expect(result.pagination.total).toBe(150);
    expect(result.pagination.limit).toBe(150);
    expect(result.pagination.has_next).toBe(false);
    expect(result.pagination.has_prev).toBe(false);
  });

  it("clamps requested page size to the backend max", async () => {
    const fetchPage = vi.fn().mockResolvedValue({
      data: [],
      pagination: {
        total: 0,
        limit: MAX_API_PAGE_LIMIT,
        offset: 40,
        has_next: false,
        has_prev: true,
      },
    });

    await fetchAllPaginated(fetchPage, { limit: 250, offset: 40 });

    expect(fetchPage).toHaveBeenCalledWith({ limit: MAX_API_PAGE_LIMIT, offset: 40 });
  });
});