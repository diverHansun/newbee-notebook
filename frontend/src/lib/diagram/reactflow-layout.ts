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

type DiagramPosition = {
  x: number;
  y: number;
};

const NODE_X_GAP = 260;
const NODE_Y_GAP = 120;

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

function buildAutoLayout(nodes: DiagramNode[], edges: DiagramEdge[]): Map<string, DiagramPosition> {
  const order = new Map(nodes.map((node, index) => [node.id, index]));
  const children = new Map<string, string[]>();
  const incoming = new Map<string, number>();

  nodes.forEach((node) => {
    children.set(node.id, []);
    incoming.set(node.id, 0);
  });

  edges.forEach((edge) => {
    if (!children.has(edge.source) || !incoming.has(edge.target) || edge.source === edge.target) {
      return;
    }
    children.get(edge.source)?.push(edge.target);
    incoming.set(edge.target, (incoming.get(edge.target) ?? 0) + 1);
  });

  const rootIds = nodes
    .filter((node) => (incoming.get(node.id) ?? 0) === 0)
    .map((node) => node.id);

  if (rootIds.length === 0) {
    rootIds.push(nodes[0].id);
  }

  const depthById = new Map<string, number>();
  const queue: string[] = [...rootIds];

  rootIds.forEach((rootId) => depthById.set(rootId, 0));

  while (queue.length > 0) {
    const nodeId = queue.shift();
    if (!nodeId) {
      continue;
    }

    const depth = depthById.get(nodeId) ?? 0;
    const nextDepth = depth + 1;
    for (const childId of children.get(nodeId) ?? []) {
      const existingDepth = depthById.get(childId);
      if (existingDepth == null || nextDepth < existingDepth) {
        depthById.set(childId, nextDepth);
        queue.push(childId);
      }
    }
  }

  let fallbackDepth = Math.max(0, ...depthById.values());
  nodes.forEach((node) => {
    if (!depthById.has(node.id)) {
      fallbackDepth += 1;
      depthById.set(node.id, fallbackDepth);
    }
  });

  const levelMap = new Map<number, string[]>();
  nodes.forEach((node) => {
    const depth = depthById.get(node.id) ?? 0;
    const level = levelMap.get(depth) ?? [];
    level.push(node.id);
    levelMap.set(depth, level);
  });

  for (const ids of levelMap.values()) {
    ids.sort((left, right) => (order.get(left) ?? 0) - (order.get(right) ?? 0));
  }

  const positions = new Map<string, DiagramPosition>();
  Array.from(levelMap.entries())
    .sort(([left], [right]) => left - right)
    .forEach(([depth, ids]) => {
      ids.forEach((nodeId, index) => {
        positions.set(nodeId, {
          x: depth * NODE_X_GAP,
          y: index * NODE_Y_GAP,
        });
      });
    });

  return positions;
}

export function buildReactFlowElements(
  content: string,
  savedPositions?: Record<string, DiagramPosition> | null
): { nodes: Node[]; edges: Edge[] } | null {
  const diagram = parseReactFlowDiagram(content);
  if (!diagram) {
    return null;
  }

  const autoLayout = buildAutoLayout(diagram.nodes, diagram.edges);

  const nodes: Node[] = diagram.nodes.map((node) => ({
    id: node.id,
    data: { label: node.label || node.id },
    position: savedPositions?.[node.id] ?? autoLayout.get(node.id) ?? { x: 0, y: 0 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    draggable: false,
    selectable: false,
    connectable: false,
    style: {
      borderRadius: 16,
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--card))",
      color: "hsl(var(--foreground))",
      padding: 12,
      minWidth: 180,
      fontSize: 13,
      lineHeight: 1.4,
      boxShadow: "0 10px 30px rgba(15, 23, 42, 0.08)",
    },
  }));

  const edges: Edge[] = diagram.edges.map((edge, index) => ({
    id: `${edge.source}-${edge.target}-${index}`,
    source: edge.source,
    target: edge.target,
    selectable: false,
    focusable: false,
    animated: false,
    style: {
      stroke: "hsl(var(--muted-foreground))",
      strokeWidth: 1.5,
    },
  }));

  return { nodes, edges };
}
