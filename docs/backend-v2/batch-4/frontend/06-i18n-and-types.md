# TypeScript 类型、i18n 与数据获取

## TypeScript 类型定义

```typescript
// frontend/src/types/diagram.ts

export interface Diagram {
  diagram_id: string;
  notebook_id: string;
  title: string;
  diagram_type: DiagramType;
  format: DiagramFormat;
  document_ids: string[];
  node_positions: Record<string, { x: number; y: number }> | null;
  created_at: string;
  updated_at: string;
}

export type DiagramType = "mindmap" | "flowchart" | "sequence" | "gantt";

export type DiagramFormat = "reactflow_json" | "mermaid";

// Agent 生成的 mindmap JSON 内容结构
export interface ReactFlowDiagramContent {
  nodes: ReactFlowRawNode[];
  edges: ReactFlowRawEdge[];
}

export interface ReactFlowRawNode {
  id: string;
  label: string;
}

export interface ReactFlowRawEdge {
  source: string;
  target: string;
}

// 坐标更新请求体
export interface UpdateDiagramPositionsRequest {
  positions: Record<string, { x: number; y: number }>;
}
```

## i18n 文案键值

在现有 i18n 系统（`frontend/src/lib/i18n`）中新增图表相关文案：

```typescript
// 追加到现有 uiStrings 中

studio: {
  // ... 现有键值
  diagrams: {
    cardTitle: {
      zh: "图表",
      en: "Diagrams",
    },
    cardDescription: {
      zh: "生成思维导图、流程图等可视化图表",
      en: "Generate mind maps, flowcharts, and more",
    },
    emptyState: {
      zh: "在对话框中输入 /mindmap 开始创建图表",
      en: "Type /mindmap in the chat to create a diagram",
    },
    types: {
      mindmap: { zh: "思维导图", en: "Mind Map" },
      flowchart: { zh: "流程图", en: "Flowchart" },
      sequence: { zh: "时序图", en: "Sequence Diagram" },
      gantt: { zh: "甘特图", en: "Gantt Chart" },
    },
    exportButton: { zh: "导出图片", en: "Export Image" },
    deleteButton: { zh: "删除图表", en: "Delete Diagram" },
    deleteConfirm: {
      title: { zh: "删除图表", en: "Delete Diagram" },
      message: {
        zh: "确定要删除这张图表吗？此操作不可撤销。",
        en: "Are you sure you want to delete this diagram? This cannot be undone.",
      },
    },
    unsupportedFormat: {
      zh: "不支持的图表格式",
      en: "Unsupported diagram format",
    },
    loadError: {
      zh: "图表加载失败，请稍后重试",
      en: "Failed to load diagram, please try again",
    },
    exportError: {
      zh: "导出失败，请稍后重试",
      en: "Export failed, please try again",
    },
  },
},

slashCommands: {
  // ... 现有 /note 条目
  mindmap: {
    label: { zh: "/mindmap", en: "/mindmap" },
    description: {
      zh: "生成思维导图",
      en: "Generate a mind map",
    },
  },
  flowchart: {
    label: { zh: "/flowchart", en: "/flowchart" },
    description: {
      zh: "生成流程图（即将推出）",
      en: "Generate a flowchart (coming soon)",
    },
  },
  sequence: {
    label: { zh: "/sequence", en: "/sequence" },
    description: {
      zh: "生成时序图（即将推出）",
      en: "Generate a sequence diagram (coming soon)",
    },
  },
},
```

## TanStack Query Hooks

```typescript
// frontend/src/hooks/use-diagrams.ts

/**
 * 获取 notebook 下的图表列表，可按文档 ID 过滤。
 */
export function useDiagrams(
  notebookId: string,
  documentId?: string,
) {
  return useQuery({
    queryKey: ["diagrams", notebookId, documentId ?? "all"],
    queryFn: () => fetchDiagrams(notebookId, documentId),
    staleTime: 30_000,
  });
}

/**
 * 获取单张图表元数据（含 node_positions）。
 */
export function useDiagram(diagramId: string) {
  return useQuery({
    queryKey: ["diagram", diagramId],
    queryFn: () => fetchDiagram(diagramId),
    enabled: Boolean(diagramId),
  });
}

/**
 * 获取图表内容文件（JSON 字符串或 Mermaid 语法）。
 * 内容较大，单独缓存，不与元数据耦合。
 */
export function useDiagramContent(diagramId: string) {
  return useQuery({
    queryKey: ["diagram-content", diagramId],
    queryFn: () => fetchDiagramContent(diagramId),
    enabled: Boolean(diagramId),
    staleTime: 60_000,
  });
}

/**
 * 更新节点坐标（拖拽后防抖触发）。
 */
export function useUpdateDiagramPositions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ diagramId, positions }: {
      diagramId: string;
      positions: Record<string, { x: number; y: number }>;
    }) => patchDiagramPositions(diagramId, positions),
    onSuccess: (_, { diagramId }) => {
      // 更新元数据缓存中的 node_positions，避免下次加载时重置
      queryClient.invalidateQueries({ queryKey: ["diagram", diagramId] });
    },
  });
}

/**
 * 删除图表。
 */
export function useDeleteDiagram() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (diagramId: string) => deleteDiagram(diagramId),
    onSuccess: (_, diagramId) => {
      queryClient.invalidateQueries({ queryKey: ["diagrams"] });
      queryClient.removeQueries({ queryKey: ["diagram", diagramId] });
      queryClient.removeQueries({ queryKey: ["diagram-content", diagramId] });
    },
  });
}
```

## QueryKey 失效策略

| 事件 | 失效的 QueryKey |
|------|----------------|
| Agent 创建图表（收到 SSE done 事件后） | `["diagrams", notebookId]` |
| Agent 更新图表内容（确认后） | `["diagram", diagramId]`、`["diagram-content", diagramId]` |
| 用户删除图表 | `["diagrams"]`，移除 `["diagram", id]` 和 `["diagram-content", id]` |
| 用户拖拽保存坐标 | `["diagram", diagramId]` |

Agent 操作完成后触发列表刷新的时机：监听 SSE `done` 事件，并判断本次消息是否经由图表 skill（根据 session 中的 active_skill 状态），若是则 invalidate 图表列表 QueryKey。
