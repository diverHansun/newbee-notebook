# Backend-v1: 文档处理模块

## 模块概述

本模块负责将用户上传的各种格式文档(PDF、Word、Excel 等)转换为统一的 Markdown 格式,供:
1. **前端阅读器**: Markdown 渲染展示,支持用户选中文字进行 AI 交互(Explain/Conclude 模式)
2. **RAG 系统**: 基于 Markdown 格式进行文本分块和向量索引(PgVector)
3. **ES 搜索**: 基于 Markdown 格式进行全文检索索引

**设计核心**: 统一使用 Markdown 作为中间格式,前端选中的文字与 RAG/ES 中的 chunk 保持一致,便于精确定位引用来源。

## 文档结构

按照 docs-plan 规范,本模块文档按以下顺序组织:

| 序号 | 文档 | 说明 |
|------|------|------|
| 01 | [goals-duty.md](./01-goals-duty.md) | 设计目标与职责边界 |
| 02 | [architecture.md](./02-architecture.md) | 模块架构设计 |
| 03 | [data-model.md](./03-data-model.md) | 核心数据模型 |
| 04 | [dfd-interface.md](./04-dfd-interface.md) | 数据流与接口定义 |
| 05 | [test.md](./05-test.md) | 测试说明 |

## 架构演进: 从多格式加载到统一 Markdown

### 当前架构 (ai-core-v1)

```
原始文档(PDF/DOCX/XLSX)
        ↓
content_extraction/base.py (PyPDF2/docx2txt/pandas 提取纯文本)
        ↓
LlamaDocument(text=纯文本)
        ↓
split_documents() 分块
        ↓
    ├── PgVector 索引
    └── Elasticsearch 索引
```

**当前实现位置**:
- Celery 任务: `medimind_agent/infrastructure/tasks/document_tasks.py`
- 内容提取: `medimind_agent/infrastructure/content_extraction/base.py`
- 文档加载: `medimind_agent/core/rag/document_loader/loader.py`

**当前问题**:
1. 纯文本提取丢失原文档结构(标题层级、表格格式)
2. 前端无法直接展示提取后的纯文本(无格式)
3. 前端选中的文字无法与 RAG chunk 精确对应

### 新架构 (backend-v1)

```
原始文档(PDF/DOCX/XLSX)
        ↓
文档处理模块(MinerU/MarkItDown)
        ↓
Markdown 文件(统一中间格式,保留结构)
        ↓
存储到文件系统(data/documents/{id}/content.md)
        ↓
    ├── 前端阅读器(react-markdown 渲染)
    ├── RAG 索引(MarkdownReader 加载 → 分块 → PgVector)
    └── ES 索引(MarkdownReader 加载 → Elasticsearch)
```

**核心变化**:
1. 转换引擎变更: PyPDF2/docx2txt → MinerU/MarkItDown
2. 中间格式: 纯文本 → Markdown
3. 数据一致性: 前端展示与 RAG/ES 索引使用相同的 Markdown 源文件

## 核心设计决策

1. **转换引擎选择**:
   - PDF 使用 MinerU(Docker 服务): 高质量 PDF 转 Markdown,保留表格、公式
   - 其他格式使用 MarkItDown(本地库): Office 文档转 Markdown

2. **内容存储**:
   - Markdown 文件存储在文件系统
   - 数据库仅存储路径和元数据

3. **异步处理**:
   - 文档转换通过 Celery 异步执行
   - 需修改 `document_tasks.py` 的处理流程

4. **RAG/ES 加载方式变更**:
   - 不再使用 LlamaIndex 的多格式 Reader(SimpleDirectoryReader)
   - 统一使用 MarkdownReader 从 Markdown 文件加载
   - 利用 Markdown 标题结构进行智能分块

## 依赖服务

- **MinerU API** (Docker): 高质量 PDF 转 Markdown
- **MarkItDown** (Python 库): Office 文档(Word/Excel/PPT)转 Markdown
  - 安装方式: `uv add markitdown` (安装到项目 .venv 环境)
- **Celery + Redis**: 异步任务队列
- **PostgreSQL**: 元数据存储

## 与现有代码的关系

### 需要修改的文件

| 文件 | 变更说明 |
|------|----------|
| `infrastructure/tasks/document_tasks.py` | 替换 `_extract_text` 为 Markdown 转换逻辑 |
| `infrastructure/content_extraction/` | 替换为 MinerU/MarkItDown 适配器 |
| `core/rag/document_loader/loader.py` | 简化为仅加载 Markdown 文件 |
| `core/engine/index_builder.py` | 使用 MarkdownReader 替代多格式加载 |

### 保持不变的文件

| 文件 | 说明 |
|------|------|
| `core/rag/text_splitter/splitter.py` | 分块逻辑不变 |
| `core/tools/es_search_tool.py` | ES 搜索工具不变 |
| `infrastructure/pgvector.py` | PgVector 存储不变 |
| `infrastructure/elasticsearch.py` | ES 存储不变 |

## 相关文档

- [ai-core-v1](../ai-core-v1/): AI 核心模块(已实现)
- [frontend-v1](../frontend-v1/): 前端设计规划(文档阅读器、选中交互)

## 实现状态

- [ ] Document 实体扩展(添加 content_path 字段)
- [ ] 数据库迁移
- [ ] MinerU Docker 服务集成
- [ ] MarkItDown 集成 (`uv add markitdown`)
- [ ] 修改 Celery 任务(document_tasks.py)
- [ ] 内容查询 API
- [ ] RAG 加载器适配(使用 MarkdownReader)
- [ ] ES 索引适配
- [ ] 单元测试
- [ ] 集成测试
