# Studio 图表卡片与导航结构

## 导航层级

```
StudioHome（卡片网格，2 列）
  ├── [Notes & Marks] 卡片   ← batch-3
  ├── [图表] 卡片             ← batch-4（本文档）
  └── [...]  卡片             ← 未来（Coming Soon）

点击 [图表] 卡片
  → DiagramListView（图表列表）
      └── 点击某张图
            → DiagramDetailView（图表详情 + 渲染）
```

Studio 面板的导航状态由 Zustand store 的 `studioView` 字段管理，新增 `"diagrams"` 和 `"diagram-detail"` 两个视图值。

## 组件文件结构

```
frontend/src/components/studio/
├── studio-home.tsx               # 卡片网格（新增图表卡片）
├── studio-panel.tsx              # 面板容器，根据 studioView 渲染对应视图
├── notes/                        # batch-3
└── diagrams/
    ├── diagram-list-view.tsx
    ├── diagram-detail-view.tsx
    ├── diagram-viewer.tsx        # 格式分发：reactflow vs mermaid
    ├── reactflow-renderer.tsx    # React Flow 渲染器（batch-4 实现）
    └── mermaid-renderer.tsx      # Mermaid 渲染器（骨架，batch-N 实现）
```

## StudioHome 卡片网格

```tsx
// studio-home.tsx 新增图表卡片（与 Notes & Marks 卡片并列）
<FeatureCard
  title={t(uiStrings.studio.diagrams.cardTitle)}
  description={t(uiStrings.studio.diagrams.cardDescription)}
  icon={<DiagramIcon className="w-6 h-6" />}
  available={true}
  onClick={() => setStudioView("diagrams")}
/>
```

FeatureCard 组件由 batch-3 定义，available=false 时显示"即将推出"遮罩。

## DiagramListView

### 布局结构

```
┌─── 图表 ────────────────────────────┐
│ [← Studio]                          │
│ [Filter: 全部文档 v]                 │
├─────────────────────────────────────┤
│ ┌─────────────────────────────────┐ │
│ │ 大模型基础知识导图               │ │
│ │ 思维导图  2 个文档  3 天前       │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ Transformer 架构导图             │ │
│ │ 思维导图  1 个文档  昨天         │ │
│ └─────────────────────────────────┘ │
│                                     │
│  想创建图表？在对话框输入 /diagram   │
└─────────────────────────────────────┘
```

### 行为说明

- 列表项点击 → `setStudioView("diagram-detail")` + `setActiveDiagramId(id)`
- 过滤器（文档下拉）：选择某文档后，列表仅展示关联该文档的图表；选择"全部文档"时展示 notebook 下所有图表
- 列表为空时：展示空状态提示，引导用户通过 `/diagram` 命令创建
- 列表项右侧有删除按钮（trash icon），点击弹出确认对话框，确认后调用 DELETE API

### 列表项结构

```tsx
interface DiagramListItem {
  diagram_id: string;
  title: string;
  diagram_type: string;    // "mindmap" → 显示为"思维导图"
  document_ids: string[];
  created_at: string;
  updated_at: string;
}
```

图表类型 badge 文案通过 i18n 映射：`diagram_type → t(uiStrings.studio.diagrams.types[diagram_type])`

## DiagramDetailView

### 布局结构

```
┌─── 大模型基础知识导图 ─────────────────────┐
│ [← 图表列表]         [导出图片] [删除]      │
├───────────────────────────────────────────┤
│                                           │
│           < DiagramViewer />             │
│         （React Flow 画布）               │
│                                           │
│  [+]  [-]  [适应窗口]   （右下角控件）    │
└───────────────────────────────────────────┘
```

### 行为说明

- 返回按钮 → `setStudioView("diagrams")`，清除 `activeDiagramId`
- 导出图片 → 调用 ReactFlowRenderer 暴露的 `exportToPng()` 方法
- 删除按钮 → 弹出确认对话框（前端 UI 确认，非 Agent 确认机制），确认后调用 DELETE API，跳转回列表视图
- 图表加载状态：骨架屏（Skeleton）覆盖整个画布区域，内容加载完成后替换

### DiagramViewer 格式分发

```tsx
// diagram-viewer.tsx
function DiagramViewer({ diagram, content }: DiagramViewerProps) {
  if (diagram.format === "reactflow_json") {
    return (
      <ReactFlowRenderer
        diagram={diagram}
        content={content}
      />
    );
  }

  if (diagram.format === "mermaid") {
    return <MermaidRenderer syntax={content} />;
  }

  return <div className="text-muted">{t(uiStrings.studio.diagrams.unsupportedFormat)}</div>;
}
```

## Zustand Store 扩展

在现有 Studio store（或创建 `useDiagramStore`）中追加：

```typescript
interface DiagramStoreState {
  activeDiagramId: string | null;
  setActiveDiagramId: (id: string | null) => void;
}
```

`studioView` 字段扩展：新增 `"diagrams"` 和 `"diagram-detail"` 两个值，与 batch-3 的 `"notes"` 等值并列。
