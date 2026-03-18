# 测试策略

## 测试层次

```
单元测试
  工具函数：applyDagreLayout、mergeUserPositions、exportReactFlowToPng
  i18n：图表相关文案键值完整性

组件测试（React Testing Library）
  DiagramListView：列表渲染、过滤、空状态、删除交互
  DiagramDetailView：加载状态、工具栏按钮行为
  DiagramViewer：format 分发逻辑
  ReactFlowRenderer：初始渲染、节点可见性

集成测试
  Slash 命令选择器：新增 /mindmap 条目显示、/flowchart 显示"即将推出"
  TanStack Query hooks：API 调用、缓存失效、错误处理
```

## 单元测试

### applyDagreLayout

```
输入：3 个节点 + 2 条边（root → n1、root → n2）
期望：输出节点均有有效 position（x、y 为数字）
期望：root 节点 x 坐标小于 n1、n2（从左到右布局）

输入：1 个节点 + 0 条边
期望：单节点有 position，不报错

输入：空 nodes 数组
期望：返回空数组，不报错
```

### mergeUserPositions

```
savedPositions 为 null → 返回原始 dagreNodes 不变
savedPositions 为空对象 → 返回原始 dagreNodes 不变
savedPositions 覆盖 node "root" 的坐标 → 仅 "root" 节点 position 被替换
savedPositions 中包含不存在的节点 ID → 忽略，其余节点不受影响
```

### exportReactFlowToPng

```
html2canvas mock 返回 canvas
  → canvas.toBlob 被调用（参数 image/png）
  → document.createElement("a") 被调用
  → link.download 为 "{title}.png"

标题包含特殊字符（例如 "test/file"）
  → 下载文件名为 "test-file.png"

标题为空字符串
  → 下载文件名为 "diagram.png"
```

## 组件测试

### DiagramListView

```
正常渲染：有 2 张图表 → 展示 2 个列表项，每项含标题、类型 badge、文档数
空状态：diagrams 为空数组 → 展示引导文案（含 /mindmap 提示）
加载中：isLoading = true → 展示骨架屏
按文档过滤：选择 documentId="doc-1" → 调用 useDiagrams(notebookId, "doc-1")
点击列表项 → studioView 切换为 "diagram-detail"，activeDiagramId 更新
点击删除按钮 → 弹出确认对话框
确认删除 → useDeleteDiagram.mutate 被调用，传入正确 diagram_id
取消删除 → useDeleteDiagram.mutate 未被调用
```

### DiagramDetailView

```
加载中：useDiagram 或 useDiagramContent loading → 展示骨架屏
加载失败 → 展示错误提示文案
加载成功（format=reactflow_json）→ 渲染 ReactFlowRenderer
加载成功（format=mermaid）→ 渲染 MermaidRenderer
点击"← 图表列表"→ studioView 切换为 "diagrams"
点击"导出图片"→ rendererRef.current.exportToPng 被调用
点击"删除"→ 弹出确认对话框，确认后调用 useDeleteDiagram，跳转到列表视图
```

### DiagramViewer

```
format = "reactflow_json" → 渲染 ReactFlowRenderer
format = "mermaid" → 渲染 MermaidRenderer
format = "unknown" → 渲染"不支持的图表格式"提示
```

### ReactFlowRenderer

```
JSON 内容解析后 nodes 数量正确
初始化后所有节点在 DOM 中可见（React Flow 渲染后节点 data-id 存在）
node_positions 为 null → 使用 dagre 坐标（x/y 不为 0/0 对所有节点）
node_positions 覆盖了 "root" → "root" 节点 position 与 savedPositions 中一致
```

## Slash 命令集成测试

```
chat 输入框键入 "/" → 命令选择器弹出
命令列表中包含 "/mindmap"（available=true）
命令列表中包含 "/flowchart"（显示"即将推出"，不可点击）
键入 "/min" → 列表过滤为仅 "/mindmap"
点击 "/mindmap" → 输入框填入 "/mindmap "，光标在末尾
```

## TanStack Query 集成测试

```
useDiagrams：
  - 调用 GET /api/v1/diagrams?notebook_id=X
  - document_id 过滤时附加 &document_id=Y 参数
  - 服务器返回 404 → isError = true

useUpdateDiagramPositions：
  - mutate 调用 PATCH /api/v1/diagrams/{id}/positions
  - onSuccess 后 ["diagram", id] queryKey 被 invalidate

useDeleteDiagram：
  - mutate 调用 DELETE /api/v1/diagrams/{id}
  - onSuccess 后 diagrams 列表和对应 diagram/content 缓存被清除
```
