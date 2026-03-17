# Note-Bookmark 模块：设计目标与职责边界

## 1. 设计目标

### 1.1 全局笔记实体

Note 是独立于 Notebook 的全局知识实体。Notebook 只是操作载体（类似 VSCode 项目窗口），不拥有 Note。Note 通过文档标签（note_document_tags）与 Document 建立多对多关联，间接出现在包含这些文档的 Notebook 的 Studio 面板中。

### 1.2 文档级书签

Mark 是对文档 Markdown 内容特定位置的标记。每个 Mark 直接关联一个 Document，记录选中文本（anchor_text）和字符偏移量（char_offset）。Mark 与 Notebook 无关。

### 1.3 笔记-书签引用

Note 可通过 `[[mark:mark_id]]` wiki-link 语法在内容中引用 Mark。引用关系在 note_mark_refs 关联表中维护。一个 Note 可引用多个 Mark，一个 Mark 可被多个 Note 引用。

### 1.4 服务层中立

NoteService 和 MarkService 不感知调用方身份。同一套 Service 方法同时服务于：

- 前端 REST API（用户直接操作）
- Agent Skill 层（/note 命令激活后由 agent 调用）

调用方差异（如 agent 操作需确认）由上层处理，Service 层不涉及。

## 2. 职责

### 2.1 MarkService

- Mark 的 CRUD 操作
- 按 document_id 查询书签列表（Viewer 渲染高亮用）
- 按 notebook_id 联查书签列表（Studio 展示用，通过 notebook_document_refs 关联）
- Mark comment 的更新

### 2.2 NoteService

- Note 的 CRUD 操作
- Note 内容的 partial update（支持 auto-save 场景：5s 防抖 / Ctrl+S）
- Note 与 Document 的标签关联管理（添加/移除文档标签）
- Note 与 Mark 的引用关系管理（添加/移除 mark 引用）
- 按 notebook_id 查询关联 notes（查询链：notebook -> notebook_document_refs -> document_ids -> note_document_tags -> notes）
- 按 document_id 过滤 notes

### 2.3 级联清理

- 删除 Document 时：该文档下所有 Mark 级联删除（ON DELETE CASCADE），note_document_tags 中的关联记录级联删除
- 删除 Note 时：note_document_tags 和 note_mark_refs 中的关联记录级联删除
- 删除 Mark 时：note_mark_refs 中的引用记录级联删除

### 2.4 Repository 层

遵循现有 Repository 模式，为 Mark、Note、NoteDocumentTag、NoteMarkRef 各提供独立的 Repository 接口和 SQLAlchemy 实现。

## 3. 非职责

- 不负责 Mark 在前端 Viewer 中的渲染逻辑（属于前端 rehype 插件职责）
- 不负责 Agent 工具调用的权限控制和确认机制（属于 note-related-skills 模块职责）
- 不负责 Note 内容中 `[[mark:mark_id]]` 语法的解析和渲染（属于前端 Markdown 编辑器/渲染器职责）
- 不负责 Note 的导出功能（后续批次实现）
- 不负责 Note 的全文搜索（初期仅列表浏览和按文档过滤）
- 不实现笔记的协作编辑或多用户共享
