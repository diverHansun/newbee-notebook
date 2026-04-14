# 组件结构与状态设计

## 1. 总体架构

导出功能涉及两个独立的 UI 区域，不共享组件或状态：

```
Studio 面板（即时导出）
├── video-detail.tsx        -- 新增导出按钮
├── studio-panel.tsx        -- renderNoteDetail 新增导出按钮
└── studio-panel.tsx        -- renderDiagramDetail（已有 PNG 导出，不改动）

Settings 控制面板（归档导出）
└── notebook-export-panel.tsx   -- 新组件，替换现有 notes-export-panel.tsx
```

## 2. Studio 即时导出：组件改动

### 2.1 Video Summary 导出（video-detail.tsx）

改动范围：在现有的 `card video-detail-card` 内部，将 meta 区域改为 `row-between` 布局，右侧放置导出 icon 按钮。

按钮位置：

```
┌────────────────────────────────────────────┐
│  视频标题                                    │
│  [Bilibili] [作者] [3:42] [BV...]     [箭头] │
└────────────────────────────────────────────┘
```

实现方式：

- 按钮复用 Diagram 导出的 SVG icon（16x16 向下箭头）
- 点击时将 `summary.summary_content` 构造为 `new Blob([content], { type: "text/markdown;charset=utf-8" })`
- 文件名：`{title}.md`，对 title 做文件名安全处理（替换特殊字符）
- 使用 `saveAs(blob, filename)` 触发下载

不引入新的状态，所有数据均取自已加载的 `summary` 对象。

### 2.2 Note 导出（studio-panel.tsx renderNoteDetail）

改动范围：在 Note detail 视图的标题区域旁新增导出 icon 按钮。

实现方式与 Video Summary 相同：

- 取 `activeNote.content` 和 `activeNote.title`
- 构造 Markdown Blob 并触发 saveAs
- 文件名：`{title}.md`

### 2.3 导出 icon 按钮的统一规格

三个子模块的导出按钮保持以下一致属性：

| 属性 | 值 |
|------|------|
| className | `btn btn-ghost btn-sm` |
| SVG 尺寸 | 16x16，viewBox 0 0 24 24 |
| SVG 样式 | stroke="currentColor"，strokeWidth="2" |
| SVG 路径 | 与 Diagram 导出按钮完全相同 |
| title / aria-label | 通过 i18n key 提供 tooltip |
| style | `{ padding: "4px 6px" }` |

SVG 内容（复用已有）：

```html
<svg width="16" height="16" viewBox="0 0 24 24" fill="none"
     stroke="currentColor" strokeWidth="2"
     strokeLinecap="round" strokeLinejoin="round">
  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
  <polyline points="7 10 12 15 17 10" />
  <line x1="12" y1="15" x2="12" y2="3" />
</svg>
```

## 3. Settings 归档导出：新组件设计

### 3.1 notebook-export-panel.tsx

该组件替换现有的 `notes-export-panel.tsx`，在 Settings 控制面板的"数据"标签下渲染。

组件内部状态：

| 状态 | 类型 | 说明 |
|------|------|------|
| selectedNotebookIds | `Set<string>` | 当前选中的 Notebook（可多选） |
| notebookKeyword | `string` | Notebook 搜索关键字 |
| contentTypes | `Set<ContentType>` | 用户勾选的导出内容类型 |
| exporting | `boolean` | 是否正在导出 |
| error | `string \| null` | 导出错误信息 |

其中 `ContentType` 为：

```typescript
type ContentType = "documents" | "notes" | "marks" | "diagrams" | "video_summaries";
```

### 3.2 UI 布局

```
┌──────────────────────────────────────┐
│  Notebook 归档导出                     │
│  搜索并选择一个或多个 Notebook，逐个打包下载 │
│                                      │
│  ┌──────────────────────────────┐    │
│  │  搜索 Notebook               │    │
│  └──────────────────────────────┘    │
│  [x] Notebook A  [ ] Notebook B ...    │
│                                      │
│  包含内容：                            │
│  [x] 解析后的文档 (Markdown)            │
│  [x] 笔记                             │
│  [x] 书签 (Marks)                      │
│  [x] 图表 (Diagram 源码)               │
│  [x] 视频总结                          │
│                                      │
│  ┌──────────────────────────────┐    │
│  │  导出所选 Notebook 归档 (.zip)   │    │
│  └──────────────────────────────┘    │
│                                      │
│  (导出中显示 loading spinner)          │
└──────────────────────────────────────┘
```

### 3.3 数据获取

- Notebook 列表：复用 `listNotebooks` API + `useQuery`（若后续新增 `useNotebooks` hook 可再收敛）
- 导出操作：调用新的后端 API `GET /notebooks/{id}/export?types=documents,notes,...`，响应为 ZIP 文件的二进制流
- 使用 `fetch` + `response.blob()` 获取 ZIP，再通过 `saveAs` 触发下载
- 多选导出：对 `selectedNotebookIds` 逐个调用导出 API 并依次触发下载

### 3.4 与 notes-export-panel.tsx 的关系

notes-export-panel.tsx 重构为 notebook-export-panel.tsx。原有的批量笔记导出能力被 Notebook 归档导出完全覆盖，单条笔记导出能力迁移至 Studio Note detail 视图。

实施步骤：
1. 先完成 Studio 即时导出（无依赖，可独立上线）
2. 再完成 notebook-export-panel.tsx（依赖后端 API）
3. 最后移除 notes-export-panel.tsx 并更新 control-panel.tsx 的引用

## 4. 后续导入功能的 UI 预留

本版不实现导入功能，但以下是已确定的交互设计方向，供后续参考：

### 4.1 Notebook 列表页底栏

当前底栏为 `[+ 创建 Notebook]  [查看 Library]`，后续新增导入按钮：

```
┌───────────────────────────────────────────────┐
│  [+ 创建 Notebook]  [导入 Notebook]  [查看 Library] │
└───────────────────────────────────────────────┘
```

### 4.2 导入上传方式

支持两种方式，后端统一接收 ZIP：

| 方式 | 前端实现 | 说明 |
|------|------|------|
| 选择 ZIP 文件 | `<input type="file" accept=".zip">` | 全浏览器兼容 |
| 选择文件夹 | File System Access API (`showDirectoryPicker`) 或 `<input webkitdirectory>` | 前端用 JSZip 将文件夹打包为 ZIP 后上传 |

两种方式在 UI 上并列展示，用户选择其一。无论哪种方式，最终都通过同一个后端 API 上传 ZIP。

### 4.3 导入流程概述

导入分两阶段：

1. 校验阶段 -- 上传 ZIP 后后端解析 manifest.json，返回预览报告（新增多少、冲突多少）
2. 确认阶段 -- 用户确认后执行实际导入

导入的文档写入 Library 并关联到新 Notebook 的 Sources 面板，但不自动触发 embedding/ES 流水线。用户在 Sources 面板中手动触发文档的转换和处理。

## 5. 设计模式与理由

不引入额外的设计模式。

理由：
- Studio 即时导出只需在现有组件内添加一个按钮和几行下载逻辑，不构成独立模块
- 归档导出面板是单一组件，内部状态通过 useState 管理即可，不需要 Context 或状态机
- 下载触发逻辑（Blob + saveAs）足够简单，不需要抽象为 hook 或 util

## 6. 约束与权衡

### 选择后端生成 ZIP 而非前端打包

前端打包方案（使用 JSZip）在理论上可行，但归档导出需要拉取多种数据（文档内容、笔记、图表源码等），全部在前端完成意味着：
- 需要发起大量并行 API 请求
- 大型文档（如整本书的解析结果）可能导致浏览器内存压力
- 前端打包过程无法做进度反馈
- manifest.json 的构建需要知道文档元数据（content_type、page_count 等），前端不一定全部持有

后端打包方案将数据聚合、manifest 构建和 ZIP 生成放在服务端，前端只需一次请求即可获取结果。

### 不将 sanitizeFilename / saveAs 提取为公共 util

三个导出场景（Diagram PNG、Video MD、Note MD）的数据准备逻辑完全不同，唯一的共同点是调用 `saveAs`。为一行代码提取 util 不产生实际价值。各组件内部各自调用 `saveAs` 即可。
