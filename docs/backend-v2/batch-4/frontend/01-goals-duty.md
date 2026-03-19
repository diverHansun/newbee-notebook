# 设计目标与职责

## 设计目标

### 目标一：Studio 图表卡片作为通用入口

Studio 首屏的"图表"卡片语义上代表所有图表类型（思维导图、流程图等），而非单一的思维导图。batch-4 先实现 mindmap，卡片命名和内部视图结构保持类型可扩展。

### 目标一补充：统一 slash 入口，降低学习成本

聊天侧统一使用 `/diagram` 单命令。用户可直接描述“生成思维导图/流程图/时序图”；若描述未明确类型，前端通过确认卡片承接后端 `confirmation_request`，让用户选择类型后继续执行。

### 目标二：最小化交互，保持渲染质量

React Flow 的节点拖拽重定位是唯一的用户交互写操作，且通过防抖异步保存，不阻塞 UI。pan/zoom 为内置行为。其余操作（增删节点、编辑 label）不实现，内容修改仅通过 Agent 完成。

### 目标三：内容与坐标独立加载

图表元数据（含 node_positions）和图表内容（JSON 或 Mermaid 文本）通过两个独立 API 请求加载，分别缓存。坐标更新不触发内容重新加载，内容更新（Agent 重新生成后）不丢失未保存的坐标偏移。

### 目标四：格式无关的渲染分发

DiagramViewer 组件根据 `format` 字段分发到对应渲染器，调用方无需关心渲染细节。batch-4 实现 ReactFlowRenderer，MermaidRenderer 预留文件骨架，未来启用时只需补充实现。

## 模块职责

前端 diagram 模块负责：

- Studio Home 中"图表"卡片的展示与点击导航
- DiagramListView：显示 notebook 下的图表列表，支持按文档过滤
- DiagramDetailView：加载并展示单张图表，含工具栏（导出、删除）
- ReactFlowRenderer：React Flow 渲染 + dagre 自动布局 + 用户坐标覆盖 + 防抖保存
- PNG 导出（html2canvas）
- Slash 命令选择器中新增 `/diagram` 条目（复用 batch-3 组件）
- Agent update/delete 确认卡片的图表文案适配（复用 batch-3 ConfirmationCard）

前端 diagram 模块不负责：

- 图表内容的生成或修改（通过 chat Agent 完成）
- Mermaid 渲染的完整实现（预留骨架，batch-N 补充）
- 图表内容的语义搜索
- 图表版本历史展示

## 非目标

- batch-4 不实现图表编辑（节点增删、label 编辑）
- batch-4 不实现图表间的关联或引用
- batch-4 不实现 Mermaid 渲染（mermaid 包预装但不启用渲染组件）
