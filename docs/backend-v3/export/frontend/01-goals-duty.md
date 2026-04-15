# 设计目标与职责边界

## 1. 设计目标

### 1.1 Studio 即时导出：一键下载，零等待

用户在 Studio 中查看某条 Diagram/Video Summary/Note 时，可以通过卡片区域内的 icon 按钮直接下载该条内容。整个过程在前端完成，不发起额外 API 请求（内容已在页面中加载），不出现加载状态。

### 1.2 Notebook 归档导出：以 Notebook 为单位的完整归档

用户在 Settings 数据面板中搜索并选择一个或多个 Notebook，可以将其关联的全部内容（文档、笔记、书签、图表、视频总结）分别打包为 ZIP 压缩包下载。ZIP 内包含 manifest.json 清单文件，保证导出包是自描述的，可供后续导入功能消费。

### 1.3 导出按钮的视觉一致性

Studio 三个子模块（Diagram/Video/Note）的即时导出按钮使用相同的 icon 样式（向下箭头 SVG）、相同的按钮规格（btn-ghost btn-sm）、相同的交互模式（点击即下载），不出现文字标签。

### 1.4 数据面板从"笔记导出"演进为"Notebook 归档中心"

现有 Settings 数据面板围绕笔记列表设计（筛选、排序、单条/批量导出）。重构后，数据面板围绕 Notebook 粒度设计：搜索并多选 Notebook、选择要包含的内容类型、触发归档导出。现有的笔记单条导出能力迁移至 Studio 的 Note detail 视图。notes-export-panel.tsx 重构为 notebook-export-panel.tsx。

## 2. 职责

### 2.1 Studio 即时导出（video-detail.tsx / studio-panel.tsx）

- 在 Video Summary 详情卡片的 meta 区域提供 icon 下载按钮
- 在 Note detail 视图提供 icon 下载按钮
- 将当前页面已加载的内容（summary_content / note content）构造为 Blob 并触发浏览器下载
- 使用 file-saver 的 saveAs 进行下载

### 2.2 Notebook 归档导出（notebook-export-panel.tsx）

- 展示 Notebook 列表供用户选择
- 提供内容类型勾选（文档/笔记/书签/图表/视频总结）
- 调用后端归档导出 API 获取 ZIP 文件
- 展示导出过程的 loading 状态
- 触发浏览器下载 ZIP 文件

### 2.3 i18n 维护

- 为导出相关的 tooltip、按钮文案、状态文案提供中英文 i18n key

## 3. 非职责

- 不负责 ZIP 包的生成逻辑（归档导出由后端完成）
- 不负责 Diagram 的 PNG 导出（已有实现，不在本次改动范围）
- 不负责导出内容的格式转换（如 Markdown 转 PDF）
- 不在 Studio 即时导出中添加格式选择或内容编辑能力
- 不维护导出历史记录
- 不负责 Notebook 导入功能（本版不实现）
