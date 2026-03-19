export type ReactFlowRawNode = {
  id: string;
  label: string;
};

export type ReactFlowRawEdge = {
  source: string;
  target: string;
};

export type MindMapTreeNode = {
  id: string;
  label: string;
  children: MindMapTreeNode[];
};

type ReactFlowDiagram = {
  nodes: ReactFlowRawNode[];
  edges: ReactFlowRawEdge[];
};

function isObjectLike(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}

export function parseReactFlowTree(content: string): MindMapTreeNode[] {
  const parsed: unknown = JSON.parse(content);
  if (!isObjectLike(parsed)) {
    return [];
  }

  const rawNodes = Array.isArray(parsed.nodes) ? parsed.nodes : [];
  const rawEdges = Array.isArray(parsed.edges) ? parsed.edges : [];

  const nodes: ReactFlowRawNode[] = rawNodes
    .filter(isObjectLike)
    .map((node) => ({
      id: String(node.id ?? ""),
      label: String(node.label ?? ""),
    }))
    .filter((node) => node.id.length > 0);

  const edges: ReactFlowRawEdge[] = rawEdges
    .filter(isObjectLike)
    .map((edge) => ({
      source: String(edge.source ?? ""),
      target: String(edge.target ?? ""),
    }))
    .filter((edge) => edge.source.length > 0 && edge.target.length > 0);

  const diagram: ReactFlowDiagram = { nodes, edges };
  if (diagram.nodes.length === 0) {
    return [];
  }

  const nodeMap = new Map<string, MindMapTreeNode>();
  diagram.nodes.forEach((node) => {
    nodeMap.set(node.id, {
      id: node.id,
      label: node.label || node.id,
      children: [],
    });
  });

  const incoming = new Map<string, number>();
  diagram.nodes.forEach((node) => incoming.set(node.id, 0));

  diagram.edges.forEach((edge) => {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target || source.id === target.id) return;
    source.children.push(target);
    incoming.set(target.id, (incoming.get(target.id) ?? 0) + 1);
  });

  const roots = diagram.nodes
    .map((node) => node.id)
    .filter((nodeId) => (incoming.get(nodeId) ?? 0) === 0)
    .map((nodeId) => nodeMap.get(nodeId))
    .filter((node): node is MindMapTreeNode => Boolean(node));

  if (roots.length > 0) {
    return roots;
  }

  const first = diagram.nodes[0];
  const fallback = nodeMap.get(first.id);
  return fallback ? [fallback] : [];
}
