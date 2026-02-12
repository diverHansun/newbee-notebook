# 文档引用系统设计

## 1. 系统概述

文档引用系统是类似 Google NotebookLM 的核心功能，允许用户在查看文档内容的同时，将特定段落引用到对话中，并在 AI 回答时追溯来源。

### 1.1 核心功能

- 文档结构化展示（章节、页码）
- 文档内容选中和引用
- AI 回答自动关联来源
- 引用来源点击跳转
- 引用历史管理
- Explain/Conclude 模式的选中触发

### 1.2 用户价值

- 提升用户对 AI 回答的信任度
- 支持深度文档研究
- 便于引用和笔记整理
- 提供完整的溯源能力

### 1.3 与 Notebook/Library 的关系

文档引用系统运行在 Notebook 上下文中：
- 只能引用当前 Notebook 内的文档
- 包括直接上传到 Notebook 的文档
- 包括从 Library 引用到 Notebook 的文档
- 不能引用 Library 中未添加到当前 Notebook 的文档

## 2. 系统架构

### 2.1 架构层次

```
前端展示层
    ↓
API 接口层
    ↓
应用服务层
    ↓
核心逻辑层（RAG + 引用追踪）
    ↓
基础设施层（数据存储）
```

### 2.2 核心组件

**文档解析器**
- 提取文档结构（章节、目录）
- 识别页码和位置
- 保留格式信息

**智能分块器**
- 按章节或页面分块
- 保留元数据（页码、章节、位置）
- 支持跨块引用

**引用追踪器**
- 记录 AI 使用的文档块
- 生成引用关系
- 提供溯源查询

**上下文构建器**
- 整合文档内容和引用
- 优先级排序
- Token 预算管理
- 限定在 Notebook 文档范围内

## 3. 数据模型设计

### 3.1 文档实体

**Document**
- document_id：文档唯一标识
- library_id：所属 Library（可为空）
- notebook_id：所属 Notebook（可为空，与 library_id 互斥）
- title：文档标题
- content_type：文档类型（pdf、docx 等）
- file_path：文件路径
- url：来源 URL（视频等）
- status：处理状态
- page_count：页数
- chunk_count：分块数
- created_at、updated_at：时间戳

**文档归属规则**
- library_id 有值：属于 Library
- notebook_id 有值：属于 Notebook（专属文档）
- 两者不能同时有值

### 3.2 文档块存储（使用 LlamaIndex）

> **设计决策**：文档块不单独建表，统一使用 LlamaIndex 自动创建的向量表（`data_documents_*`）。

**LlamaIndex 表结构**（自动创建）
- id：BIGSERIAL 主键
- text：文本内容
- metadata_：JSONB 元数据
- node_id：VARCHAR 节点标识（UUID 格式）
- embedding：VECTOR 向量

**metadata_ 字段存储内容**
- document_id：所属文档 UUID
- page_number：页码（PDF）
- section_title：章节标题
- section_level：章节层级（1、2、3）
- start_position：起始字符位置
- end_position：结束字符位置
- timestamp：时间戳（视频字幕，秒级）
- ref_doc_id：LlamaIndex 内部引用

**优点**
- 复用 LlamaIndex 的索引构建和检索优化
- 减少数据同步问题
- 支持按配置切换嵌入模型表

### 3.3 引用实体

**Reference**
- reference_id：引用唯一标识
- session_id：所属 Session
- message_id：关联消息
- chunk_id：引用的文档块（VARCHAR，存储 LlamaIndex node_id）
- document_id：引用的文档
- quoted_text：引用的文本
- context：上下文（前后文）
- created_at：创建时间

> **注意**：`chunk_id` 不设外键，因为 LlamaIndex 表使用 BIGSERIAL 主键，与我们的 UUID 体系不匹配。
> 查询时通过 `chunk_id` 去 LlamaIndex 表按 `node_id` 字段查询。

### 3.4 文档结构

**DocumentStructure（内存对象）**
- document_id：文档标识
- title：文档标题
- structure：树形结构
  - type：节点类型（chapter、section、page）
  - title：节点标题
  - level：层级
  - page_number：页码
  - start_position、end_position：位置
  - children：子节点列表

## 4. 核心流程设计

### 4.1 文档上传和处理流程

**上传到 Library**

1. 用户通过 Library 页面上传文档
2. 创建 Document 记录，设置 library_id，状态为 processing
3. 提交 Celery 异步任务
4. 异步任务执行：
   - 内容提取（PDF、Word 等）
   - 结构解析（章节、页码）
   - 智能分块（保留元数据）
   - 嵌入生成
   - 存储到 pgvector
5. 更新 Document 状态为 completed

**上传到 Notebook**

1. 用户在 Notebook 内部上传文档
2. 创建 Document 记录，设置 notebook_id，状态为 processing
3. （后续流程同上）

**关键技术点**

- PDF：使用 PyMuPDF 提取页码和内容
- Word：使用 python-docx 提取章节
- 章节识别：基于样式和标题层级
- 页面分块：优先按页面或章节分块，而非固定 token

### 4.2 文档结构提取流程

**PDF 文档**

1. 解析 PDF 目录（TOC）
2. 识别标题样式（字体大小、粗体）
3. 按页面提取内容
4. 构建章节树形结构
5. 为每个块关联页码和章节

**Word 文档**

1. 解析文档样式
2. 识别标题级别（Heading 1、2、3）
3. 按段落提取内容
4. 构建章节树形结构
5. 计算字符位置

**视频字幕**

1. 提取字幕文件（SRT、VTT）
2. 解析时间戳
3. 按时间段分块（如每 30 秒）
4. 保留时间戳信息

### 4.3 文档内容查询流程

**请求流程**

1. 前端请求 GET /api/v1/documents/{id}/content
2. 验证文档属于当前 Notebook（直接上传或引用）
3. 从数据库查询 Document 和 DocumentChunk
4. 构建树形结构（如未缓存）
5. 返回结构化 JSON
6. 缓存到 Redis（1 小时）

**数据结构示例**

```json
{
  "document_id": "doc-1",
  "title": "论文标题",
  "structure": [
    {
      "type": "chapter",
      "title": "第一章 引言",
      "level": 1,
      "page_number": 1,
      "start_position": 0,
      "end_position": 5000,
      "children": [
        {
          "type": "section",
          "title": "1.1 研究背景",
          "level": 2,
          "page_number": 1,
          "start_position": 0,
          "end_position": 2000
        }
      ]
    }
  ],
  "total_pages": 10
}
```

### 4.4 用户引用创建流程

**前端交互**

1. 用户在左侧文档视图选中文本
2. 点击"引用到对话"按钮
3. 前端调用 POST /api/v1/references
4. 传递：session_id、选中文本、位置信息
5. 后端创建 Reference 记录
6. 返回引用 ID
7. 前端在对话输入框插入引用标记

**后端处理**

1. 验证文档属于当前 Session 所在的 Notebook
2. 根据位置信息查找对应的 chunk_id
3. 获取上下文（前后各 200 字符）
4. 创建 Reference 记录
5. 返回完整引用信息

### 4.5 AI 回答自动引用流程

**流程步骤**

1. 用户发送问题
2. 获取当前 Notebook 的文档列表
3. RAG 检索相关文档块（限定在 Notebook 范围）
4. 将检索结果传递给 LLM
5. ReferenceTracker 记录使用的块
6. LLM 生成回答
7. 后端自动创建 Reference 记录
8. 返回回答 + 引用来源

**关键技术点**

- 在 Prompt 中要求 LLM 标注来源
- ReferenceTracker 解析 LLM 输出
- 自动关联 chunk_id 和 message_id
- 返回格式化的引用信息

### 4.6 引用跳转流程

**前端交互**

1. 用户点击回答中的引用来源
2. 前端调用 GET /api/v1/references/{id}
3. 获取引用详情（chunk_id、位置）
4. 左侧文档视图滚动到对应位置
5. 高亮显示引用文本

**后端处理**

1. 查询 Reference 记录
2. 查询关联的 Chunk 和元数据
3. 返回完整上下文和位置信息

### 4.7 Explain/Conclude 选中触发流程

**Explain 模式（讲解）**

1. 用户在文档阅读器中选中一段文本
2. 右键菜单选择"讲解"
3. 前端调用 POST /api/v1/notebooks/{id}/chat/stream
4. 请求体包含：
   - mode: "explain"
   - context.selected_text: 选中的文本
   - context.document_id: 文档 ID
   - context.chunk_id: 所在的块 ID
   - context.page_number: 页码
5. 后端调用 Explain 模式处理
6. 流式返回讲解内容

**Conclude 模式（总结）**

1. 用户在文档阅读器中选中一段或多段文本
2. 右键菜单选择"总结"
3. 前端调用 POST /api/v1/notebooks/{id}/chat/stream
4. 请求体包含：
   - mode: "conclude"
   - context.selected_text: 选中的文本
   - context.document_id: 文档 ID
   - context.chunk_id: 所在的块 ID（或块 ID 列表）
   - context.page_number: 页码
5. 后端调用 Conclude 模式处理
6. 流式返回总结内容

## 5. 核心组件实现

### 5.1 文档解析器（DocumentParser）

**职责**
- 提取文档结构
- 识别章节和页码
- 构建树形结构

**接口**

```python
class DocumentParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> DocumentStructure:
        """解析文档结构"""

    @abstractmethod
    def extract_metadata(self, content: str, position: int) -> ChunkMetadata:
        """提取块元数据"""
```

**实现**
- PDFParser：解析 PDF 文档
- WordParser：解析 Word 文档
- SubtitleParser：解析视频字幕

### 5.2 智能分块器（SmartChunker）

**职责**
- 按语义边界分块
- 保留元数据
- 优化块大小

**策略**

**PDF 文档**
- 优先按页面分块
- 如页面过长，按段落分块
- 保留页码信息

**Word 文档**
- 按章节分块
- 如章节过长，按段落分块
- 保留章节标题和层级

**视频字幕**
- 按时间段分块（30-60 秒）
- 保留时间戳
- 保证语义完整性

**接口**

```python
class SmartChunker:
    def chunk_with_metadata(
        self,
        content: str,
        structure: DocumentStructure
    ) -> List[DocumentChunk]:
        """智能分块并附加元数据"""
```

### 5.3 引用追踪器（ReferenceTracker）

**职责**
- 追踪 RAG 检索结果
- 记录 LLM 使用的块
- 自动创建引用

**流程**

1. RAG 检索返回 chunk_id 列表
2. ReferenceTracker 缓存检索上下文
3. LLM 生成回答
4. 解析回答中的引用标记
5. 创建 Reference 记录

**接口**

```python
class ReferenceTracker:
    def track_retrieval(
        self,
        session_id: str,
        chunk_ids: List[str]
    ):
        """记录检索上下文"""

    def create_references(
        self,
        session_id: str,
        message_id: int,
        llm_response: str
    ) -> List[Reference]:
        """从LLM回答中提取并创建引用"""
```

### 5.4 上下文构建器（ContextBuilder）

**职责**
- 整合文档内容和引用
- 优先级排序
- Token 预算管理
- 限定在 Notebook 文档范围

**策略**

**优先级排序**
1. 用户主动引用的内容（权重 100）
2. RAG 检索的相关块（权重 80）
3. 同文档的相关块（权重 60）
4. Session 历史中的引用（权重 40）

**Token 预算**
- 计算可用 token 数
- 按优先级填充内容
- 超出部分截断
- 保证完整性（不截断句子）

**接口**

```python
class ContextBuilder:
    def build(
        self,
        notebook_id: str,
        session_id: str,
        max_tokens: int = 4000,
        user_references: List[str] = None
    ) -> Dict:
        """构建对话上下文，限定在 Notebook 文档范围"""
```

### 5.5 Notebook 检索器（NotebookRetriever）

**职责**
- 获取 Notebook 的文档列表
- 限定检索范围
- 支持多种检索模式

**接口**

```python
class NotebookRetriever:
    async def get_notebook_documents(
        self,
        notebook_id: str
    ) -> List[Document]:
        """获取 Notebook 的所有文档（直接上传 + 引用）"""
    
    async def retrieve(
        self,
        notebook_id: str,
        query: str,
        mode: str = "hybrid",
        top_k: int = 10
    ) -> List[ChunkWithScore]:
        """在 Notebook 范围内检索"""
```

## 6. 数据库设计

### 6.1 表结构

**documents 表**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| library_id | UUID | 所属 Library（可为空）|
| notebook_id | UUID | 所属 Notebook（可为空）|
| title | VARCHAR(500) | 标题 |
| content_type | VARCHAR(50) | 类型 |
| file_path | VARCHAR(1000) | 文件路径 |
| url | VARCHAR(1000) | 来源 URL |
| status | VARCHAR(20) | 状态 |
| page_count | INTEGER | 页数 |
| chunk_count | INTEGER | 块数 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**约束**：library_id 和 notebook_id 不能同时有值

**文档块存储**

> 使用 LlamaIndex 自动创建的表，不单独建表。详见 [07-technical-decisions.md](07-technical-decisions.md) 第 2.2 节。

**references 表**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| session_id | UUID | Session ID |
| message_id | INTEGER | 消息 ID |
| chunk_id | VARCHAR(64) | 文档块 node_id（不设外键）|
| document_id | UUID | 文档 ID |
| quoted_text | TEXT | 引用文本 |
| context | TEXT | 上下文 |
| created_at | TIMESTAMP | 创建时间 |

> **注意**：`chunk_id` 存储 LlamaIndex 的 `node_id`，不设外键约束。

### 6.2 索引设计

**documents 表**
- PRIMARY KEY (id)
- INDEX idx_library_id (library_id)
- INDEX idx_notebook_id (notebook_id)
- INDEX idx_status (status)
- INDEX idx_created_at (created_at)

**references 表**
- PRIMARY KEY (id)
- FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
- FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
- INDEX idx_session_id (session_id)
- INDEX idx_document_id (document_id)
- INDEX idx_chunk_id (chunk_id)
- INDEX idx_created_at (created_at)

## 7. 缓存策略

### 7.1 文档结构缓存

**缓存键**
```
doc:structure:{document_id}
```

**缓存内容**
- 完整的树形结构 JSON
- 过期时间：1 小时
- 更新策略：文档更新时清除

### 7.2 文档块缓存

**缓存键**
```
doc:chunk:{chunk_id}
```

**缓存内容**
- 块内容和元数据
- 过期时间：30 分钟
- 更新策略：被访问时延长

### 7.3 Notebook 文档列表缓存

**缓存键**
```
notebook:documents:{notebook_id}
```

**缓存内容**
- Notebook 的文档 ID 列表（包括直接上传和引用）
- 过期时间：10 分钟
- 更新策略：文档增删时清除

### 7.4 引用缓存

**缓存键**
```
ref:session:{session_id}
```

**缓存内容**
- Session 所有引用的 ID 列表
- 过期时间：10 分钟
- 更新策略：新增引用时更新

## 8. 性能优化

### 8.1 文档处理优化

- 异步处理，不阻塞上传响应
- 批量嵌入生成
- 并发处理多个文档
- 进度反馈

### 8.2 查询优化

- 向量索引优化（IVFFlat）
- 分页加载大文档
- 预加载常用文档结构
- 查询结果缓存
- Notebook 文档列表缓存

### 8.3 引用创建优化

- 批量创建引用
- 异步写入数据库
- 缓存引用关系

## 9. 前端交互设计

### 9.1 文档视图

**布局**
- 左侧：文档内容展示
- 右侧：对话界面
- 可调整分隔比例

**功能**
- 章节导航（左侧目录）
- 页面跳转
- 文本选中
- 引用按钮
- 右键菜单（讲解、总结）
- 高亮显示

### 9.2 引用交互

**创建引用**
1. 选中文本
2. 出现悬浮按钮"引用到对话"
3. 点击后在对话框插入引用标记
4. 显示引用来源信息

**右键菜单**
1. 选中文本
2. 右键弹出菜单
3. 选择"讲解"→ 触发 Explain 模式
4. 选择"总结"→ 触发 Conclude 模式

**查看引用**
1. 回答中显示引用来源标记
2. 点击跳转到文档对应位置
3. 高亮显示引用文本
4. 显示引用上下文

### 9.3 引用管理

**引用列表**
- 显示 Session 所有引用
- 按时间排序
- 支持搜索过滤
- 点击跳转

## 10. 质量保证

### 10.1 准确性保证

**章节识别**
- 多种策略结合
- 人工标注样本验证
- 错误率 < 5%

**页码关联**
- PDF 页码精确提取
- Word 按字符位置计算
- 误差 < 1 页

**引用溯源**
- 100% 可追溯
- 引用关系完整
- 无孤立引用

### 10.2 性能保证

**响应时间**
- 文档结构查询 < 200ms
- 引用创建 < 100ms
- 引用查询 < 50ms

**处理能力**
- 支持 100 页 PDF
- 支持 1 小时视频
- 并发 50 个文档处理

### 10.3 鲁棒性保证

**异常处理**
- 文档格式错误
- 结构提取失败
- 引用关系丢失

**降级策略**
- 无法提取结构时按固定大小分块
- 无法识别章节时只保留页码
- 引用失败时仅显示文本

## 11. 测试策略

### 11.1 单元测试

- DocumentParser 各实现
- SmartChunker 分块逻辑
- ReferenceTracker 引用创建
- ContextBuilder 上下文构建
- NotebookRetriever 范围检索

### 11.2 集成测试

- 文档上传到结构提取完整流程
- 引用创建到查询流程
- 对话中自动引用流程
- Notebook 范围检索准确性

### 11.3 E2E 测试

- 用户上传 PDF 到查看结构
- 用户选中文本到引用
- 用户提问到引用来源跳转
- 右键讲解/总结功能

## 12. 未来扩展

### 12.1 高级功能

- 图表识别和引用
- 公式识别和引用
- 表格数据引用
- 跨文档引用关联

### 12.2 协作功能（需多用户支持）

- 引用分享
- 引用评论
- 引用标注

### 12.3 智能功能

- 自动摘要引用段落
- 引用相似度分析
- 引用关系图谱
