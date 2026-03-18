# ReactFlowRenderer 组件

## 职责

ReactFlowRenderer 负责将后端存储的 reactflow_json 内容渲染为交互式思维导图，具体包括：

- 解析 Agent 生成的 JSON（仅含 nodes/edges，无坐标）
- 通过 dagre 自动计算节点布局坐标
- 将用户已保存的 node_positions 覆盖到 dagre 坐标上
- 响应用户拖拽，防抖保存坐标到后端
- 暴露 exportToPng() 方法供父组件调用

## 依赖

```
@xyflow/react       React Flow 核心
@dagrejs/dagre      自动树形布局
html2canvas         PNG 导出（见 05-export.md）
```

## 数据流

```
后端 content（JSON 字符串）
  → JSON.parse() → { nodes: RawNode[], edges: RawEdge[] }
  → applyDagreLayout()
      → dagre 图实例计算 x/y
      → 返回 ReactFlowNode[]（含 dagre 坐标）
  → mergeUserPositions(dagreNodes, diagram.node_positions)
      → 用户已保存坐标覆盖 dagre 坐标
      → 返回最终 ReactFlowNode[]
  → useNodesState(initialNodes)
  → <ReactFlow nodes={...} />
```

## 组件接口

```typescript
interface ReactFlowRendererProps {
  diagram: Diagram;      // 含 node_positions（可为 null）
  content: string;       // Agent 生成的 JSON 字符串
}

// 通过 forwardRef 暴露命令式方法，供 DiagramDetailView 调用
interface ReactFlowRendererHandle {
  exportToPng: () => Promise<void>;
}
```

## dagre 布局函数

```typescript
import dagre from "@dagrejs/dagre";
import type { Node, Edge } from "@xyflow/react";

const NODE_WIDTH = 160;
const NODE_HEIGHT = 40;

function applyDagreLayout(
  rawNodes: { id: string; label: string }[],
  rawEdges: { source: string; target: string }[],
): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 40, ranksep: 80 });
  // rankdir: "LR" 从左到右布局，适合思维导图展开方向

  rawNodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  rawEdges.forEach((e) => g.setEdge(e.source, e.target));

  dagre.layout(g);

  return rawNodes.map((n) => {
    const { x, y } = g.node(n.id);
    return {
      id: n.id,
      type: "mindmap",
      data: { label: n.label },
      position: { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 },
    };
  });
}
```

## 坐标合并函数

```typescript
function mergeUserPositions(
  dagreNodes: Node[],
  savedPositions: Record<string, { x: number; y: number }> | null,
): Node[] {
  if (!savedPositions) return dagreNodes;

  return dagreNodes.map((node) => {
    const saved = savedPositions[node.id];
    return saved ? { ...node, position: saved } : node;
  });
}
```

## ReactFlowRenderer 实现骨架

```typescript
const ReactFlowRenderer = forwardRef<ReactFlowRendererHandle, ReactFlowRendererProps>(
  function ReactFlowRenderer({ diagram, content }, ref) {
    const containerRef = useRef<HTMLDivElement>(null);

    const { initialNodes, initialEdges } = useMemo(() => {
      const parsed = JSON.parse(content) as { nodes: RawNode[]; edges: RawEdge[] };
      const dagreNodes = applyDagreLayout(parsed.nodes, parsed.edges);
      const mergedNodes = mergeUserPositions(dagreNodes, diagram.node_positions);
      const edges: Edge[] = parsed.edges.map((e) => ({
        id: `${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        type: "smoothstep",
      }));
      return { initialNodes: mergedNodes, initialEdges: edges };
    }, [content, diagram.node_positions]);

    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

    const updatePositionsMutation = useUpdateDiagramPositions();

    const debouncedSave = useDebouncedCallback((currentNodes: Node[]) => {
      const positions: Record<string, { x: number; y: number }> = {};
      currentNodes.forEach((n) => { positions[n.id] = n.position; });
      updatePositionsMutation.mutate({
        diagramId: diagram.diagram_id,
        positions,
      });
    }, 2000);

    const handleNodesChange = useCallback(
      (changes: NodeChange[]) => {
        onNodesChange(changes);
        // 仅在有位置变更时触发防抖保存
        if (changes.some((c) => c.type === "position" && c.dragging === false)) {
          setNodes((nds) => { debouncedSave(nds); return nds; });
        }
      },
      [onNodesChange, debouncedSave, setNodes],
    );

    useImperativeHandle(ref, () => ({
      exportToPng: async () => {
        if (!containerRef.current) return;
        await exportReactFlowToPng(containerRef.current, diagram.title);
      },
    }));

    return (
      <div ref={containerRef} className="w-full h-full">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
        >
          <Controls showInteractive={false} />
          <Background gap={16} size={1} />
        </ReactFlow>
      </div>
    );
  },
);

const nodeTypes = { mindmap: MindMapNode };
```

## MindMapNode 自定义节点

```typescript
function MindMapNode({ data, id }: NodeProps<{ label: string }>) {
  const isRoot = id === "root";

  return (
    <div
      className={clsx(
        "px-3 py-1.5 rounded-md border text-sm select-none",
        isRoot
          ? "bg-primary text-primary-foreground border-primary font-semibold"
          : "bg-background text-foreground border-border",
      )}
    >
      <Handle type="target" position={Position.Left} className="opacity-0" />
      {data.label}
      <Handle type="source" position={Position.Right} className="opacity-0" />
    </div>
  );
}
```

Handle 设置为透明（`opacity-0`），保留连接点结构但不显示，避免用户误操作添加连线。

## 坐标保存防抖说明

- 防抖延迟：2000 毫秒
- 仅在 `dragging === false` 时（拖拽结束）触发，避免拖拽过程中频繁调用 API
- 坐标保存为全量覆盖（所有节点坐标一次性发送），不做增量 patch
- 保存失败时仅 console.error，不阻断用户操作，下次保存时重试
