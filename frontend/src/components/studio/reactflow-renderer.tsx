"use client";

import {
  Background,
  Controls,
  Handle,
  type NodeTypes,
  Position,
  ReactFlow,
  type ReactFlowInstance,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import clsx from "clsx";
import { useCallback, useEffect, useMemo, useRef } from "react";

import type { Diagram } from "@/lib/api/types";
import { useUpdateDiagramPositions } from "@/lib/hooks/use-diagrams";
import {
  buildReactFlowElements,
  type DiagramNodeData,
  type DiagramPosition,
} from "@/lib/diagram/reactflow-layout";

type ReactFlowRendererProps = {
  diagram: Diagram;
  content: string;
};

const POSITION_SAVE_DELAY_MS = 2_000;
const ROOT_FOCUS_X_OFFSET = 164;
const INITIAL_DETAIL_ZOOM = 0.5;
type DiagramFlowNode = Node<DiagramNodeData, "diagramNode">;
type DiagramFlowEdge = Edge;

function DiagramNodeCard({ data, selected }: NodeProps<DiagramFlowNode>) {
  const isMindMap = data.diagramType === "mindmap";
  const isRoot = data.kind === "root";
  const background = isRoot
    ? "linear-gradient(135deg, #e8f6df 0%, #d8efcb 100%)"
    : isMindMap
      ? "linear-gradient(180deg, rgba(255,255,255,0.99) 0%, rgba(248,251,247,0.99) 100%)"
      : "linear-gradient(180deg, hsl(var(--card)) 0%, hsl(var(--secondary)) 100%)";
  const color = isRoot ? "#173b2a" : "hsl(var(--foreground))";
  const borderColor = isRoot ? "rgba(122, 179, 106, 0.45)" : "hsl(var(--border))";
  const shadow = selected
    ? "0 20px 44px rgba(122, 179, 106, 0.2)"
    : isRoot
      ? "0 18px 34px rgba(92, 132, 78, 0.18)"
      : "0 12px 26px rgba(60, 84, 52, 0.1)";

  return (
    <div
      className={clsx("select-none", isMindMap ? "cursor-grab active:cursor-grabbing" : "")}
      data-testid={isRoot ? "diagram-node-root" : undefined}
      style={{
        minWidth: isRoot ? 224 : 188,
        maxWidth: isRoot ? 272 : 236,
        borderRadius: isRoot ? 26 : 18,
        border: `1px solid ${borderColor}`,
        background,
        color,
        boxShadow: shadow,
        padding: isRoot ? "18px 24px" : "14px 18px 14px 22px",
        position: "relative",
      }}
    >
      {!isRoot ? (
        <span
          aria-hidden="true"
          style={{
            position: "absolute",
            left: 10,
            top: 10,
            bottom: 10,
            width: 4,
            borderRadius: 999,
            background: data.accentColor,
            opacity: 0.92,
          }}
        />
      ) : null}
      <Handle type="target" position={Position.Left} style={{ opacity: 0, pointerEvents: "none" }} />
      <div
        data-testid={isRoot ? "diagram-node-label-root" : undefined}
        style={{
          fontSize: isRoot ? 18 : 15,
          fontWeight: isRoot ? 700 : data.kind === "branch" ? 600 : 500,
          letterSpacing: isRoot ? "0.01em" : "normal",
          lineHeight: 1.5,
          textAlign: isMindMap ? "left" : "center",
        }}
      >
        {data.label}
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0, pointerEvents: "none" }} />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  diagramNode: DiagramNodeCard,
};

function toPositionPayload(nodes: DiagramFlowNode[]): Record<string, DiagramPosition> {
  return Object.fromEntries(
    nodes.map((node) => [
      node.id,
      {
        x: node.position.x,
        y: node.position.y,
      },
    ])
  );
}

export function ReactFlowRenderer({ diagram, content }: ReactFlowRendererProps) {
  const updatePositionsMutation = useUpdateDiagramPositions(diagram.notebook_id);
  const saveTimerRef = useRef<number | null>(null);
  const reactFlowRef = useRef<ReactFlowInstance<DiagramFlowNode, DiagramFlowEdge> | null>(null);

  const initialElements = useMemo(
    () => buildReactFlowElements(content, diagram.node_positions, diagram.diagram_type),
    [content, diagram.diagram_type, diagram.node_positions]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState<DiagramFlowNode>(initialElements?.nodes ?? []);
  const [edges, setEdges, onEdgesChange] = useEdgesState<DiagramFlowEdge>(initialElements?.edges ?? []);

  useEffect(() => {
    setNodes(initialElements?.nodes ?? []);
    setEdges(initialElements?.edges ?? []);
  }, [initialElements, setEdges, setNodes]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current !== null) {
        window.clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  const focusRootRegion = useCallback(() => {
    if (!reactFlowRef.current || !initialElements?.nodes.length) {
      return;
    }

    const rootNode =
      initialElements.nodes.find((node) => node.data.kind === "root") ?? initialElements.nodes[0];
    const focusX = rootNode.position.x + ROOT_FOCUS_X_OFFSET;
    const focusY = rootNode.position.y + (rootNode.data.kind === "root" ? 40 : 32);

    reactFlowRef.current.setCenter(focusX, focusY, {
      zoom: INITIAL_DETAIL_ZOOM,
      duration: 0,
    });
  }, [initialElements]);

  useEffect(() => {
    focusRootRegion();
  }, [focusRootRegion]);

  const schedulePositionSave = useCallback(
    (nextNodes: DiagramFlowNode[]) => {
      if (saveTimerRef.current !== null) {
        window.clearTimeout(saveTimerRef.current);
      }

      saveTimerRef.current = window.setTimeout(() => {
        updatePositionsMutation.mutate({
          diagramId: diagram.diagram_id,
          positions: toPositionPayload(nextNodes),
        });
      }, POSITION_SAVE_DELAY_MS);
    },
    [diagram.diagram_id, updatePositionsMutation]
  );

  const handleNodeDragStop = useCallback(
    (_event: unknown, draggedNode: { id: string; position: DiagramPosition }) => {
      setNodes((currentNodes) => {
        const nextNodes = currentNodes.map((node) =>
          node.id === draggedNode.id
            ? {
                ...node,
                position: draggedNode.position,
              }
            : node
        );
        schedulePositionSave(nextNodes);
        return nextNodes;
      });
    },
    [schedulePositionSave, setNodes]
  );

  if (!initialElements) {
    return (
      <pre
        style={{
          margin: 0,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          fontFamily: "\"Cascadia Code\", monospace",
          fontSize: 12,
          lineHeight: 1.5,
        }}
      >
        {content}
      </pre>
    );
  }

  return (
    <div
      data-testid="diagram-viewer-reactflow"
      style={{
        height: "100%",
        minHeight: 440,
        borderRadius: 20,
        border: "1px solid hsl(var(--border))",
        background:
          "radial-gradient(circle at top left, rgba(122, 179, 106, 0.14), transparent 34%), linear-gradient(180deg, hsl(var(--background)) 0%, rgba(245, 249, 243, 0.98) 100%)",
        overflow: "hidden",
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={handleNodeDragStop}
        onInit={(instance) => {
          reactFlowRef.current = instance;
          focusRootRegion();
        }}
        nodeTypes={nodeTypes}
        proOptions={{ hideAttribution: true }}
        minZoom={0.28}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable={false}
        selectNodesOnDrag={false}
        zoomOnDoubleClick={false}
      >
        <Background gap={20} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
