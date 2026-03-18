# batch-4 / 前端 diagram 模块概述

## 模块定位

本模块负责 Newbee Notebook 前端中图表功能的全部 UI 实现，包含 Studio 图表卡片、图表列表与详情视图、React Flow 交互式渲染、节点坐标持久化、PNG 导出，以及 slash 命令触发入口。

技术栈目标：Next.js 15、React 19、TypeScript、Tailwind CSS、`@xyflow/react`、`@dagrejs/dagre`、`html2canvas`，以及预留给后续批次的 `mermaid`。

当前代码库对齐说明：

- `frontend/package.json` 目前尚未安装 `@xyflow/react`、`@dagrejs/dagre`、`html2canvas`、`mermaid`
- 前端测试脚本和 Vitest 基建目前也尚未接入，batch-4 前端任务需要先补这部分基础设施
- Mermaid 在 batch-4 仅作为格式与接口预留，不应假定“已预装可直接渲染”

## 文档索引

| 文件 | 内容 |
|------|------|
| [01-goals-duty.md](./01-goals-duty.md) | 设计目标、模块职责与边界 |
| [02-studio-diagram.md](./02-studio-diagram.md) | Studio 图表卡片、列表视图、详情视图导航结构 |
| [03-reactflow-renderer.md](./03-reactflow-renderer.md) | ReactFlowRenderer 组件、dagre 布局、坐标持久化、MindMapNode |
| [04-slash-command.md](./04-slash-command.md) | Slash 命令选择器集成、/mindmap 命令触发图表生成 |
| [05-export.md](./05-export.md) | PNG 导出实现（html2canvas）、Mermaid SVG 导出预留 |
| [06-i18n-and-types.md](./06-i18n-and-types.md) | TypeScript 类型定义、i18n 文案键值、TanStack Query hooks |
| [07-test.md](./07-test.md) | 测试策略与用例说明 |

## 与其他模块的关系

- **batch-3 前端**：复用 slash 命令选择器 UI 组件（新增 /mindmap 条目）、ConfirmationCard 组件（update/delete 图表确认）、Studio Home 卡片网格（新增"图表"卡片）
- **batch-4 后端 diagram**：消费 `/api/v1/diagrams` REST API，见 `docs/backend-v2/batch-4/diagram/06-api-layer.md`
