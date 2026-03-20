import dagre from "@dagrejs/dagre";
import { Position, type Edge, type Node } from "@xyflow/react";

type ObjectLike = Record<string, unknown>;

type DiagramNode = {
  id: string;
  label: string;
};

type DiagramEdge = {
  source: string;
  target: string;
};

type DiagramPayload = {
  nodes: DiagramNode[];
  edges: DiagramEdge[];
};

export type DiagramPosition = {
  x: number;
  y: number;
};

export type DiagramNodeKind = "root" | "branch" | "leaf";

export type DiagramNodeData = {
  label: string;
  kind: DiagramNodeKind;
  depth: number;
  accentColor: string;
  diagramType: string;
};

export type LayoutNode = DiagramNode & {
  position: DiagramPosition;
  kind: DiagramNodeKind;
  depth: number;
  accentColor: string;
};

const ROOT_NODE_WIDTH = 224;
const ROOT_NODE_HEIGHT = 78;
const CHILD_NODE_WIDTH = 188;
const CHILD_NODE_HEIGHT = 58;
const MINDMAP_ACCENTS = ["#7ab36a", "#5aa88a", "#8bbf73", "#d4a85b", "#6fa38d"];

function isObjectLike(value: unknown): value is ObjectLike {
  return Boolean(value) && typeof value === "object";
}

export function parseReactFlowDiagram(content: string): DiagramPayload | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    return null;
  }

  if (!isObjectLike(parsed)) {
    return null;
  }

  const nodes = Array.isArray(parsed.nodes)
    ? parsed.nodes
        .filter(isObjectLike)
        .map((node) => ({
          id: String(node.id ?? ""),
          label: String(node.label ?? node.id ?? ""),
        }))
        .filter((node) => node.id.length > 0)
    : [];

  const edges = Array.isArray(parsed.edges)
    ? parsed.edges
        .filter(isObjectLike)
        .map((edge) => ({
          source: String(edge.source ?? ""),
          target: String(edge.target ?? ""),
        }))
        .filter((edge) => edge.source.length > 0 && edge.target.length > 0)
    : [];

  if (nodes.length === 0) {
    return null;
  }

  return { nodes, edges };
}

function buildGraphMetadata(nodes: DiagramNode[], edges: DiagramEdge[]) {
  const childrenById = new Map<string, string[]>();
  const parentById = new Map<string, string>();
  const incomingCountById = new Map<string, number>();

  nodes.forEach((node) => {
    childrenById.set(node.id, []);
    incomingCountById.set(node.id, 0);
  });

  edges.forEach((edge) => {
    if (!childrenById.has(edge.source) || !incomingCountById.has(edge.target)) {
      return;
    }
    childrenById.get(edge.source)?.push(edge.target);
    incomingCountById.set(edge.target, (incomingCountById.get(edge.target) ?? 0) + 1);
    if (!parentById.has(edge.target)) {
      parentById.set(edge.target, edge.source);
    }
  });

  const rootId =
    nodes.find((node) => (incomingCountById.get(node.id) ?? 0) === 0)?.id ?? nodes[0].id;

  const depthById = new Map<string, number>([[rootId, 0]]);
  const queue = [rootId];
  while (queue.length > 0) {
    const currentId = queue.shift();
    if (!currentId) {
      continue;
    }
    const currentDepth = depthById.get(currentId) ?? 0;
    for (const childId of childrenById.get(currentId) ?? []) {
      if (depthById.has(childId)) {
        continue;
      }
      depthById.set(childId, currentDepth + 1);
      queue.push(childId);
    }
  }

  let fallbackDepth = Math.max(0, ...depthById.values());
  nodes.forEach((node) => {
    if (!depthById.has(node.id)) {
      fallbackDepth += 1;
      depthById.set(node.id, fallbackDepth);
    }
  });

  const rootChildren = childrenById.get(rootId) ?? [];
  const topLevelBranchIndex = new Map<string, number>();
  rootChildren.forEach((nodeId, index) => {
    topLevelBranchIndex.set(nodeId, index);
  });

  const resolveBranchIndex = (nodeId: string): number => {
    if (nodeId === rootId) {
      return 0;
    }

    let currentId = nodeId;
    while (true) {
      const parentId = parentById.get(currentId);
      if (!parentId || parentId === rootId) {
        return topLevelBranchIndex.get(currentId) ?? 0;
      }
      currentId = parentId;
    }
  };

  return {
    rootId,
    childrenById,
    depthById,
    resolveBranchIndex,
  };
}

function getNodeSize(nodeId: string, rootId: string) {
  if (nodeId === rootId) {
    return { width: ROOT_NODE_WIDTH, height: ROOT_NODE_HEIGHT };
  }
  return { width: CHILD_NODE_WIDTH, height: CHILD_NODE_HEIGHT };
}

export function applyDagreLayout(nodes: DiagramNode[], edges: DiagramEdge[]): LayoutNode[] {
  if (nodes.length === 0) {
    return [];
  }

  const graph = new dagre.graphlib.Graph();
  graph.setGraph({
    rankdir: "LR",
    nodesep: 34,
    ranksep: 88,
    marginx: 20,
    marginy: 20,
  });
  graph.setDefaultEdgeLabel(() => ({}));

  const metadata = buildGraphMetadata(nodes, edges);

  nodes.forEach((node) => {
    const size = getNodeSize(node.id, metadata.rootId);
    graph.setNode(node.id, size);
  });
  edges.forEach((edge) => {
    graph.setEdge(edge.source, edge.target);
  });

  dagre.layout(graph);

  return nodes.map((node) => {
    const size = getNodeSize(node.id, metadata.rootId);
    const position = graph.node(node.id) as { x: number; y: number };
    const children = metadata.childrenById.get(node.id) ?? [];
    const kind: DiagramNodeKind =
      node.id === metadata.rootId ? "root" : children.length > 0 ? "branch" : "leaf";
    const depth = metadata.depthById.get(node.id) ?? 0;
    const accentIndex = metadata.resolveBranchIndex(node.id) % MINDMAP_ACCENTS.length;

    return {
      ...node,
      kind,
      depth,
      accentColor: MINDMAP_ACCENTS[accentIndex],
      position: {
        x: position.x - size.width / 2,
        y: position.y - size.height / 2,
      },
    };
  });
}

type HasDiagramPosition = {
  id: string;
  position: DiagramPosition;
};

export function mergeUserPositions<T extends HasDiagramPosition>(
  dagreNodes: T[],
  savedPositions: Record<string, DiagramPosition> | null | undefined
) {
  if (!savedPositions || Object.keys(savedPositions).length === 0) {
    return dagreNodes;
  }

  return dagreNodes.map((node) => {
    const saved = savedPositions[node.id];
    return saved ? { ...node, position: saved } : node;
  });
}

export function buildReactFlowElements(
  content: string,
  savedPositions?: Record<string, DiagramPosition> | null,
  diagramType = "mindmap"
): { nodes: Node<DiagramNodeData, "diagramNode">[]; edges: Edge[] } | null {
  const diagram = parseReactFlowDiagram(content);
  if (!diagram) {
    return null;
  }

  const layoutNodes = mergeUserPositions(
    applyDagreLayout(diagram.nodes, diagram.edges),
    savedPositions
  );

  const nodes: Node<DiagramNodeData, "diagramNode">[] = layoutNodes.map((node) => ({
    id: node.id,
    type: "diagramNode",
    data: {
      label: node.label || node.id,
      kind: node.kind,
      depth: node.depth,
      accentColor: node.accentColor,
      diagramType,
    },
    position: node.position,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    draggable: true,
    selectable: false,
    connectable: false,
  }));

  const edges: Edge[] = diagram.edges.map((edge, index) => ({
    id: `${edge.source}-${edge.target}-${index}`,
    source: edge.source,
    target: edge.target,
    type: "smoothstep",
    selectable: false,
    focusable: false,
    animated: false,
    style: {
      stroke: diagramType === "mindmap" ? "rgba(148, 163, 184, 0.9)" : "rgba(100, 116, 139, 0.9)",
      strokeWidth: diagramType === "mindmap" ? 2 : 1.6,
    },
  }));

  return { nodes, edges };
}
