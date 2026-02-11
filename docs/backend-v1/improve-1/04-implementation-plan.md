# 实现计划

## 1. 任务概览

### 1.1 任务分组

| 分组 | 任务数 | 优先级 | 描述 |
|------|--------|--------|------|
| Phase 1: 数据模型 | 3 | P0 | 状态枚举、实体变更、数据库迁移 |
| Phase 2: 存储层 | 2 | P0 | 文件存储结构改造 |
| Phase 3: 服务层 | 4 | P0 | 核心业务逻辑实现 |
| Phase 4: API层 | 4 | P0 | 端点实现与废弃 |
| Phase 5: 任务层 | 2 | P0 | Celery 任务改造 |
| Phase 6: 测试 | 3 | P1 | 单元测试、集成测试 |

### 1.2 依赖关系

```
Phase 1 ─────────────────────────────────┐
    │                                    │
    ▼                                    │
Phase 2                                  │
    │                                    │
    ▼                                    │
Phase 3 ◄────────────────────────────────┘
    │
    ▼
Phase 4
    │
    ▼
Phase 5
    │
    ▼
Phase 6
```

## 2. Phase 1: 数据模型

### Task 1.1: DocumentStatus 枚举变更

**文件**：`newbee_notebook/domain/value_objects/document_status.py`

**变更内容**：
```python
class DocumentStatus(Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"       # 新增
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
```

**验收标准**：
- [ ] 添加 UPLOADED 状态
- [ ] 更新相关文档字符串

---

### Task 1.2: Document 实体变更

**文件**：`newbee_notebook/domain/entities/document.py`

**变更内容**：
- 移除 `notebook_id` 字段（或标记为废弃）
- 将 `library_id` 改为必填
- 添加状态转换方法

```python
def mark_uploaded(self) -> None:
    """标记为已上传状态"""
    self.status = DocumentStatus.UPLOADED
    self.touch()
```

**验收标准**：
- [ ] library_id 字段标记为必填
- [ ] 添加 mark_uploaded 方法
- [ ] 添加 is_uploaded 属性

---

### Task 1.3: 数据库迁移

**文件**：新建 Alembic 迁移脚本

**变更内容**：
1. 添加 `uploaded` 状态到枚举类型
2. 迁移现有 `notebook_id` 数据到 `notebook_document_refs`
3. 更新现有 PENDING 文档状态

**验收标准**：
- [ ] 迁移脚本可正常执行
- [ ] 迁移可回滚
- [ ] 现有数据正确迁移

## 3. Phase 2: 存储层

### Task 2.1: 修改文件保存逻辑

**文件**：`newbee_notebook/infrastructure/storage/local_storage.py`

**变更内容**：

```python
def save_upload_file(
    upload: UploadFile,
    document_id: str,           # 新增参数
    base_root: Optional[str] = None,
) -> Tuple[str, int, str]:
    """
    保存上传文件到 {document_id}/original/ 目录
    
    返回：(相对路径, 文件大小, 扩展名)
    """
    base_root = base_root or get_documents_directory()
    
    # 验证文件类型
    filename = _decode_filename(upload.filename)
    stem, suffix = os.path.splitext(filename)
    ext = suffix.lower().lstrip(".")
    
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: .{ext}")
    
    # 创建目录 {document_id}/original/
    dest_dir = Path(base_root) / document_id / "original"
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存文件（保留原始文件名）
    dest_path = dest_dir / filename
    
    # 处理文件名冲突
    if dest_path.exists():
        dest_path = dest_dir / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
    
    with dest_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    
    size = dest_path.stat().st_size
    rel_path = dest_path.relative_to(base_root).as_posix()
    
    return rel_path, size, ext
```

**验收标准**：
- [ ] 文件保存到正确目录
- [ ] 返回相对路径格式正确
- [ ] 文件名冲突处理正确

---

### Task 2.2: 修改 Markdown 保存逻辑

**文件**：`newbee_notebook/infrastructure/document_processing/store.py`

**变更内容**：

```python
def save_markdown(
    document_id: str,
    markdown: str,
    *,
    images: Optional[Sequence[bytes]] = None,
    base_root: Optional[str] = None,
) -> tuple[str, int]:
    """
    保存 Markdown 到 {document_id}/markdown/content.md
    """
    root = Path(base_root or get_documents_directory())
    doc_dir = root / document_id / "markdown"  # 变更：添加 markdown 子目录
    doc_dir.mkdir(parents=True, exist_ok=True)
    
    content_path = doc_dir / "content.md"
    content_bytes = markdown.encode("utf-8")
    content_path.write_bytes(content_bytes)
    
    # 图片保存到 {document_id}/images/（保持不变）
    if images:
        images_dir = root / document_id / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        for idx, image_bytes in enumerate(images):
            if isinstance(image_bytes, (bytes, bytearray)):
                (images_dir / f"{idx:03d}.bin").write_bytes(bytes(image_bytes))
    
    rel_path = content_path.relative_to(root).as_posix()
    return rel_path, len(content_bytes)
```

**验收标准**：
- [ ] Markdown 保存到正确目录
- [ ] 图片保存到正确目录
- [ ] 返回路径格式正确

## 4. Phase 3: 服务层

### Task 3.1: 修改上传服务

**文件**：`newbee_notebook/application/services/document_service.py`

**变更内容**：
- 修改 `save_upload_and_register` 方法
- 只保存文件，不触发处理
- 设置状态为 UPLOADED

```python
async def upload_to_library(
    self,
    files: List[UploadFile],
) -> List[Document]:
    """
    批量上传文件到 Library
    
    只保存文件，不触发转换和 Embedding
    """
    library = await self.library_service.get_or_create()
    documents = []
    
    for file in files:
        document_id = generate_uuid()
        
        # 保存文件
        file_path, file_size, ext = save_upload_file(
            file, 
            document_id=document_id
        )
        
        # 创建文档记录
        document = Document(
            document_id=document_id,
            title=file.filename,
            content_type=DocumentType.from_extension(ext),
            file_path=file_path,
            file_size=file_size,
            status=DocumentStatus.UPLOADED,
            library_id=library.library_id,
        )
        
        await self.document_repo.save(document)
        documents.append(document)
    
    return documents
```

**验收标准**：
- [ ] 支持批量上传
- [ ] 文件保存到正确位置
- [ ] 状态设置为 UPLOADED
- [ ] 不触发处理任务

---

### Task 3.2: 新增 NotebookDocumentService

**文件**：新建 `newbee_notebook/application/services/notebook_document_service.py`

**内容**：

```python
class NotebookDocumentService:
    """Notebook 文档关联服务"""
    
    async def add_documents(
        self,
        notebook_id: str,
        document_ids: List[str],
    ) -> AddDocumentsResult:
        """
        添加文档到 Notebook
        
        返回：添加成功、跳过、失败的文档列表
        """
        pass
    
    async def list_documents(
        self,
        notebook_id: str,
        limit: int = 20,
        offset: int = 0,
        status: Optional[DocumentStatus] = None,
    ) -> Tuple[List[Document], int]:
        """
        列出 Notebook 的文档
        """
        pass
    
    async def remove_document(
        self,
        notebook_id: str,
        document_id: str,
    ) -> None:
        """
        从 Notebook 移除文档（仅解除关联）
        """
        pass
```

**验收标准**：
- [ ] 实现添加文档逻辑
- [ ] 实现列出文档逻辑
- [ ] 实现移除文档逻辑
- [ ] 添加时触发处理任务

---

### Task 3.3: 修改删除服务

**文件**：`newbee_notebook/application/services/document_service.py`

**变更内容**：

```python
async def delete_document(
    self,
    document_id: str,
    force: bool = False,
) -> DeleteResult:
    """
    完全删除文档
    
    包括：文件、向量、索引、数据库记录
    """
    document = await self.document_repo.get(document_id)
    if not document:
        raise DocumentNotFoundError(document_id)
    
    # 检查引用
    refs = await self.ref_repo.list_by_document(document_id)
    if refs and not force:
        raise DocumentHasReferencesError(document_id, len(refs))
    
    # 删除引用
    refs_removed = 0
    if refs:
        await self.ref_repo.delete_by_document(document_id)
        refs_removed = len(refs)
    
    # 异步删除向量数据
    delete_document_data_task.delay(document_id)
    
    # 同步删除文件
    files_deleted = await self._delete_document_files(document_id)
    
    # 删除数据库记录
    await self.document_repo.delete(document_id)
    
    return DeleteResult(
        document_id=document_id,
        files_deleted=files_deleted,
        references_removed=refs_removed,
    )

async def _delete_document_files(self, document_id: str) -> bool:
    """删除文档的所有文件"""
    doc_dir = Path(get_documents_directory()) / document_id
    if doc_dir.exists():
        shutil.rmtree(doc_dir)
        return True
    return False
```

**验收标准**：
- [ ] 检查并处理引用
- [ ] 删除文件系统目录
- [ ] 异步删除向量数据
- [ ] 删除数据库记录
- [ ] 返回清理结果

---

### Task 3.4: 新增下载服务

**文件**：`newbee_notebook/application/services/document_service.py`

**变更内容**：

```python
async def get_download_path(
    self,
    document_id: str,
) -> Tuple[Path, str]:
    """
    获取原始文件下载路径
    
    返回：(文件路径, 文件名)
    """
    document = await self.document_repo.get(document_id)
    if not document:
        raise DocumentNotFoundError(document_id)
    
    file_path = Path(get_documents_directory()) / document.file_path
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {document.file_path}")
    
    filename = file_path.name
    return file_path, filename
```

**验收标准**：
- [ ] 返回正确的文件路径
- [ ] 返回原始文件名
- [ ] 文件不存在时抛出异常

## 5. Phase 4: API 层

### Task 4.1: 修改上传端点

**文件**：`newbee_notebook/api/routes/documents.py`

**变更内容**：
- 修改为支持批量上传
- 移除处理触发逻辑

```python
@router.post("/library/upload", status_code=201)
async def upload_to_library(
    files: List[UploadFile] = File(...),
    document_service: DocumentService = Depends(),
):
    """批量上传文档到 Library"""
    documents = await document_service.upload_to_library(files)
    return {
        "documents": [doc.to_dict() for doc in documents],
        "total": len(documents),
        "failed": [],
    }
```

**验收标准**：
- [ ] 支持多文件上传
- [ ] 返回格式正确
- [ ] 不触发处理

---

### Task 4.2: 新增 Notebook 文档端点

**文件**：新建 `newbee_notebook/api/routes/notebook_documents.py`

**内容**：

```python
router = APIRouter(prefix="/notebooks/{notebook_id}/documents")

@router.post("")
async def add_documents(
    notebook_id: str,
    request: AddDocumentsRequest,
    service: NotebookDocumentService = Depends(),
):
    """添加文档到 Notebook"""
    pass

@router.get("")
async def list_documents(
    notebook_id: str,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    service: NotebookDocumentService = Depends(),
):
    """列出 Notebook 文档"""
    pass

@router.delete("/{document_id}")
async def remove_document(
    notebook_id: str,
    document_id: str,
    service: NotebookDocumentService = Depends(),
):
    """从 Notebook 移除文档"""
    pass
```

**验收标准**：
- [ ] 实现添加端点
- [ ] 实现列出端点
- [ ] 实现移除端点
- [ ] 注册到主路由

---

### Task 4.3: 新增下载端点

**文件**：`newbee_notebook/api/routes/documents.py`

**变更内容**：

```python
@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    document_service: DocumentService = Depends(),
):
    """下载原始文件"""
    file_path, filename = await document_service.get_download_path(document_id)
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )
```

**验收标准**：
- [ ] 返回文件流
- [ ] 设置正确的文件名
- [ ] 404 处理正确

---

### Task 4.4: 废弃 Notebook 上传端点

**文件**：`newbee_notebook/api/routes/documents.py`

**变更内容**：

```python
@router.post("/notebooks/{notebook_id}/upload", deprecated=True)
async def upload_to_notebook_deprecated(
    notebook_id: str,
):
    """
    [已废弃] 直接上传到 Notebook
    
    请使用：
    1. POST /documents/library/upload 上传到 Library
    2. POST /notebooks/{id}/documents 添加到 Notebook
    """
    raise HTTPException(
        status_code=410,
        detail="This endpoint is deprecated. Use POST /documents/library/upload instead.",
    )
```

**验收标准**：
- [ ] 返回 410 状态码
- [ ] 提供迁移指引

## 6. Phase 5: 任务层

### Task 5.1: 修改处理任务

**文件**：`newbee_notebook/infrastructure/tasks/document_tasks.py`

**变更内容**：
- 处理任务不再由上传触发
- 由添加到 Notebook 触发
- 增加状态检查防止重复处理

```python
@celery_app.task(bind=True, max_retries=3)
def process_document_task(self, document_id: str):
    """处理文档：转换 + Embedding + 索引"""
    
    # 获取文档并加锁
    with document_lock(document_id):
        document = get_document(document_id)
        
        # 检查状态
        if document.status == DocumentStatus.COMPLETED:
            return {"status": "skipped", "reason": "already_completed"}
        
        if document.status == DocumentStatus.PROCESSING:
            return {"status": "skipped", "reason": "already_processing"}
        
        # 更新状态
        document.mark_processing()
        save_document(document)
    
    try:
        # 执行处理
        # ... 转换、分块、Embedding、索引 ...
        
        document.mark_completed(
            chunk_count=chunk_count,
            page_count=page_count,
            content_path=content_path,
            content_size=content_size,
        )
        save_document(document)
        
        return {"status": "completed", "chunk_count": chunk_count}
        
    except Exception as e:
        document.mark_failed(str(e))
        save_document(document)
        raise
```

**验收标准**：
- [ ] 状态检查防止重复
- [ ] 使用锁防止并发
- [ ] 失败时正确记录

---

### Task 5.2: 新增清理任务

**文件**：`newbee_notebook/infrastructure/tasks/document_tasks.py`

**变更内容**：

```python
@celery_app.task
def delete_document_data_task(document_id: str):
    """
    异步清理文档的向量数据
    """
    # 删除 pgvector 向量
    try:
        pg_index = load_pgvector_index()
        pg_index.delete_ref_doc(document_id)
    except Exception as e:
        logger.warning(f"Failed to delete pgvector nodes: {e}")
    
    # 删除 Elasticsearch 索引
    try:
        es_index = load_es_index()
        es_index.delete_ref_doc(document_id)
    except Exception as e:
        logger.warning(f"Failed to delete ES nodes: {e}")
    
    return {"status": "completed", "document_id": document_id}
```

**验收标准**：
- [ ] 删除 pgvector 数据
- [ ] 删除 ES 数据
- [ ] 错误时记录警告但不阻断

## 7. Phase 6: 测试

### Task 6.1: 单元测试

**文件**：新建测试文件

**测试范围**：
- DocumentStatus 枚举
- 文件存储路径生成
- Document 实体方法

**验收标准**：
- [ ] 状态转换测试
- [ ] 路径格式测试
- [ ] 边界条件测试

---

### Task 6.2: 服务层测试

**文件**：新建测试文件

**测试范围**：
- 上传服务
- 添加文档服务
- 删除服务

**验收标准**：
- [ ] Mock 数据库操作
- [ ] Mock 文件系统操作
- [ ] 异常情况测试

---

### Task 6.3: 集成测试

**文件**：新建测试文件

**测试范围**：
- 完整上传 -> 添加 -> 删除流程
- API 端点测试

**验收标准**：
- [ ] 端到端流程测试
- [ ] 状态流转正确
- [ ] 数据清理完整

## 8. 检查清单

### 8.1 代码变更

- [ ] DocumentStatus 添加 UPLOADED
- [ ] Document 实体变更
- [ ] 数据库迁移脚本
- [ ] local_storage.py 修改
- [ ] store.py 修改
- [ ] document_service.py 修改
- [ ] 新建 notebook_document_service.py
- [ ] documents.py 路由修改
- [ ] 新建 notebook_documents.py 路由
- [ ] document_tasks.py 修改
- [ ] 主路由注册新端点

### 8.2 文档更新

- [ ] API 文档更新
- [ ] Postman Collection 更新
- [ ] README 更新

### 8.3 测试验证

- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 手动测试验证

### 8.4 部署

- [ ] 数据库迁移执行
- [ ] 服务重启
- [ ] 功能验证
