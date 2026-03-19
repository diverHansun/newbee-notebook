import { apiFetch } from "@/lib/api/client";
import {
  Diagram,
  DiagramListResponse,
  DiagramUpdatePositionsInput,
} from "@/lib/api/types";

export function listDiagrams(
  notebookId: string,
  params?: { document_id?: string }
) {
  const search = new URLSearchParams({ notebook_id: notebookId });
  if (params?.document_id) {
    search.set("document_id", params.document_id);
  }
  return apiFetch<DiagramListResponse>(`/diagrams?${search.toString()}`);
}

export function getDiagram(diagramId: string) {
  return apiFetch<Diagram>(`/diagrams/${diagramId}`);
}

export function getDiagramContent(diagramId: string) {
  return apiFetch<string>(`/diagrams/${diagramId}/content`);
}

export function updateDiagramPositions(
  diagramId: string,
  input: DiagramUpdatePositionsInput
) {
  return apiFetch<Diagram>(`/diagrams/${diagramId}/positions`, {
    method: "PATCH",
    body: input,
  });
}

export function deleteDiagram(diagramId: string) {
  return apiFetch<void>(`/diagrams/${diagramId}`, {
    method: "DELETE",
  });
}
