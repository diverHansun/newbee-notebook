# Batch-4 收尾: 笔记导出 + Diagram 图片导出

## 一、现状分析

### 1.1 笔记 (Notes) 模块现状

**后端 API:**
- `GET /notebooks/{notebook_id}/notes` -- 按 notebook 列表, 支持 `?document_id=` 筛选
- `GET /notes/{note_id}` -- 按 ID 获取单条 (含完整 content)
- `POST /notes` / `PATCH /notes/{note_id}` / `DELETE /notes/{note_id}`
- **缺失:** 无全局 `GET /notes` 端点; NoteRepository 只有 `list_by_notebook()`, 无 `list_all()`

**Service 层:**
- `NoteService.list_by_notebook(notebook_id, document_id?)` -- 唯一的列表方法
- 无全局列表、排序功能

**前端 API 客户端:**
- `listNotes(notebookId, params?)` -- 仅 notebook 维度
- 无全局笔记查询函数

**前端 Settings (Control Panel):**
- 现有 tab: language, theme, model, mcp, about
- 预留但未实现: rag, skills
- 无 "数据/个人笔记" 板块

### 1.2 Diagram 模块现状

**后端 API:** 完整 CRUD, 无需改动
- `GET /diagrams`, `GET /diagrams/{id}`, `GET /diagrams/{id}/content`
- `PATCH /diagrams/{id}/positions`, `DELETE /diagrams/{id}`

**前端渲染组件:**
- `reactflow-renderer.tsx` -- ReactFlow 画布渲染 (思维导图/流程图)
- `mermaid-renderer.tsx` -- Mermaid SVG 渲染 (流程图/时序图)
- `diagram-viewer.tsx` -- 路由层, 按 format 分发
- `studio-panel.tsx` -- 图表详情视图 (标题、ID、类型、删除)

**导出现状:** 无任何导出功能; 未安装 `html-to-image` 库

---

## 二、实施目标

### 目标 1: 笔记导出

在 Settings 面板新增 "数据" -> "个人笔记" 板块:
- 全局查看所有笔记 (不受 notebook 限制)
- 筛选: 按关联文档 ID 过滤
- 排序: 按创建时间 / 修改时间, 升序 / 降序
- 单条导出: 下载为 `{title}_{note_id}.md`
- 全部导出: 打包为 `newbee-notes-export-{YYYY-MM-DD}.zip`, 每条笔记一个 .md 文件

Markdown 文件格式 (带元数据头):
```markdown
---
id: {note_id}
created: {created_at}
updated: {updated_at}
documents: [{doc_title_1}, {doc_title_2}]
---

# {note.title}

{note.content}
```

### 目标 2: Diagram 图片导出

在 Studio 图表详情视图, "图表详情" 标题行右侧添加下载按钮:
- 点击后将当前 diagram 导出为 PNG (白色背景)
- 文件名: `{diagram.title}.png`
- ReactFlow 类型: 使用 `html-to-image` 的 `toPng()` 捕获画布
- Mermaid 类型: 提取已渲染 SVG, 通过 Canvas 转 PNG

---

## 三、实施方案

### 3.1 笔记导出 -- 后端改动

#### 3.1.1 Repository 层

文件: `newbee_notebook/domain/repositories/note_repository.py`

新增抽象方法:
```python
async def list_all(self) -> list[Note]
```

文件: `newbee_notebook/infrastructure/repositories/sqlite_note_repository.py`

实现 `list_all()`: 查询 notes 表全量数据, 附带 document_ids 和 mark_ids 关联.

#### 3.1.2 Service 层

文件: `newbee_notebook/application/services/note_service.py`

新增方法:
```python
async def list_all(
    self,
    document_id: str | None = None,
    sort_by: str = "updated_at",   # "created_at" | "updated_at"
    order: str = "desc",           # "asc" | "desc"
) -> list[Note]:
```

全量获取后, 在内存中执行筛选和排序 (笔记总量 < 1000).

#### 3.1.3 Router 层

文件: `newbee_notebook/api/routers/notes.py`

新增端点:
```
GET /notes?document_id=&sort_by=updated_at&order=desc
```

返回 `NoteListResponse` (复用现有 response model).

#### 3.1.4 测试

文件: `newbee_notebook/tests/unit/application/services/test_note_service.py` (新增或扩展)

覆盖: list_all 无参数 / 按 document_id 筛选 / 排序方向验证.

### 3.2 笔记导出 -- 前端改动

#### 3.2.1 API 客户端

文件: `frontend/src/lib/api/notes.ts`

新增:
```typescript
export async function listAllNotes(params?: {
  document_id?: string;
  sort_by?: "created_at" | "updated_at";
  order?: "asc" | "desc";
}): Promise<NoteListResponse>
```

#### 3.2.2 Settings UI

文件: `frontend/src/components/layout/control-panel.tsx`

- 新增 `"data"` tab 到 ControlPanelTab 类型和导航列表
- tab 图标: 数据库/文件夹类图标

文件: `frontend/src/components/layout/notes-export-panel.tsx` (新建)

组件结构:
```
NotesExportPanel
  +-- 筛选栏: 文档下拉选择 + 排序切换 (created_at/updated_at + asc/desc)
  +-- 笔记列表: 勾选框 + 标题 + 关联文档标签 + 时间
  +-- 操作栏: "导出选中" + "全部导出" 按钮
```

数据流:
1. 组件挂载时调用 `listAllNotes()` 获取全量笔记
2. 筛选/排序变化时重新调用 API (或前端内存过滤)
3. 导出时, 对每条选中笔记调用 `getNote(noteId)` 获取完整 content
4. 生成 markdown 文件, 单条直接下载, 多条用 jszip 打包

#### 3.2.3 依赖

```
pnpm add jszip
pnpm add -D @types/jszip  (如需要)
```

#### 3.2.4 i18n

文件: `frontend/src/lib/i18n/strings.ts`

新增 data/export 相关文案: tab 标签、筛选提示、导出按钮、成功/失败提示.

### 3.3 Diagram 图片导出

#### 3.3.1 依赖

```
pnpm add html-to-image
```

#### 3.3.2 ReactFlow 导出

文件: `frontend/src/components/studio/reactflow-renderer.tsx`

- 通过 `useReactFlow()` 获取实例
- 暴露 `exportImage` 回调 (通过 `useImperativeHandle` 或 props callback)
- 导出逻辑: `toPng(reactFlowWrapper, { backgroundColor: '#ffffff' })`

#### 3.3.3 Mermaid 导出

文件: `frontend/src/components/studio/mermaid-renderer.tsx`

- 暴露 `exportImage` 回调
- 导出逻辑:
  1. 获取容器内 `<svg>` 元素
  2. 序列化为 SVG 字符串
  3. 创建 Image + Canvas, 绘制后 `canvas.toBlob('image/png')`
  4. 触发下载

#### 3.3.4 DiagramViewer + StudioPanel

文件: `frontend/src/components/studio/diagram-viewer.tsx`

- 通过 `forwardRef` + `useImperativeHandle` 暴露 `{ exportImage: () => Promise<void> }`

文件: `frontend/src/components/studio/studio-panel.tsx`

- 在 "图表详情" 标题行右侧添加下载图标按钮
- 点击时调用 `diagramViewerRef.current.exportImage()`

---

## 四、文件清单

| 层 | 文件 | 操作 |
|---|---|---|
| Backend repo | `domain/repositories/note_repository.py` | 修改 |
| Backend repo impl | `infrastructure/repositories/sqlite_note_repository.py` | 修改 |
| Backend service | `application/services/note_service.py` | 修改 |
| Backend router | `api/routers/notes.py` | 修改 |
| Backend test | `tests/unit/.../test_note_service.py` | 新增/修改 |
| Frontend API | `lib/api/notes.ts` | 修改 |
| Frontend Settings | `components/layout/control-panel.tsx` | 修改 |
| Frontend Export Panel | `components/layout/notes-export-panel.tsx` | 新增 |
| Frontend Diagram Viewer | `components/studio/diagram-viewer.tsx` | 修改 |
| Frontend ReactFlow | `components/studio/reactflow-renderer.tsx` | 修改 |
| Frontend Mermaid | `components/studio/mermaid-renderer.tsx` | 修改 |
| Frontend Studio | `components/studio/studio-panel.tsx` | 修改 |
| Frontend i18n | `lib/i18n/strings.ts` | 修改 |
| Frontend deps | `package.json` | 修改 (jszip, html-to-image) |

---

## 五、实施顺序

1. **Diagram PNG 导出** (独立, 不依赖后端改动)
   - 安装 html-to-image
   - 实现 ReactFlow / Mermaid 导出回调
   - studio-panel 添加下载按钮

2. **笔记导出 -- 后端**
   - Repository list_all + Service list_all + Router GET /notes
   - 单元测试

3. **笔记导出 -- 前端**
   - API 客户端 listAllNotes
   - Settings "数据" tab + NotesExportPanel
   - jszip 打包导出
   - i18n 文案
