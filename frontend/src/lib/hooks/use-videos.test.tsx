import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageContext } from "@/lib/i18n/language-context";
import { createQueryClient } from "@/test/test-utils";

const apiMocks = vi.hoisted(() => ({
  associateVideoSummary: vi.fn(),
  deleteVideoSummary: vi.fn(),
  disassociateVideoSummary: vi.fn(),
  getVideoSummary: vi.fn(),
  listAllVideoSummaries: vi.fn(),
  listVideoSummaries: vi.fn(),
}));

vi.mock("@/lib/api/videos", () => ({
  associateVideoSummary: (...args: unknown[]) => apiMocks.associateVideoSummary(...args),
  deleteVideoSummary: (...args: unknown[]) => apiMocks.deleteVideoSummary(...args),
  disassociateVideoSummary: (...args: unknown[]) => apiMocks.disassociateVideoSummary(...args),
  getVideoSummary: (...args: unknown[]) => apiMocks.getVideoSummary(...args),
  listAllVideoSummaries: (...args: unknown[]) => apiMocks.listAllVideoSummaries(...args),
  listVideoSummaries: (...args: unknown[]) => apiMocks.listVideoSummaries(...args),
}));

import {
  ALL_VIDEO_SUMMARIES_QUERY_KEY,
  VIDEO_SUMMARIES_QUERY_KEY,
  VIDEO_SUMMARY_QUERY_KEY,
  useAllVideoSummaries,
  useAssociateVideoSummary,
  useDeleteVideoSummary,
  useDisassociateVideoSummary,
  useVideoSummaries,
  useVideoSummary,
} from "@/lib/hooks/use-videos";

function createWrapper() {
  const queryClient = createQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>
        {children}
      </LanguageContext.Provider>
    </QueryClientProvider>
  );
  return { queryClient, wrapper };
}

describe("use-videos", () => {
  beforeEach(() => {
    Object.values(apiMocks).forEach((mockFn) => mockFn.mockReset());
  });

  it("loads the global video summary list", async () => {
    apiMocks.listAllVideoSummaries.mockResolvedValue({
      summaries: [
        {
          summary_id: "sum-1",
          notebook_id: null,
          platform: "bilibili",
          video_id: "BV1",
          title: "Video 1",
          cover_url: null,
          duration_seconds: 120,
          uploader_name: "UP",
          status: "completed",
          created_at: "2026-03-27T00:00:00Z",
          updated_at: "2026-03-27T00:00:00Z",
        },
      ],
      total: 1,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useAllVideoSummaries(), { wrapper });

    await waitFor(() => {
      expect(result.current.data?.summaries).toHaveLength(1);
    });

    expect(apiMocks.listAllVideoSummaries).toHaveBeenCalledOnce();
  });

  it("loads notebook-scoped video summaries", async () => {
    apiMocks.listVideoSummaries.mockResolvedValue({ summaries: [], total: 0 });

    const { wrapper } = createWrapper();
    renderHook(() => useVideoSummaries("notebook-1"), { wrapper });

    await waitFor(() => {
      expect(apiMocks.listVideoSummaries).toHaveBeenCalledWith("notebook-1");
    });
  });

  it("loads a single video summary detail", async () => {
    apiMocks.getVideoSummary.mockResolvedValue({
      summary_id: "sum-1",
      notebook_id: null,
      platform: "bilibili",
      video_id: "BV1",
      source_url: "https://www.bilibili.com/video/BV1",
      title: "Video 1",
      cover_url: null,
      duration_seconds: 120,
      uploader_name: "UP",
      uploader_id: "uploader-1",
      summary_content: "# Summary",
      status: "completed",
      error_message: null,
      document_ids: [],
      stats: null,
      transcript_source: "subtitle",
      transcript_path: null,
      created_at: "2026-03-27T00:00:00Z",
      updated_at: "2026-03-27T00:00:00Z",
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useVideoSummary("sum-1"), { wrapper });

    await waitFor(() => {
      expect(result.current.data?.summary_id).toBe("sum-1");
    });
  });

  it("invalidates list and detail caches after deleting a summary", async () => {
    apiMocks.deleteVideoSummary.mockResolvedValue(undefined);

    const { queryClient, wrapper } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const removeSpy = vi.spyOn(queryClient, "removeQueries");
    const { result } = renderHook(() => useDeleteVideoSummary("notebook-1"), { wrapper });

    await act(async () => {
      await result.current.mutateAsync("sum-1");
    });

    expect(apiMocks.deleteVideoSummary).toHaveBeenCalledWith("sum-1");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: VIDEO_SUMMARIES_QUERY_KEY("notebook-1"),
    });
    expect(removeSpy).toHaveBeenCalledWith({ queryKey: VIDEO_SUMMARY_QUERY_KEY("sum-1") });
  });

  it("invalidates all relevant caches after association changes", async () => {
    apiMocks.associateVideoSummary.mockResolvedValue(undefined);
    apiMocks.disassociateVideoSummary.mockResolvedValue(undefined);

    const { queryClient, wrapper } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result: associateResult } = renderHook(
      () => useAssociateVideoSummary("notebook-1"),
      { wrapper }
    );
    const { result: disassociateResult } = renderHook(
      () => useDisassociateVideoSummary("notebook-1"),
      { wrapper }
    );

    await act(async () => {
      await associateResult.current.mutateAsync("sum-1");
      await disassociateResult.current.mutateAsync("sum-1");
    });

    expect(apiMocks.associateVideoSummary).toHaveBeenCalledWith("sum-1", "notebook-1");
    expect(apiMocks.disassociateVideoSummary).toHaveBeenCalledWith("sum-1");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: VIDEO_SUMMARIES_QUERY_KEY("notebook-1"),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: VIDEO_SUMMARY_QUERY_KEY("sum-1") });
  });
});
