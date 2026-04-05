import { ApiListResponse } from "@/lib/api/types";

export const MAX_API_PAGE_LIMIT = 100;

type PageRequest = {
  limit: number;
  offset: number;
};

export async function fetchAllPaginated<T>(
  fetchPage: (request: PageRequest) => Promise<ApiListResponse<T>>,
  request: Partial<PageRequest> = {}
): Promise<ApiListResponse<T>> {
  const limit = Math.min(request.limit ?? MAX_API_PAGE_LIMIT, MAX_API_PAGE_LIMIT);
  const startOffset = request.offset ?? 0;
  const data: T[] = [];
  let offset = startOffset;
  let total = 0;

  while (true) {
    const page = await fetchPage({ limit, offset });
    data.push(...page.data);
    total = page.pagination.total;

    if (!page.pagination.has_next || page.data.length === 0) {
      break;
    }

    offset += page.data.length;
    if (offset >= total) {
      break;
    }
  }

  return {
    data,
    pagination: {
      total,
      limit: data.length,
      offset: startOffset,
      has_next: false,
      has_prev: startOffset > 0,
    },
  };
}