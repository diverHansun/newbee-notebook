import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Diagram } from "@/lib/api/types";

const { mermaidRender, mermaidInitialize } = vi.hoisted(() => ({
  mermaidRender: vi.fn(async () => ({ svg: "<svg><text>Mermaid Diagram</text></svg>" })),
  mermaidInitialize: vi.fn(),
}));

vi.mock("mermaid", () => ({
  default: {
    initialize: mermaidInitialize,
    render: mermaidRender,
  },
}));

vi.mock("@xyflow/react", () => ({
  Background: () => <div data-testid="diagram-background" />,
  Controls: () => <div data-testid="diagram-controls" />,
  ReactFlow: ({ nodes }: { nodes: Array<{ id: string; data?: { label?: string } }> }) => (
    <div data-testid="diagram-reactflow">
      {nodes.map((node) => (
        <span key={node.id}>{node.data?.label ?? node.id}</span>
      ))}
    </div>
  ),
  Position: {
    Left: "left",
    Right: "right",
  },
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
    expect(screen.getByText("Root")).toBeInTheDocument();
    expect(screen.getByText("Child")).toBeInTheDocument();
  });

  it("renders mermaid content into svg markup", async () => {
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

    await waitFor(() => {
      expect(mermaidRender).toHaveBeenCalled();
    });
    expect(screen.getByText("Mermaid Diagram")).toBeInTheDocument();
  });
});
