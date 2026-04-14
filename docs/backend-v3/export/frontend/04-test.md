# 测试策略

## 1. 测试范围

导出功能覆盖两个独立场景，测试策略按场景划分。

## 2. Studio 即时导出

### 2.1 单元级验证

| 测试项 | 验证内容 |
|------|------|
| 文件名安全处理 | 特殊字符替换为下划线、空标题回退为 "untitled" |
| Blob 构造 | 内容为 UTF-8 编码的 Markdown，type 为 text/markdown |

### 2.2 组件级验证

| 测试项 | 验证内容 |
|------|------|
| Video Summary 导出按钮渲染 | summaryQuery 加载完成后，按钮出现在 meta 区域 |
| Video Summary 导出点击 | 点击后调用 saveAs，传入的 Blob 内容与 summary_content 一致 |
| Note 导出按钮渲染 | activeNote 加载完成后，按钮出现在标题区域 |
| Note 导出点击 | 点击后调用 saveAs，传入的 Blob 内容与 note.content 一致 |
| 按钮无障碍 | 按钮具有 aria-label 和 title 属性 |

### 2.3 测试策略

- 使用 vitest + @testing-library/react
- mock `file-saver` 的 `saveAs` 用于验证调用参数
- 不需要 E2E 测试，因为即时导出是纯前端行为

## 3. Notebook 归档导出

### 3.1 组件级验证

| 测试项 | 验证内容 |
|------|------|
| Notebook 列表加载 | 下拉列表正确展示已有 Notebook |
| 内容类型勾选 | 默认全选，可以单独取消勾选 |
| 导出按钮禁用状态 | 未选择 Notebook 时，导出按钮禁用 |
| 导出按钮禁用状态 | 所有内容类型取消勾选时，导出按钮禁用 |
| 导出请求参数 | 点击导出后，fetch 的 URL 包含正确的 notebookId 和 types 参数 |
| 导出成功 | 响应为 Blob 时，调用 saveAs |
| 导出失败 | 响应非 2xx 时，展示错误信息 |
| Loading 状态 | 导出过程中显示 loading 指示器，按钮禁用 |

### 3.2 测试策略

- 使用 vitest + @testing-library/react
- mock fetch 返回 Blob 或错误响应
- mock `file-saver` 的 `saveAs`

## 4. notebook-export-panel 组件命名验证

| 测试项 | 验证内容 |
|------|------|
| 组件文件名 | 文件路径为 `components/layout/notebook-export-panel.tsx` |
| control-panel 引用 | control-panel.tsx 中引用 notebook-export-panel，不再引用 notes-export-panel |

## 5. 不测试的内容

- Diagram PNG 导出（已有独立实现和测试，不在本次范围）
- ZIP 包内容与 manifest.json 的正确性（后端职责，由后端测试覆盖）
- 浏览器下载行为的实际触发（受限于测试环境，通过验证 saveAs 调用参数间接覆盖）
- 导入功能（本版不实现，后续独立测试策略）
