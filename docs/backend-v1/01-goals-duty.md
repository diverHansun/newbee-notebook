# 文档处理模块 - 设计目标与职责

## 1. 模块定位

文档处理模块负责将用户上传的各种格式文档转换为统一的 Markdown 格式,供:
1. **前端阅读器**: Markdown 渲染展示
2. **RAG 系统**: 基于 Markdown 进行分块和向量索引
3. **ES 搜索**: 基于 Markdown 进行全文索引

本模块是 MediMind Agent 的基础设施层组件,是前端展示、RAG、ES 的统一数据源。

### 1.1 与现有架构的关系

**当前架构** (ai-core-v1):
- 使用 `content_extraction/base.py` 提取纯文本
- RAG 和 ES 直接从纯文本创建索引
- 前端无法直接展示提取结果

**新架构** (backend-v1):
- 使用 MinerU/MarkItDown 转换为 Markdown
- RAG 和 ES 从 Markdown 文件加载(使用 MarkdownReader)
- 前端使用 react-markdown 渲染同一 Markdown 文件
- **核心价值**: 用户选中的文字与 RAG chunk 内容一致,便于精确引用

---

## 2. Design Goals (设计目标)

### 2.1 高质量格式转换

将 PDF、Word、Excel 等格式转换为结构化的 Markdown,保留原文档的语义结构(标题层级、表格、列表、公式),而非简单的纯文本提取。

### 2.2 统一的内容输出

无论输入何种格式,输出始终是 Markdown 文本,为前端阅读器提供一致的渲染体验。

### 2.3 处理与存储分离

文档转换过程与原始文件存储、转换结果存储解耦,便于独立演进和替换转换引擎。

### 2.4 异步非阻塞

文档转换可能耗时较长(大型 PDF 可能需要数分钟),必须异步执行,不阻塞用户操作。

### 2.5 可观测性

转换过程的状态(排队中、处理中、已完成、失败)对外可见,便于用户了解进度和排查问题。

---

## 3. Duties (职责)

### 3.1 格式识别与路由

根据文件扩展名或 MIME 类型,将文档分发到对应的转换引擎:
- PDF 文档路由到高质量 PDF 处理引擎
- Office 文档(Word/Excel/PPT)路由到通用格式转换器
- 纯文本和 Markdown 直接读取

### 3.2 内容转换

调用转换引擎,将文档内容转换为 Markdown 格式:
- 保留标题层级结构
- 保留表格结构(转换为 Markdown 表格或 HTML 表格)
- 保留列表结构
- 保留公式(转换为 LaTeX 格式)
- 提取并保存内嵌图片

### 3.3 转换结果持久化

将转换后的 Markdown 内容保存到文件系统,并记录存储路径到数据库。

### 3.4 状态管理

维护文档处理状态的生命周期:
- PENDING: 等待处理
- PROCESSING: 正在转换
- COMPLETED: 转换完成
- FAILED: 转换失败(含错误信息)

### 3.5 内容查询

提供接口供外部获取文档的 Markdown 内容,用于前端阅读器渲染。

---

## 4. Non-Duties (非职责) - 变更说明

### 4.1 不负责文件上传

文件上传、临时存储、格式校验由上层 DocumentService 负责。本模块仅接收已保存的文件路径。

### 4.2 RAG/ES 索引 (变更)

**原设计**: 文本分块、向量嵌入、索引写入由独立的 RAG 模块负责。本模块仅输出完整的 Markdown 文本。

**新设计**: 本模块在完成 Markdown 转换后,触发 RAG/ES 索引流程:
1. 保存 Markdown 文件到文件系统
2. 使用 `MarkdownReader` 从 Markdown 文件加载(非原始文件)
3. 分块后索引到 PgVector 和 Elasticsearch

**变更原因**:
- 确保 RAG/ES 索引的内容与前端展示一致
- 利用 Markdown 结构信息(标题层级)进行智能分块
- 不再依赖 LlamaIndex 的多格式 Reader (SimpleDirectoryReader)

### 4.3 不负责内容编辑

本模块不提供文档编辑能力。前端阅读器为只读模式,用户选中文本用于 AI 交互,而非修改文档。

### 4.4 不负责权限控制

文档访问权限由上层服务判断。本模块假设调用方已完成权限校验。

### 4.5 不负责原始文件管理

原始文件的存储、清理、备份由 Storage 模块负责。本模块仅读取原始文件用于转换。

---

## 5. 设计约束

### 5.1 外部依赖

本模块依赖以下外部服务:
- **MinerU API 服务** (Docker 容器): 用于高质量 PDF 转换
- **MarkItDown 库** (本地 Python 库): 用于 Office 文档转换
  - 安装: `uv add markitdown`
  - 安装位置: 项目 `.venv` 虚拟环境

### 5.2 不再依赖的组件

本模块实现后,以下组件将被替代:
- `content_extraction/base.py` 中的 `PdfExtractor`, `DocxExtractor`, `ExcelExtractor`
- `document_loader/loader.py` 中的多格式加载逻辑
- LlamaIndex 的 `SimpleDirectoryReader` + 多格式 Reader 组合

### 5.2 存储约束

转换后的 Markdown 内容存储在文件系统而非数据库,原因:
- 内容可能较大(几十 MB)
- 避免影响数据库查询性能
- 便于直接读取和调试

### 5.3 处理时间

单个文档的转换时间上限为 5 分钟。超时视为失败。

---

## 6. 假设与前提

1. MinerU API 服务在 Docker 环境中稳定运行
2. 文件系统有足够的存储空间
3. 上传的文档为合法文件,非恶意构造
4. 单个文档大小不超过 100MB
