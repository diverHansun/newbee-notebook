"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getBilibiliAuthStatus, logoutBilibili } from "@/lib/api/bilibili-auth";

export const BILIBILI_AUTH_STATUS_QUERY_KEY = ["bilibili-auth", "status"] as const;

export function useBilibiliAuthStatus() {
  return useQuery({
    queryKey: BILIBILI_AUTH_STATUS_QUERY_KEY,
    queryFn: () => getBilibiliAuthStatus(),
    staleTime: 15_000,
  });
}

export function useBilibiliLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => logoutBilibili(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: BILIBILI_AUTH_STATUS_QUERY_KEY });
    },
  });
}
