"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  associateVideoSummary,
  deleteVideoSummary,
  disassociateVideoSummary,
  getVideoSummary,
  listAllVideoSummaries,
  listVideoSummaries,
} from "@/lib/api/videos";

export const ALL_VIDEO_SUMMARIES_QUERY_KEY = ["video-summaries", "all"] as const;
export const VIDEO_SUMMARIES_QUERY_KEY = (notebookId: string) =>
  ["video-summaries", notebookId] as const;
export const VIDEO_SUMMARY_QUERY_KEY = (summaryId: string) =>
  ["video-summary", summaryId] as const;

function hasProcessingItem(data: { summaries: Array<{ status: string }> } | undefined): boolean {
  return data?.summaries?.some((s) => s.status === "processing") ?? false;
}

export function useAllVideoSummaries() {
  return useQuery({
    queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY,
    queryFn: () => listAllVideoSummaries(),
    staleTime: 30_000,
    refetchInterval: (query) => {
      if (hasProcessingItem(query.state.data)) return 5_000;
      return false;
    },
  });
}

export function useVideoSummaries(notebookId: string) {
  return useQuery({
    queryKey: VIDEO_SUMMARIES_QUERY_KEY(notebookId),
    queryFn: () => listVideoSummaries(notebookId),
    enabled: Boolean(notebookId),
    staleTime: 30_000,
    refetchInterval: (query) => {
      if (hasProcessingItem(query.state.data)) return 5_000;
      return false;
    },
  });
}

export function useVideoSummary(summaryId: string | null) {
  return useQuery({
    queryKey: VIDEO_SUMMARY_QUERY_KEY(summaryId ?? ""),
    queryFn: () => getVideoSummary(summaryId!),
    enabled: Boolean(summaryId),
    refetchInterval: (query) => {
      // Poll every 3s while the summary is still processing
      if (query.state.data?.status === "processing") return 3_000;
      return false;
    },
  });
}

export function useDeleteVideoSummary(notebookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (summaryId: string) => deleteVideoSummary(summaryId),
    onSuccess: async (_, summaryId) => {
      await queryClient.invalidateQueries({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
      await queryClient.invalidateQueries({ queryKey: VIDEO_SUMMARIES_QUERY_KEY(notebookId) });
      queryClient.removeQueries({ queryKey: VIDEO_SUMMARY_QUERY_KEY(summaryId) });
    },
  });
}

async function invalidateVideoCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  notebookId: string,
  summaryId: string
) {
  await queryClient.invalidateQueries({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
  await queryClient.invalidateQueries({ queryKey: VIDEO_SUMMARIES_QUERY_KEY(notebookId) });
  await queryClient.invalidateQueries({ queryKey: VIDEO_SUMMARY_QUERY_KEY(summaryId) });
}

export function useAssociateVideoSummary(notebookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (summaryId: string) => associateVideoSummary(summaryId, notebookId),
    onSuccess: async (_, summaryId) => {
      await invalidateVideoCaches(queryClient, notebookId, summaryId);
    },
  });
}

export function useDisassociateVideoSummary(notebookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (summaryId: string) => disassociateVideoSummary(summaryId),
    onSuccess: async (_, summaryId) => {
      await invalidateVideoCaches(queryClient, notebookId, summaryId);
    },
  });
}
