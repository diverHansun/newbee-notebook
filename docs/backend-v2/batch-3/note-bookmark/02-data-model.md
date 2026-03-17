# Note-Bookmark 模块：数据模型

## 1. 实体关系总览

```
Document (已有)
    |
    |--- 1:N ---> Mark (文档级书签)
    |                  |
    |                  |--- N:M ---> NoteMarkRef ---> Note
    |                                                  |
    |--- N:M ---> NoteDocumentTag --------------------|
    |
    |--- N:M ---> NotebookDocumentRef ---> Notebook (已有)
```

关键关系：

- Mark 直接归属 Document（1:N）
- Note 通过 NoteDocumentTag 与 Document 关联（N:M）
- Note 通过 NoteMarkRef 引用 Mark（N:M）
- Studio 面板查询路径：Notebook -> NotebookDocumentRef -> Document -> NoteDocumentTag -> Note

## 2. 新增表定义

### 2.1 marks

```sql
CREATE TABLE marks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    anchor_text TEXT NOT NULL,
    char_offset INTEGER NOT NULL,
    comment     TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_marks_document_id ON marks(document_id);
CREATE INDEX idx_marks_created_at ON marks(created_at);
```

字段说明：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 书签唯一标识 |
| document_id | UUID | FK, NOT NULL | 归属文档，级联删除 |
| anchor_text | TEXT | NOT NULL | 用户选中的文本内容，截断上限 500 字符 |
| char_offset | INTEGER | NOT NULL | 选中文本在原始 Markdown 内容中的起始字符偏移量 |
| comment | TEXT | 可选 | 用户对该书签的短评 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

设计决策：

- char_offset 而非 chunk_index：chunk_index 依赖前端分块算法参数（TARGET_CHUNK_CHARS），算法变更会导致已存储索引失效。char_offset 仅依赖文档内容本身，而文档经处理后存入 MinIO 的 Markdown 内容是不可变的。前端可在运行时从 char_offset 计算出目标 chunk。
- anchor_text 截断上限 500 字符：覆盖绝大多数书签场景，避免存储整段落级文本。

### 2.2 notes

```sql
CREATE TABLE notes (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title      VARCHAR(500) NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notes_updated_at ON notes(updated_at);
CREATE INDEX idx_notes_created_at ON notes(created_at);
```

字段说明：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 笔记唯一标识 |
| title | VARCHAR(500) | NOT NULL | 笔记标题 |
| content | TEXT | NOT NULL, DEFAULT '' | Markdown 格式内容，存储于数据库 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

设计决策：

- 内容存储在 DB TEXT 字段而非 MinIO：笔记是用户频繁编辑的短文本（数百到数千字），不像文档那样是大型不可变文件。DB 存储简化了 CRUD 操作、保证事务一致性、便于后续搜索扩展。导出功能只需将 TEXT 字段输出为 .md 文件。
- Note 无 notebook_id 外键：Note 是全局实体，通过 note_document_tags 间接关联到 Notebook 的文档集合。

### 2.3 note_document_tags

```sql
CREATE TABLE note_document_tags (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id     UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (note_id, document_id)
);

CREATE INDEX idx_note_document_tags_note_id ON note_document_tags(note_id);
CREATE INDEX idx_note_document_tags_document_id ON note_document_tags(document_id);
```

语义：标记一个 Note 是关于哪些 Document 的。用于 Studio 面板按 Notebook 文档集合筛选 Notes。

### 2.4 note_mark_refs

```sql
CREATE TABLE note_mark_refs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id    UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    mark_id    UUID NOT NULL REFERENCES marks(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (note_id, mark_id)
);

CREATE INDEX idx_note_mark_refs_note_id ON note_mark_refs(note_id);
CREATE INDEX idx_note_mark_refs_mark_id ON note_mark_refs(mark_id);
```

语义：记录 Note 中通过 `[[mark:mark_id]]` 语法引用了哪些 Mark。前端在保存笔记内容时解析 wiki-link，同步维护此关联表。

## 3. Domain Entities

遵循现有 dataclass 模式（继承 Entity 基类）。

```python
@dataclass
class Mark(Entity):
    mark_id: str = field(default_factory=generate_uuid)
    document_id: str = ""
    anchor_text: str = ""
    char_offset: int = 0
    comment: str | None = None

@dataclass
class Note(Entity):
    note_id: str = field(default_factory=generate_uuid)
    title: str = ""
    content: str = ""

@dataclass
class NoteDocumentTag(Entity):
    tag_id: str = field(default_factory=generate_uuid)
    note_id: str = ""
    document_id: str = ""

@dataclass
class NoteMarkRef(Entity):
    ref_id: str = field(default_factory=generate_uuid)
    note_id: str = ""
    mark_id: str = ""
```

## 4. 级联删除规则

| 触发操作 | 级联效果 | 机制 |
|---------|---------|------|
| 删除 Document | 该文档所有 Mark 删除 | FK ON DELETE CASCADE |
| 删除 Document | note_document_tags 中该文档的关联删除 | FK ON DELETE CASCADE |
| 删除 Document | 被删除 Mark 对应的 note_mark_refs 删除 | FK ON DELETE CASCADE（经 Mark） |
| 删除 Note | note_document_tags 中该笔记的关联删除 | FK ON DELETE CASCADE |
| 删除 Note | note_mark_refs 中该笔记的引用删除 | FK ON DELETE CASCADE |
| 删除 Mark | note_mark_refs 中该书签的引用删除 | FK ON DELETE CASCADE |

前端约束：删除 Document 时，若存在关联 Mark，确认对话框需提示"此文档有 N 个书签，删除后书签将一并删除。关联这些书签的笔记引用也会失效。"该提示所需的 affected_marks_count 由 MarkService 提供。

## 5. 查询路径

### 5.1 Studio 展示 Notes（按 Notebook）

```sql
SELECT DISTINCT n.*
FROM notes n
JOIN note_document_tags ndt ON ndt.note_id = n.id
JOIN notebook_document_refs ndr ON ndr.document_id = ndt.document_id
WHERE ndr.notebook_id = :notebook_id
ORDER BY n.updated_at DESC;
```

### 5.2 Studio 按单文档过滤 Notes

```sql
SELECT n.*
FROM notes n
JOIN note_document_tags ndt ON ndt.note_id = n.id
WHERE ndt.document_id = :document_id
ORDER BY n.updated_at DESC;
```

### 5.3 Viewer 获取文档书签

```sql
SELECT * FROM marks
WHERE document_id = :document_id
ORDER BY char_offset ASC;
```

### 5.4 Notebook 下所有书签

```sql
SELECT m.*
FROM marks m
JOIN notebook_document_refs ndr ON ndr.document_id = m.document_id
WHERE ndr.notebook_id = :notebook_id
ORDER BY m.created_at DESC;
```
