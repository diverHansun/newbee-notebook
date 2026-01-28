# 文档处理模块设计

## 1. 概述

本文档描述MediMind Agent的文档处理模块设计,包括文档上传、内容提取、Markdown转换、分chunk和向量索引的完整流程。

---

## 2. 当前实现

### 2.1 文件位置

```
medimind_agent/
├── infrastructure/
│   ├── content_extraction/
│   │   └── base.py              # 内容提取器
│   ├── tasks/
│   │   ├── celery_app.py        # Celery应用配置
│   │   └── document_tasks.py    # 文档处理任务
│   └── storage/
│       └── local_storage.py     # 本地文件存储
├── application/services/
│   └── document_service.py      # 文档服务
└── core/rag/
    ├── text_splitter/
    │   └── splitter.py          # 文本分割
    └── document_loader/
        └── loader.py            # 文档加载器
```

### 2.2 处理流程

```
文件上传
    |
    v
DocumentService.save_upload_and_register()
    |
    +--> 保存文件到 data/documents/
    +--> 创建Document实体 (status=PENDING)
    +--> 触发Celery任务
    |
    v
process_document_task (Celery)
    |
    +--> 更新状态为PROCESSING
    +--> _extract_text() 提取文本
    +--> split_documents() 分chunk
    +--> _index_nodes() 索引到pgvector和ES
    +--> 更新状态为COMPLETED
```

### 2.3 已支持的文件格式

| 格式 | 提取器 | 输出 |
|------|--------|------|
| PDF | PdfExtractor (PyPDF2) | 纯文本 |
| DOCX | DocxExtractor (docx2txt) | 纯文本 |
| XLSX/XLS | ExcelExtractor (pandas) | CSV格式文本 |
| CSV | CsvExtractor (pandas) | CSV格式文本 |
| TXT/MD | TxtExtractor | 原文本 |

---

## 3. 需要新增的功能

### 3.1 PDF转Markdown

#### 3.1.1 目标

将PDF文档转换为结构化的Markdown格式,保留:
- 标题层级
- 段落结构
- 表格
- 列表

#### 3.1.2 实现方案

使用PyMuPDF(fitz)替代PyPDF2,获取更丰富的结构信息:

```python
# infrastructure/content_extraction/pdf_markdown.py

import fitz  # PyMuPDF

class PdfMarkdownExtractor:
    def extract_to_markdown(self, path: str) -> tuple[str, int]:
        """
        提取PDF为Markdown格式

        Returns:
            (markdown_content, page_count)
        """
        doc = fitz.open(path)
        markdown_parts = []

        for page_num, page in enumerate(doc, 1):
            blocks = page.get_text("dict")["blocks"]
            page_md = self._process_blocks(blocks)
            markdown_parts.append(f"<!-- Page {page_num} -->\n{page_md}")

        doc.close()
        return "\n\n".join(markdown_parts), len(doc)

    def _process_blocks(self, blocks: list) -> str:
        """处理页面块,转换为Markdown"""
        lines = []
        for block in blocks:
            if block["type"] == 0:  # 文本块
                text = self._extract_text_block(block)
                lines.append(text)
            elif block["type"] == 1:  # 图片块
                lines.append("[图片]")
        return "\n\n".join(lines)

    def _extract_text_block(self, block: dict) -> str:
        """提取文本块,识别标题"""
        text_parts = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue

                font_size = span.get("size", 12)
                is_bold = "bold" in span.get("font", "").lower()

                # 根据字体大小判断标题级别
                if font_size >= 18:
                    text = f"# {text}"
                elif font_size >= 16:
                    text = f"## {text}"
                elif font_size >= 14 and is_bold:
                    text = f"### {text}"

                text_parts.append(text)

        return " ".join(text_parts)
```

#### 3.1.3 集成到处理流程

修改document_tasks.py:

```python
async def _process_document_async(document_id: str):
    # ... 现有代码 ...

    # 提取文本
    text, page_count = _extract_text(document.file_path)

    # 新增: 如果是PDF,额外生成Markdown
    markdown_content = None
    if document.content_type == DocumentType.PDF:
        from medimind_agent.infrastructure.content_extraction.pdf_markdown import PdfMarkdownExtractor
        extractor = PdfMarkdownExtractor()
        markdown_content, _ = extractor.extract_to_markdown(document.file_path)

    # 更新Document实体
    await doc_repo.update(
        document_id,
        content_markdown=markdown_content,  # 新字段
        # ... 其他字段
    )
```

### 3.2 Document实体扩展

#### 3.2.1 新增字段

```python
# domain/entities/document.py

@dataclass
class Document(Entity):
    # ... 现有字段 ...

    # 新增
    content_markdown: Optional[str] = None  # Markdown格式内容
    content_text: Optional[str] = None       # 纯文本内容(用于RAG)
```

#### 3.2.2 数据库迁移

```sql
ALTER TABLE documents ADD COLUMN content_markdown TEXT;
ALTER TABLE documents ADD COLUMN content_text TEXT;
```

### 3.3 存储策略

| 文件类型 | 原始文件 | content_markdown | content_text |
|----------|----------|------------------|--------------|
| PDF | 保留 | 转换的Markdown | 纯文本(RAG用) |
| DOCX | 保留 | 转换的Markdown | 纯文本 |
| XLSX/CSV | 保留 | 不转换 | CSV格式文本 |
| TXT/MD | 保留 | 原内容 | 原内容 |

---

## 4. 依赖安装

```bash
# pyproject.toml 添加
dependencies = [
    # ... 现有依赖
    "PyMuPDF>=1.23.0",  # PDF转Markdown
]
```

---

## 5. 测试验证

### 5.1 单元测试

```python
# tests/unit/test_pdf_markdown.py

def test_pdf_to_markdown():
    extractor = PdfMarkdownExtractor()
    md, pages = extractor.extract_to_markdown("test.pdf")

    assert pages > 0
    assert "# " in md or "## " in md  # 包含标题
    assert len(md) > 100
```

### 5.2 集成测试

```bash
# 上传PDF文件
curl -X POST "http://localhost:8000/api/v1/documents/library/upload" \
  -F "file=@test.pdf"

# 检查处理结果
curl "http://localhost:8000/api/v1/documents/{document_id}"
# 确认 status=completed, content_markdown 不为空
```

---

## 6. 注意事项

1. PDF结构识别不完美: PyMuPDF基于视觉布局分析,复杂排版可能识别有误
2. 中文支持: 确保字体检测对中文PDF有效
3. 大文件处理: 超过50MB的PDF考虑分页处理
4. 内存管理: 处理完毕及时close文档对象
