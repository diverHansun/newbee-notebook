import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Diagram } from "@/lib/api/types";

vi.mock("@/components/studio/reactflow-renderer", () => ({
  ReactFlowRenderer: ({ diagram }: { diagram: Diagram }) => (
    <div data-testid="diagram-reactflow">{diagram.title}</div>
  ),
}));

vi.mock("@/components/studio/mermaid-renderer", () => ({
  MermaidRenderer: ({ syntax }: { syntax: string }) => (
    <div data-testid="diagram-mermaid">{syntax}</div>
  ),
}));

import { DiagramViewer } from "@/components/studio/diagram-viewer";

const baseDiagram: Diagram = {
  diagram_id: "diagram-1",
  notebook_id: "notebook-1",
  title: "Course Diagram",
  diagram_type: "mindmap",
  format: "reactflow_json",
  document_ids: ["doc-1"],
  node_positions: null,
  created_at: "2026-03-20T00:00:00Z",
  updated_at: "2026-03-20T00:00:00Z",
};

describe("DiagramViewer", () => {
  it("renders reactflow_json content with the React Flow canvas", () => {
    render(
      <DiagramViewer
        diagram={baseDiagram}
        content={JSON.stringify({
          nodes: [
            { id: "root", label: "Root" },
            { id: "child", label: "Child" },
          ],
          edges: [{ source: "root", target: "child" }],
        })}
      />
    );

    expect(screen.getByTestId("diagram-reactflow")).toBeInTheDocument();
    expect(screen.getByText("Course Diagram")).toBeInTheDocument();
  });

  it("renders mermaid content with the Mermaid renderer", () => {
    render(
      <DiagramViewer
        diagram={{
          ...baseDiagram,
          diagram_id: "diagram-2",
          format: "mermaid",
        }}
        content={"graph TD\nA[Notebook] --> B[Diagram]"}
      />
    );

    expect(screen.getByTestId("diagram-mermaid")).toBeInTheDocument();
    expect(screen.getByTestId("diagram-mermaid")).toHaveTextContent(/graph TD/);
    expect(screen.getByTestId("diagram-mermaid")).toHaveTextContent(/Notebook/);
  });
});
