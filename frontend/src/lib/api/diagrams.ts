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

export function getDiagram(notebookId: string, diagramId: string) {
  const search = new URLSearchParams({ notebook_id: notebookId });
  return apiFetch<Diagram>(`/diagrams/${diagramId}?${search.toString()}`);
}

export function getDiagramContent(notebookId: string, diagramId: string) {
  const search = new URLSearchParams({ notebook_id: notebookId });
  return apiFetch<string>(`/diagrams/${diagramId}/content?${search.toString()}`);
}

export function updateDiagramPositions(
  notebookId: string,
  diagramId: string,
  input: DiagramUpdatePositionsInput
) {
  const search = new URLSearchParams({ notebook_id: notebookId });
  return apiFetch<Diagram>(`/diagrams/${diagramId}/positions?${search.toString()}`, {
    method: "PATCH",
    body: input,
  });
}

export function deleteDiagram(notebookId: string, diagramId: string) {
  const search = new URLSearchParams({ notebook_id: notebookId });
  return apiFetch<void>(`/diagrams/${diagramId}?${search.toString()}`, {
    method: "DELETE",
  });
}
