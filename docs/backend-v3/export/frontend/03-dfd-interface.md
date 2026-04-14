# 数据流、接口与事件约定

## 1. 上下文与范围

本文档描述导出模块前端的两条数据流：

1. Studio 即时导出 -- 数据来源为页面已加载的状态，不涉及网络请求
2. Notebook 归档导出 -- 数据来源为后端归档 API，涉及一次网络请求和二进制响应处理

## 2. 数据流描述

### 2.1 Studio 即时导出（Video Summary）

```
summary 对象（useVideoSummary hook 已加载）
  │
  ├─ summary.summary_content    → Markdown 文本
  ├─ summary.title              → 文件名基础
  │
  ▼
用户点击导出按钮
  │
  ▼
构造 Blob: new Blob([summary.summary_content], { type: "text/markdown;charset=utf-8" })
  │
  ▼
调用 saveAs(blob, sanitize(summary.title) + ".md")
  │
  ▼
浏览器触发文件下载
```

不涉及 API 调用。summary 对象在进入详情页时已通过 `useVideoSummary(summaryId)` 加载。

### 2.2 Studio 即时导出（Note）

```
activeNote 对象（studio-panel.tsx 内部状态，已加载）
  │
  ├─ activeNote.content         → Markdown 文本
  ├─ activeNote.title           → 文件名基础
  │
  ▼
（流程同 2.1）
```

### 2.3 Notebook 归档导出

```
用户在 notebook-export-panel 中操作
  │
  ├─ 搜索并多选 Notebook（selectedNotebookIds）
  ├─ 勾选内容类型（contentTypes）
  │
  ▼
前端按所选 Notebook 逐个发起请求:
  GET /api/notebooks/{notebookId}/export?types=documents,notes,marks,diagrams,video_summaries
  Accept: application/zip
  │
  ▼
后端聚合数据，生成 ZIP 流
  │
  ▼
前端接收响应:
  const response = await fetch(url);
  const blob = await response.blob();
  │
  ▼
从 Content-Disposition header 提取文件名（兜底使用默认名）
  │
  ▼
调用 saveAs(blob, filename)
  │
  ▼
浏览器触发该 Notebook 的 ZIP 下载（多选时重复此流程）
```

## 3. 接口约定

### 3.1 后端归档导出 API（前端消费侧视角）

请求：

```
GET /api/notebooks/{notebook_id}/export
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| types | string | 否 | 逗号分隔的内容类型，默认全部。可选值：documents, notes, marks, diagrams, video_summaries |

响应：

| 项 | 说明 |
|------|------|
| Content-Type | application/zip |
| Content-Disposition | attachment; filename="notebook-{title}-{date}.zip" |
| Body | ZIP 二进制流，根目录包含 manifest.json 及各内容子目录 |

ZIP 内包含后端构建的 `manifest.json`，用于描述归档包的结构和元数据。前端下载后不需要解析 manifest.json，该文件的主要消费场景是后续的导入功能。

错误场景：

| HTTP 状态码 | 说明 | 前端处理 |
|------|------|------|
| 404 | Notebook 不存在 | 显示错误提示 |
| 422 | types 参数非法 | 显示错误提示 |
| 500 | 打包过程失败 | 显示错误提示，建议重试 |

### 3.2 前端 API 封装

在 `lib/api/` 中新增导出相关函数：

```typescript
// lib/api/notebooks.ts（追加）
export async function exportNotebook(
  notebookId: string,
  types?: string[],
): Promise<Blob> {
  const params = new URLSearchParams();
  if (types && types.length > 0) {
    params.set("types", types.join(","));
  }
  const query = params.toString();
  const url = query
    ? `/api/v1/notebooks/${notebookId}/export?${query}`
    : `/api/v1/notebooks/${notebookId}/export`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new ApiError(response.status, "E_EXPORT_FAILED", await response.text());
  }
  return response.blob();
}
```

### 3.3 文件名安全处理

Studio 即时导出需要对文件名做安全处理，方式为内联函数：

```typescript
function sanitize(name: string): string {
  return name.replace(/[<>:"/\\|?*]/g, "_").trim() || "untitled";
}
```

不提取为公共 util，各组件按需自行编写。

## 4. i18n Key 规划

新增以下 i18n key：

| Key 路径 | 中文 | 英文 |
|------|------|------|
| video.exportMarkdown | 导出 Markdown | Export Markdown |
| studio.exportNoteMarkdown | 导出笔记 | Export Note |
| dataPanel.notebookExport | Notebook 归档导出 | Notebook Archive Export |
| dataPanel.notebookExportDesc | 搜索并选择一个或多个 Notebook，将其内容打包下载 | Search and select one or more notebooks to export as archive |
| dataPanel.selectNotebook | 选择 Notebook | Select Notebook |
| dataPanel.contentTypes | 包含内容 | Include Content |
| dataPanel.exportArchive | 导出归档 (.zip) | Export Archive (.zip) |
| dataPanel.exportArchiveLoading | 正在打包... | Packaging... |
| dataPanel.documents | 解析后的文档 | Parsed Documents |
| dataPanel.notes | 笔记 | Notes |
| dataPanel.marks | 书签 | Bookmarks |
| dataPanel.diagrams | 图表源码 | Diagram Source |
| dataPanel.videoSummaries | 视频总结 | Video Summaries |

## 5. 后续导入功能的接口预留

本版不实现导入功能，但以下是已确定的接口方向，供后续参考：

### 5.1 导入 API（两阶段）

**校验阶段：**

```
POST /api/notebooks/import/validate
Content-Type: multipart/form-data
Body: file=<ZIP 文件>
```

返回：解析 manifest.json 后生成的预览报告（将导入哪些内容、是否有冲突等）。

**确认阶段：**

```
POST /api/notebooks/import/confirm
Content-Type: application/json
Body: { "import_id": "<校验阶段返回的临时 ID>" }
```

返回：导入结果（新建的 Notebook ID、导入的各类内容计数）。

### 5.2 前端文件夹选择与 ZIP 打包

当用户选择文件夹导入时，前端使用 JSZip 将文件夹内容打包为 ZIP，再通过上述 API 上传。后端只接收 ZIP，保持单一处理路径。

### 5.3 导入相关 i18n Key 预留

| Key 路径 | 中文 | 英文 |
|------|------|------|
| import.importNotebook | 导入 Notebook | Import Notebook |
| import.selectFile | 选择 ZIP 文件 | Select ZIP File |
| import.selectFolder | 选择文件夹 | Select Folder |
| import.validating | 正在校验... | Validating... |
| import.previewTitle | 导入预览 | Import Preview |
| import.confirmImport | 确认导入 | Confirm Import |
| import.importing | 正在导入... | Importing... |
| import.success | 导入成功 | Import Successful |
| import.error | 导入失败 | Import Failed |
