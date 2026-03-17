# Note-Bookmark 模块：Service 层设计

## 1. 定位

MarkService 和 NoteService 是 Note-Bookmark 模块的核心业务层。它们封装所有数据操作逻辑，对上层（REST API、Agent Skill）提供统一接口。

Service 层不感知调用方身份。是否需要用户确认、是否由 agent 发起，均由上层负责。

## 2. MarkService

### 2.1 依赖

```python
class MarkService:
    def __init__(
        self,
        mark_repo: MarkRepository,
        document_repo: DocumentRepository,
    ):
```

### 2.2 接口定义

#### 创建书签

```python
async def create_mark(
    self,
    document_id: str,
    anchor_text: str,
    char_offset: int,
    comment: str | None = None,
) -> Mark
```

- 校验 document_id 对应的文档存在且状态为 converted 或 completed
- anchor_text 截断至 500 字符
- char_offset 必须为非负整数

#### 查询书签

```python
async def get_mark(self, mark_id: str) -> Mark | None

async def list_by_document(self, document_id: str) -> list[Mark]
    """按 char_offset 升序排列，Viewer 渲染用"""

async def list_by_notebook(self, notebook_id: str) -> list[Mark]
    """通过 notebook_document_refs 联查，按 created_at 降序"""

async def count_by_document(self, document_id: str) -> int
    """删除文档前获取 affected_marks_count"""
```

#### 更新书签

```python
async def update_comment(self, mark_id: str, comment: str | None) -> Mark
```

仅支持更新 comment 字段。anchor_text 和 char_offset 创建后不可变。

#### 删除书签

```python
async def delete_mark(self, mark_id: str) -> bool
```

## 3. NoteService

### 3.1 依赖

```python
class NoteService:
    def __init__(
        self,
        note_repo: NoteRepository,
        tag_repo: NoteDocumentTagRepository,
        ref_repo: NoteMarkRefRepository,
        mark_repo: MarkRepository,
    ):
```

### 3.2 接口定义

#### Note CRUD

```python
async def create_note(self, title: str, content: str = "") -> Note

async def get_note(self, note_id: str) -> Note | None

async def update_note(
    self,
    note_id: str,
    title: str | None = None,
    content: str | None = None,
) -> Note
    """partial update：仅更新非 None 的字段。auto-save 场景调用。"""

async def delete_note(self, note_id: str) -> bool
```

#### Document 标签关联

```python
async def add_document_tag(self, note_id: str, document_id: str) -> NoteDocumentTag
    """幂等：重复添加同一对 (note_id, document_id) 不报错，返回已有记录"""

async def remove_document_tag(self, note_id: str, document_id: str) -> bool

async def list_tagged_documents(self, note_id: str) -> list[str]
    """返回 document_id 列表"""
```

#### Mark 引用管理

```python
async def add_mark_ref(self, note_id: str, mark_id: str) -> NoteMarkRef
    """幂等：重复添加不报错"""

async def remove_mark_ref(self, note_id: str, mark_id: str) -> bool

async def list_mark_refs(self, note_id: str) -> list[Mark]
    """返回完整 Mark 对象，供前端渲染 [[mark:mark_id]] 引用的悬浮预览"""
```

#### 查询

```python
async def list_by_notebook(
    self,
    notebook_id: str,
    document_id: str | None = None,
) -> list[Note]
    """
    查询链：notebook_id -> notebook_document_refs -> document_ids
    -> note_document_tags -> notes
    可选 document_id 进一步过滤
    按 updated_at 降序
    """

async def list_by_document(self, document_id: str) -> list[Note]
```

## 4. Repository 接口

遵循现有项目的 Repository 模式。每个实体一个抽象 Repository 接口，由 SQLAlchemy 实现。

### 4.1 MarkRepository

```python
class MarkRepository(ABC):
    async def create(self, mark: Mark) -> Mark
    async def get(self, mark_id: str) -> Mark | None
    async def list_by_document(self, document_id: str) -> list[Mark]
    async def list_by_notebook(self, notebook_id: str) -> list[Mark]
    async def count_by_document(self, document_id: str) -> int
    async def update(self, mark_id: str, **fields) -> Mark | None
    async def delete(self, mark_id: str) -> bool
    async def commit(self) -> None
```

### 4.2 NoteRepository

```python
class NoteRepository(ABC):
    async def create(self, note: Note) -> Note
    async def get(self, note_id: str) -> Note | None
    async def list_by_notebook(
        self, notebook_id: str, document_id: str | None = None
    ) -> list[Note]
    async def list_by_document(self, document_id: str) -> list[Note]
    async def update(self, note_id: str, **fields) -> Note | None
    async def delete(self, note_id: str) -> bool
    async def commit(self) -> None
```

### 4.3 NoteDocumentTagRepository

```python
class NoteDocumentTagRepository(ABC):
    async def create(self, tag: NoteDocumentTag) -> NoteDocumentTag
    async def get_by_pair(self, note_id: str, document_id: str) -> NoteDocumentTag | None
    async def list_by_note(self, note_id: str) -> list[NoteDocumentTag]
    async def delete_by_pair(self, note_id: str, document_id: str) -> bool
    async def commit(self) -> None
```

### 4.4 NoteMarkRefRepository

```python
class NoteMarkRefRepository(ABC):
    async def create(self, ref: NoteMarkRef) -> NoteMarkRef
    async def get_by_pair(self, note_id: str, mark_id: str) -> NoteMarkRef | None
    async def list_by_note(self, note_id: str) -> list[NoteMarkRef]
    async def list_marks_by_note(self, note_id: str) -> list[Mark]
    async def delete_by_pair(self, note_id: str, mark_id: str) -> bool
    async def commit(self) -> None
```

## 5. 设计要点

### 5.1 幂等性

add_document_tag 和 add_mark_ref 采用 upsert 语义。由于表中有 UNIQUE 约束，重复插入时捕获 IntegrityError 并返回已有记录，而非抛出异常。这简化了前端的调用逻辑。

### 5.2 auto-save 兼容

update_note 的 partial update 设计（只更新非 None 字段）确保 auto-save 调用不会意外清空未传入的字段。前端可以每 5 秒只发送 content 字段的增量。

### 5.3 anchor_text 不可变

Mark 创建后 anchor_text 和 char_offset 不可变。这两个字段共同构成书签的位置标识，修改它们等同于创建新书签。仅 comment 字段可更新。

### 5.4 count_by_document 用途

MarkService.count_by_document 为现有的 DocumentService.delete_document 流程提供 affected_marks_count。前端在删除文档的确认对话框中展示此信息。该方法不改变现有 DocumentService 的代码结构，仅在 API 层组合调用。
