# 设计目标与职责边界

## 1. 设计目标

### 1.1 提供 Notebook 级别的一站式归档导出

用户（通过前端）选择一个 Notebook 后，后端将该 Notebook 关联的全部或部分内容打包为 ZIP 文件返回。用户无需逐条下载，也无需在前端等待大量并行请求。

### 1.2 导出格式面向 round-trip，兼容后续导入

ZIP 包内包含 manifest.json 清单文件，记录 Notebook 元信息、各内容条目的元数据及其关联关系。后续的导入功能可以直接解析 manifest.json 来重建 Notebook 结构，而无需对文件内容做反向推断。

### 1.3 复用已有 Service 层，不引入新的数据访问路径

归档导出的数据全部通过已有的 Service 方法获取（DocumentService、NoteService、MarkService、DiagramService、VideoService）。不绕过 Service 直接访问 Repository 或存储后端，保持现有分层结构的完整性。

### 1.4 ZIP 结构清晰，可直接用于离线阅读

导出的 ZIP 包内按内容类型分目录，文件使用 `{safe_title}_{id}` 可读命名，解压后无需额外工具即可浏览。manifest.json 同时作为包内的目录索引。

### 1.5 支持按类型选择性导出

用户可以只选择导出文档和笔记而不包含图表，避免不需要的内容增大包体积。后端通过查询参数接收类型筛选，默认导出全部。

## 2. 职责

### 2.1 ExportService（新增，Application 层）

负责：

- 接收 notebook_id 和 types 参数
- 获取 Notebook 元信息（标题、描述）
- 编排 Service 调用，按类型分别获取数据
- 将获取到的内容写入 zipfile.ZipFile（BytesIO 模式）
- 构建 manifest.json 并写入 ZIP 根目录
- 处理单条内容获取失败的情况（跳过失败项，记录到 export-errors.txt，不中断整体导出）
- 返回 BytesIO 对象供 API 层构造响应

### 2.2 API 端点（新增，API 层）

负责：

- 路由注册：GET /api/notebooks/{notebook_id}/export
- 参数校验：types 为合法枚举值的逗号分隔列表
- 校验 Notebook 是否存在（404）
- 调用 ExportService 获取 ZIP 内容
- 构造 StreamingResponse，设置 Content-Type 和 Content-Disposition

### 2.3 DI 注册

负责：

- 将 ExportService 注册到依赖注入容器
- ExportService 依赖已有的 NotebookService、NotebookDocumentService、DocumentService、NoteService、MarkService、DiagramService、VideoService

## 3. 非职责

- 不负责 Studio 即时导出（前端完成，不涉及后端）
- 不负责导出 embedding 向量、ES 索引或其他派生数据（这些可从 Markdown 内容重建）
- 不负责导出原始文档文件（PDF/DOCX 等），只导出解析后的 Markdown 内容
- 不负责 Session 会话导出（本版预留目录结构，下一版实现）
- 不负责 Notebook 导入功能（本版不实现）
- 不负责导出进度的实时推送（初版不实现 SSE 进度，前端展示简单 loading 状态）
- 不负责管理导出历史或导出任务队列
- 不做 ZIP 文件的持久化存储（生成后即返回，不保存到 MinIO 或文件系统）
- 不处理 Diagram 的 PNG 渲染（图表导出为源码，不做服务端渲染）
