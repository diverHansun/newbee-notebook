import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Diagram } from "@/lib/api/types";

const mocks = vi.hoisted(() => ({
  mutate: vi.fn(),
  latestReactFlowProps: null as null | Record<string, unknown>,
  setCenter: vi.fn(),
}));

vi.mock("@/lib/hooks/use-diagrams", () => ({
  useUpdateDiagramPositions: () => ({
    mutate: mocks.mutate,
  }),
}));

vi.mock("@xyflow/react", async () => {
  const React = await import("react");

  return {
    Background: () => <div data-testid="diagram-background" />,
    Controls: () => <div data-testid="diagram-controls" />,
    Handle: () => null,
    Position: {
      Left: "left",
      Right: "right",
    },
    ReactFlow: (props: {
      nodes: Array<{ id: string; data?: { label?: string } }>;
      nodeTypes?: Record<string, ComponentType<{ data: unknown; selected: boolean }>>;
      nodesDraggable?: boolean;
      minZoom?: number;
      onInit?: (instance: { setCenter: typeof mocks.setCenter }) => void;
      onNodeDragStop?: (
        event: unknown,
        node: { id: string; position: { x: number; y: number } }
      ) => void;
    }) => {
      mocks.latestReactFlowProps = props as unknown as Record<string, unknown>;
      props.onInit?.({ setCenter: mocks.setCenter });
      return (
        <div data-testid="diagram-reactflow">
          <button
            type="button"
            onClick={() =>
              props.onNodeDragStop?.({}, { id: "root", position: { x: 320, y: 180 } })
            }
          >
            drag-root
          </button>
          {props.nodes.map((node) => {
            const NodeComponent = props.nodeTypes?.diagramNode;
            if (NodeComponent) {
              return <NodeComponent key={node.id} data={node.data} selected={false} />;
            }
            return <span key={node.id}>{node.data?.label ?? node.id}</span>;
          })}
        </div>
      );
    },
    useNodesState: (initialNodes: unknown[]) => {
      const [nodes, setNodes] = React.useState(initialNodes);
      return [nodes, setNodes, vi.fn()] as const;
    },
    useEdgesState: (initialEdges: unknown[]) => {
      const [edges, setEdges] = React.useState(initialEdges);
      return [edges, setEdges, vi.fn()] as const;
    },
  };
});

import { ReactFlowRenderer } from "@/components/studio/reactflow-renderer";

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

describe("ReactFlowRenderer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mocks.mutate.mockReset();
    mocks.latestReactFlowProps = null;
    mocks.setCenter.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("enables node dragging and persists node positions after drag stop", async () => {
    render(
      <ReactFlowRenderer
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

    expect(mocks.latestReactFlowProps?.nodesDraggable).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "drag-root" }));

    expect(mocks.mutate).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1_999);
    expect(mocks.mutate).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(mocks.mutate).toHaveBeenCalledTimes(1);
    expect(mocks.mutate).toHaveBeenCalledWith({
      diagramId: "diagram-1",
      positions: expect.objectContaining({
        root: { x: 320, y: 180 },
      }),
    });
  });

  it("renders larger XMind-like root styling for mind maps", () => {
    render(
      <ReactFlowRenderer
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

    expect(screen.getByTestId("diagram-node-root")).toBeInTheDocument();
    expect(screen.getByTestId("diagram-node-root").getAttribute("style")).toContain("rgb(232, 246, 223)");
    expect(screen.getByTestId("diagram-node-root").getAttribute("style")).toContain("min-width: 224px");
    expect(screen.getByTestId("diagram-node-label-root").getAttribute("style")).toContain("font-size: 18px");
    expect(mocks.latestReactFlowProps?.minZoom).toBe(0.28);
    expect(mocks.setCenter).toHaveBeenCalledWith(
      expect.any(Number),
      expect.any(Number),
      expect.objectContaining({ zoom: 0.5, duration: 0 })
    );
  });
});
