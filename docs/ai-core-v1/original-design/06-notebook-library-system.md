# Notebook 和 Library 系统设计

## 1. 系统概述

MediMind Agent 采用 **Notebook + Library 双轨文档管理机制**，提供灵活的资料组织和智能对话能力。

### 1.1 核心概念

**Library（独立文档库）**
- 用户的文档仓库，集中管理所有资料
- 全局唯一，每个部署实例一个
- 文档可以被多个 Notebook 引用
- 作为资料的"存储池"

**Notebook（笔记本）**
- 用户的工作空间，围绕特定主题组织资料
- 可以创建多个，数量不限
- 支持从 Library 引用文档
- 支持直接上传专属文档
- 包含 Session（对话会话）

**Session（对话会话）**
- 在 Notebook 上下文中进行的对话
- 每个 Notebook 最多 20 个 Session
- 支持 4 种交互模式

### 1.2 设计目标

- 灵活的文档组织方式
- 清晰的资料归属关系
- 高效的 RAG 检索
- 良好的用户体验

### 1.3 设计原则

- 开源优先，单用户模式
- 简化部署，开箱即用
- 遵循 SOLID、DRY、KISS、YAGNI

## 2. 文档管理模型

### 2.1 双轨制文档结构

```
┌─────────────────────────────────────────────────────────────┐
│                    Library (文档仓库)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ doc-A.pdf │  │doc-B.docx│  │video-url │  │doc-C.xlsx│    │
│  └─────┬────┘  └─────┬────┘  └────┬─────┘  └──────────┘    │
│        │             │            │                         │
└────────┼─────────────┼────────────┼─────────────────────────┘
         │             │            │
    ┌────┴────┐   ┌────┴────┐  ┌───┴────┐
    ▼         ▼   ▼         ▼  ▼        ▼
┌─────────────────┐  ┌─────────────────┐
│   Notebook A    │  │   Notebook B    │
│ ┌─────────────┐ │  │ ┌─────────────┐ │
│ │[引用]doc-A  │ │  │ │[引用]doc-A  │ │
│ │[引用]video  │ │  │ │[引用]doc-B  │ │
│ │专属-doc-X   │ │  │ │专属-doc-Y   │ │
│ └─────────────┘ │  │ └─────────────┘ │
│ ┌─────────────┐ │  │ ┌─────────────┐ │
│ │  Sessions   │ │  │ │  Sessions   │ │
│ │ (max 20)    │ │  │ │ (max 20)    │ │
│ └─────────────┘ │  │ └─────────────┘ │
└─────────────────┘  └─────────────────┘
```

### 2.2 文档归属规则

| 上传方式 | 归属 | 可引用性 | 删除行为 |
|---------|------|----------|----------|
| 通过 Library 页面上传 | Library | 可被多个 Notebook 引用 | 提示并解除引用后删除 |
| 通过 Notebook 内部上传 | Notebook（专属）| 只属于该 Notebook | 删除 Notebook 时一并删除 |

### 2.3 引用机制

**从 Library 引用到 Notebook**
- 软引用，不复制文档
- 同一文档可被多个 Notebook 引用
- 引用后，文档纳入该 Notebook 的 RAG 检索范围
- 取消引用不影响 Library 中的文档

**引用关系表**
- notebook_document_refs 表记录引用关系
- 包含：notebook_id, document_id, created_at

## 3. Session 管理

### 3.1 Session 规则

**数量限制**
- 每个 Notebook 最多 20 个 Session
- 达到上限后拒绝创建新 Session
- 用户可以删除旧 Session 释放配额
- 也可以创建新 Notebook

**恢复逻辑**
- 打开 Notebook 时默认恢复最近的 Session
- 前端提供"新建 Session"按钮
- 用户可以选择任意历史 Session

### 3.2 Session 生命周期

```
打开 Notebook
      │
      ▼
┌─────────────┐
│ 检查 Session │
└──────┬──────┘
       │
  ┌────┴────┐
  ▼         ▼
有 Session   无 Session
  │              │
  ▼              ▼
恢复最近    创建新 Session
  │              │
  └──────┬───────┘
         ▼
  ┌────────────┐
  │  对话交互   │
  │ (4种模式)  │
  └──────┬─────┘
         │
         ▼
  消息自动保存
         │
         ▼
  关闭 Notebook
  (Session 保留)
```

### 3.3 四种交互模式

所有模式在 Notebook 上下文中运行：

| 模式 | 说明 | 触发方式 | RAG 范围 |
|------|------|----------|----------|
| **Chat** | 自由对话 + 工具调用 | 对话框输入 | Notebook 文档（可选）|
| **Ask** | 深度问答 + 混合检索 | 对话框输入 | Notebook 文档 |
| **Explain** | 概念讲解 | 右键"讲解" | 选中内容 + 相关上下文 |
| **Conclude** | 内容总结 | 右键"总结" | 选中内容 |

## 4. 数据模型

### 4.1 实体关系图

```
┌─────────┐       ┌──────────┐       ┌──────────┐
│ Library │       │ Notebook │       │ Session  │
│─────────│       │──────────│       │──────────│
│ id      │       │ id       │◄──────│ id       │
│ created │       │ title    │  1:N  │ notebook │
│ updated │       │ desc     │       │ title    │
└────┬────┘       │ created  │       │ messages │
     │            │ updated  │       │ created  │
     │            └────┬─────┘       └──────────┘
     │                 │
     │      ┌──────────┴───────────┐
     │      │                      │
     ▼      ▼                      ▼
┌──────────────┐          ┌───────────────────┐
│   Document   │          │NotebookDocumentRef│
│──────────────│          │───────────────────│
│ id           │◄─────────│ id                │
│ library_id   │   1:N    │ notebook_id       │
│ notebook_id  │          │ document_id       │
│ title        │          │ created_at        │
│ content_type │          └───────────────────┘
│ file_path    │
│ url          │
│ status       │
└──────────────┘
        │
        │ 文档块存储在 LlamaIndex 表
        │ (data_documents_*)
        ▼
┌─────────────────────────┐
│ LlamaIndex Vector Table │
│─────────────────────────│
│ id (BIGSERIAL)          │
│ text                    │
│ metadata_ (含document_id)│
│ node_id                 │
│ embedding               │
└─────────────────────────┘
```

### 4.2 Library 实体

```python
@dataclass
class Library:
    library_id: str
    document_count: int
    created_at: datetime
    updated_at: datetime
```

**说明**：
- 全局唯一，每个部署实例一个
- 主要作为文档的聚合根

### 4.3 Notebook 实体

```python
@dataclass
class Notebook:
    notebook_id: str
    title: str
    description: Optional[str]
    session_count: int
    document_count: int  # 包括专属文档 + 引用文档
    created_at: datetime
    updated_at: datetime
```

**业务规则**：
- 数量不限
- 删除时级联删除专属文档和所有 Session
- session_count 上限为 20

### 4.4 Document 实体

```python
@dataclass
class Document:
    document_id: str
    library_id: Optional[str]     # 属于 Library
    notebook_id: Optional[str]    # 属于 Notebook（专属文档）
    title: str
    content_type: str             # pdf, docx, xlsx, youtube, bilibili
    file_path: Optional[str]
    url: Optional[str]
    status: DocumentStatus        # processing, completed, failed
    page_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime
```

**业务规则**：
- library_id 和 notebook_id 互斥，不能同时有值
- library_id 有值：属于 Library
- notebook_id 有值：属于 Notebook（专属文档）

### 4.5 Session 实体

```python
@dataclass
class Session:
    session_id: str
    notebook_id: str
    title: Optional[str]
    message_count: int
    context_summary: Optional[str]  # 压缩后的历史消息摘要
    created_at: datetime
    updated_at: datetime
```

**业务规则**：
- 必须属于一个 Notebook
- 每个 Notebook 最多 20 个 Session
- 当消息超过 10 轮（20 条）时，旧消息压缩为摘要存入 `context_summary`

### 4.6 NotebookDocumentRef 实体

```python
@dataclass
class NotebookDocumentRef:
    reference_id: str
    notebook_id: str
    document_id: str              # 指向 Library 中的文档
    created_at: datetime
```

**业务规则**：
- 只能引用 Library 中的文档
- 同一文档可被多个 Notebook 引用

## 5. 核心业务流程

### 5.1 创建 Notebook

```
用户点击"新建 Notebook"
         │
         ▼
  输入标题和描述
         │
         ▼
  POST /api/v1/notebooks
         │
         ▼
  创建 Notebook 记录
         │
         ▼
  返回 Notebook 信息
         │
         ▼
  跳转到 Notebook 页面
```

### 5.2 上传文档到 Library

```
用户在 Library 页面点击"上传"
         │
         ▼
  选择文件 或 输入视频 URL
         │
         ▼
  POST /api/v1/library/documents/upload
         │
         ▼
  创建 Document 记录 (library_id = xxx)
         │
         ▼
  提交 Celery 异步任务
         │
         ▼
    ┌────────────────────────┐
    │ 内容提取 → 分块 → 嵌入 │
    └────────────────────────┘
         │
         ▼
  更新文档状态为 completed
```

### 5.3 上传文档到 Notebook（专属）

```
用户在 Notebook 内点击"上传"
         │
         ▼
  选择文件 或 输入视频 URL
         │
         ▼
  POST /api/v1/notebooks/{id}/documents/upload
         │
         ▼
  创建 Document 记录 (notebook_id = xxx)
         │
         ▼
  提交 Celery 异步任务
         │
         ▼
    ┌────────────────────────┐
    │ 内容提取 → 分块 → 嵌入 │
    └────────────────────────┘
         │
         ▼
  更新文档状态为 completed
```

### 5.4 从 Library 引用文档到 Notebook

```
用户在 Notebook 内点击"从资料库选择"
         │
         ▼
  显示 Library 文档列表
         │
         ▼
  用户选择一个或多个文档
         │
         ▼
  POST /api/v1/notebooks/{id}/references
         │
         ▼
  创建 NotebookDocumentRef 记录
         │
         ▼
  文档纳入 Notebook 的 RAG 范围
```

### 5.5 在 Notebook 中对话

```
用户打开 Notebook
         │
         ▼
  获取最近 Session 或创建新 Session
         │
         ▼
  用户输入消息，选择模式
         │
         ▼
  POST /api/v1/notebooks/{id}/chat/stream
         │
         ├────────────────────────────┐
         ▼                            │
  获取 Notebook 文档列表              │
  (专属文档 + 引用文档)               │
         │                            │
         ▼                            │
  ContextBuilder 构建上下文           │
  (限定在 Notebook 文档范围)          │
         │                            │
         ▼                            │
  RAG 检索 + LLM 生成                 │
         │                            │
         ▼                            │
  流式返回 (SSE) ──────────────────────┘
```

### 5.6 删除 Notebook

```
用户点击"删除 Notebook"
         │
         ▼
  确认删除对话框
         │
         ▼
  DELETE /api/v1/notebooks/{id}
         │
         ▼
  ┌──────────────────────────────┐
  │ 1. 删除所有 Session           │
  │ 2. 删除专属文档及其 Chunks    │
  │ 3. 删除引用关系               │
  │ 4. 删除 Notebook 记录         │
  └──────────────────────────────┘
         │
         ▼
  返回成功
```

### 5.7 删除 Library 文档

```
用户点击"删除文档"
         │
         ▼
  DELETE /api/v1/library/documents/{id}
         │
         ▼
  检查是否被 Notebook 引用
         │
    ┌────┴────┐
    ▼         ▼
  无引用    有引用
    │         │
    ▼         ▼
  直接删除  提示用户
    │     "该文档被 X 个
    │      Notebook 引用，
    │      确认删除？"
    │         │
    │    ┌────┴────┐
    │    ▼         ▼
    │  取消      确认
    │    │         │
    │    ▼         ▼
    │  保留   自动解除引用
    │            │
    │            ▼
    │         删除文档
    │            │
    └─────┬──────┘
          ▼
       返回结果
```

### 5.8 创建 Session（含上限检查）

```
用户点击"新建对话"
         │
         ▼
  POST /api/v1/notebooks/{id}/sessions
         │
         ▼
  查询当前 session_count
         │
    ┌────┴────┐
    ▼         ▼
  < 20      >= 20
    │         │
    ▼         ▼
  创建     返回错误
  Session  SESSION_LIMIT_EXCEEDED
    │      "已达上限，请删除
    │       旧 Session 或
    │       新建 Notebook"
    │
    ▼
  返回 Session 信息
```

## 6. RAG 检索范围

### 6.1 检索策略

在 Notebook 上下文中进行对话时，RAG 检索遵循以下规则：

**检索范围**
```python
def get_notebook_documents(notebook_id: str) -> List[Document]:
    """获取 Notebook 的所有可检索文档"""
    
    # 1. 获取专属文档
    owned_docs = Document.query.filter(
        Document.notebook_id == notebook_id,
        Document.status == "completed"
    ).all()
    
    # 2. 获取引用的 Library 文档
    ref_doc_ids = NotebookDocumentRef.query.filter(
        NotebookDocumentRef.notebook_id == notebook_id
    ).values("document_id")
    
    referenced_docs = Document.query.filter(
        Document.id.in_(ref_doc_ids),
        Document.status == "completed"
    ).all()
    
    return owned_docs + referenced_docs
```

### 6.2 检索流程

```
用户提问
    │
    ▼
获取 Notebook 文档列表
    │
    ▼
提取文档的 chunk_ids
    │
    ▼
向量检索 (限定 chunk_ids)
    │
    ▼
全文检索 (限定 document_ids)
    │
    ▼
RRF 融合排序
    │
    ▼
返回 Top-K 结果
```

### 6.3 检索模式

| 模式 | 向量检索 | 全文检索 | 融合 |
|------|----------|----------|------|
| vector | ✓ | ✗ | ✗ |
| text | ✗ | ✓ | ✗ |
| hybrid | ✓ | ✓ | RRF |

## 7. 数据库表设计

### 7.1 library 表

```sql
CREATE TABLE library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 7.2 notebooks 表

```sql
CREATE TABLE notebooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    session_count INTEGER DEFAULT 0,
    document_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notebooks_created_at ON notebooks(created_at);
CREATE INDEX idx_notebooks_updated_at ON notebooks(updated_at);
```

### 7.3 documents 表

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    library_id UUID REFERENCES library(id),
    notebook_id UUID REFERENCES notebooks(id),
    title VARCHAR(500) NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    file_path VARCHAR(1000),
    url VARCHAR(2000),
    status VARCHAR(20) DEFAULT 'processing',
    page_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- library_id 和 notebook_id 不能同时有值
    CONSTRAINT check_document_owner CHECK (
        (library_id IS NULL) != (notebook_id IS NULL)
        OR (library_id IS NULL AND notebook_id IS NULL)
    )
);

CREATE INDEX idx_documents_library_id ON documents(library_id);
CREATE INDEX idx_documents_notebook_id ON documents(notebook_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_created_at ON documents(created_at);
```

### 7.4 notebook_document_refs 表

```sql
CREATE TABLE notebook_document_refs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(notebook_id, document_id)
);

CREATE INDEX idx_refs_notebook_id ON notebook_document_refs(notebook_id);
CREATE INDEX idx_refs_document_id ON notebook_document_refs(document_id);
```

### 7.5 sessions 表

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    title VARCHAR(500),
    message_count INTEGER DEFAULT 0,
    context_summary TEXT,  -- 压缩后的历史消息摘要
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_notebook_id ON sessions(notebook_id);
CREATE INDEX idx_sessions_created_at ON sessions(created_at);
CREATE INDEX idx_sessions_updated_at ON sessions(updated_at);
```

> **注意**：`context_summary` 用于存储压缩后的历史消息摘要。当对话超过 10 轮（20 条消息）时，
> 系统会将旧消息压缩为摘要并存储在此字段，保留最近 5 轮原始消息。

## 8. 仓储接口设计

### 8.1 LibraryRepository

```python
class LibraryRepository(ABC):
    @abstractmethod
    async def get(self) -> Library:
        """获取 Library"""
    
    @abstractmethod
    async def get_documents(
        self,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Document], int]:
        """获取 Library 文档列表"""
    
    @abstractmethod
    async def get_document_reference_count(
        self,
        document_id: str
    ) -> int:
        """获取文档被引用次数"""
```

### 8.2 NotebookRepository

```python
class NotebookRepository(ABC):
    @abstractmethod
    async def create(self, notebook: Notebook) -> Notebook:
        """创建 Notebook"""
    
    @abstractmethod
    async def get(self, notebook_id: str) -> Optional[Notebook]:
        """获取 Notebook"""
    
    @abstractmethod
    async def list(
        self,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Notebook], int]:
        """获取 Notebook 列表"""
    
    @abstractmethod
    async def update(self, notebook: Notebook) -> Notebook:
        """更新 Notebook"""
    
    @abstractmethod
    async def delete(self, notebook_id: str) -> None:
        """删除 Notebook（级联删除）"""
    
    @abstractmethod
    async def get_documents(
        self,
        notebook_id: str
    ) -> List[Document]:
        """获取 Notebook 的所有文档（专属 + 引用）"""
    
    @abstractmethod
    async def add_document_reference(
        self,
        notebook_id: str,
        document_id: str
    ) -> NotebookDocumentRef:
        """添加文档引用"""
    
    @abstractmethod
    async def remove_document_reference(
        self,
        notebook_id: str,
        reference_id: str
    ) -> None:
        """移除文档引用"""
    
    @abstractmethod
    async def get_session_count(
        self,
        notebook_id: str
    ) -> int:
        """获取 Session 数量"""
```

### 8.3 SessionRepository

```python
class SessionRepository(ABC):
    @abstractmethod
    async def create(self, session: Session) -> Session:
        """创建 Session"""
    
    @abstractmethod
    async def get(self, session_id: str) -> Optional[Session]:
        """获取 Session"""
    
    @abstractmethod
    async def get_latest(
        self,
        notebook_id: str
    ) -> Optional[Session]:
        """获取最近的 Session"""
    
    @abstractmethod
    async def list_by_notebook(
        self,
        notebook_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Session], int]:
        """获取 Notebook 的 Session 列表"""
    
    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """删除 Session"""
```

## 9. 应用服务设计

### 9.1 LibraryService

```python
class LibraryService:
    async def get_library(self) -> Library:
        """获取 Library 信息"""
    
    async def upload_document(
        self,
        file: UploadFile = None,
        url: str = None,
        title: str = None
    ) -> Document:
        """上传文档到 Library"""
    
    async def delete_document(
        self,
        document_id: str,
        confirm: bool = False
    ) -> DeleteResult:
        """删除文档，如有引用需确认"""
```

### 9.2 NotebookService

```python
class NotebookService:
    async def create_notebook(
        self,
        title: str,
        description: str = None
    ) -> Notebook:
        """创建 Notebook"""
    
    async def delete_notebook(
        self,
        notebook_id: str
    ) -> None:
        """删除 Notebook（级联删除专属文档）"""
    
    async def upload_document(
        self,
        notebook_id: str,
        file: UploadFile = None,
        url: str = None,
        title: str = None
    ) -> Document:
        """上传专属文档到 Notebook"""
    
    async def reference_document(
        self,
        notebook_id: str,
        document_id: str
    ) -> NotebookDocumentRef:
        """从 Library 引用文档"""
    
    async def get_documents(
        self,
        notebook_id: str
    ) -> List[DocumentWithSource]:
        """获取所有文档（标注来源）"""
```

### 9.3 SessionService

```python
class SessionService:
    MAX_SESSIONS_PER_NOTEBOOK = 20
    
    async def create_session(
        self,
        notebook_id: str,
        title: str = None
    ) -> Session:
        """创建 Session（含上限检查）"""
        count = await self.notebook_repo.get_session_count(notebook_id)
        if count >= self.MAX_SESSIONS_PER_NOTEBOOK:
            raise SessionLimitExceededError(
                f"该 Notebook 已达到 Session 上限（{self.MAX_SESSIONS_PER_NOTEBOOK} 个）"
            )
        # 创建 Session...
    
    async def get_latest_session(
        self,
        notebook_id: str
    ) -> Optional[Session]:
        """获取最近的 Session"""
```

## 10. 配置项

### 10.1 Session 配置

```yaml
# configs/notebook.yaml
notebook:
  session:
    max_per_notebook: 20    # 每个 Notebook 最多 Session 数量
    default_title: "新对话"  # 默认 Session 标题
```

### 10.2 文档配置

```yaml
# configs/document.yaml
document:
  upload:
    max_file_size: 104857600  # 100MB
    allowed_types:
      - pdf
      - docx
      - xlsx
      - txt
      - md
      - csv
    allowed_video_hosts:
      - youtube.com
      - youtu.be
      - bilibili.com
```

## 11. 错误处理

### 11.1 业务异常

```python
class NotebookError(Exception):
    """Notebook 相关错误基类"""

class NotebookNotFoundError(NotebookError):
    """Notebook 不存在"""

class SessionLimitExceededError(NotebookError):
    """Session 数量达到上限"""

class DocumentReferencedError(NotebookError):
    """文档被引用，无法直接删除"""

class InvalidDocumentOwnerError(NotebookError):
    """文档归属无效"""
```

### 11.2 错误码映射

| 异常 | HTTP 状态码 | 错误码 |
|------|------------|--------|
| NotebookNotFoundError | 404 | NOT_FOUND |
| SessionLimitExceededError | 409 | SESSION_LIMIT_EXCEEDED |
| DocumentReferencedError | 409 | DOCUMENT_REFERENCED |
| InvalidDocumentOwnerError | 400 | INVALID_REQUEST |

## 12. 测试策略

### 12.1 单元测试

- NotebookService.create_notebook()
- NotebookService.delete_notebook()（级联删除）
- SessionService.create_session()（上限检查）
- LibraryService.delete_document()（引用检查）

### 12.2 集成测试

- 上传文档到 Library → 引用到 Notebook → 对话
- 删除 Notebook → 验证专属文档已删除
- 删除被引用的 Library 文档 → 验证引用已解除
- 创建第 21 个 Session → 验证拒绝

### 12.3 E2E 测试

- 完整的 Notebook 工作流
- 文档管理工作流
- Session 管理工作流

## 13. 未来扩展

### 13.1 多用户支持

如需支持多用户，可扩展：
- 增加 User 实体
- Library 和 Notebook 增加 user_id
- 增加认证和权限控制

### 13.2 协作功能

- Notebook 分享
- 多人协作编辑
- 评论和标注

### 13.3 高级功能

- Notebook 模板
- 文档自动分类
- 智能推荐相关文档
