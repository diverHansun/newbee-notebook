"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteDiagram,
  getDiagram,
  getDiagramContent,
  listDiagrams,
  updateDiagramPositions,
} from "@/lib/api/diagrams";

export const DIAGRAMS_QUERY_KEY = (
  notebookId: string,
  documentId: string | null = null
) => ["diagrams", notebookId, documentId ?? "all"] as const;

export function useDiagrams(notebookId: string, documentId?: string | null) {
  return useQuery({
    queryKey: DIAGRAMS_QUERY_KEY(notebookId, documentId ?? null),
    queryFn: () =>
      listDiagrams(notebookId, documentId ? { document_id: documentId } : undefined),
    staleTime: 30_000,
  });
}

export function useDiagram(diagramId: string | null) {
  return useQuery({
    queryKey: ["diagram", diagramId] as const,
    queryFn: () => getDiagram(diagramId!),
    enabled: Boolean(diagramId),
  });
}

export function useDiagramContent(diagramId: string | null) {
  return useQuery({
    queryKey: ["diagram-content", diagramId] as const,
    queryFn: () => getDiagramContent(diagramId!),
    enabled: Boolean(diagramId),
    staleTime: 60_000,
  });
}

export function useUpdateDiagramPositions(notebookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ diagramId, positions }: { diagramId: string; positions: Record<string, { x: number; y: number }> }) =>
      updateDiagramPositions(diagramId, { positions }),
    onSuccess: async (diagram) => {
      await queryClient.invalidateQueries({
        queryKey: DIAGRAMS_QUERY_KEY(notebookId, null),
      });
      queryClient.setQueryData(["diagram", diagram.diagram_id], diagram);
    },
  });
}

export function useDeleteDiagram(notebookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (diagramId: string) => deleteDiagram(diagramId),
    onSuccess: async (_, diagramId) => {
      await queryClient.invalidateQueries({
        queryKey: DIAGRAMS_QUERY_KEY(notebookId, null),
      });
      queryClient.removeQueries({ queryKey: ["diagram", diagramId] });
      queryClient.removeQueries({ queryKey: ["diagram-content", diagramId] });
    },
  });
}
