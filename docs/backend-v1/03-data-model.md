# 文档处理模块 - 数据模型

## 1. Core Concepts (核心概念)

### 1.1 Document (文档)

用户上传的一个文件单元。Document 贯穿整个处理流程,从上传到转换完成。

本模块关注 Document 的内容转换相关属性,不涉及其归属关系(Library/Notebook)。

### 1.2 DocumentContent (文档内容)

Document 转换后的 Markdown 文本内容。

虽然逻辑上属于 Document 的一部分,但物理上独立存储在文件系统中,通过路径关联。

### 1.3 ProcessingStatus (处理状态)

Document 在转换流程中的状态标识。状态流转反映处理进度。

### 1.4 ConversionResult (转换结果)

转换引擎输出的结果,包含 Markdown 内容、页数、提取的图片等。

这是一个临时数据结构,用于转换器与协调器之间的数据传递,不持久化。

---

## 2. Entity / Value Object 区分

### 2.1 Entity (实体)

| 概念 | 说明 | 标识 |
|------|------|------|
| Document | 有唯一 ID,有生命周期 | document_id (UUID) |

### 2.2 Value Object (值对象)

| 概念 | 说明 | 特点 |
|------|------|------|
| ProcessingStatus | 状态枚举值 | 无身份,不可变 |
| DocumentType | 文件类型枚举 | 无身份,不可变 |
| ConversionResult | 转换输出结果 | 无身份,临时存在 |

---

## 3. Key Data Fields (关键数据字段)

### 3.1 Document 扩展字段

本模块需要在现有 Document 实体上扩展以下字段:

| 字段 | 含义 | 说明 |
|------|------|------|
| content_path | 内容文件的相对路径 | 如 "abc-123/content.md",相对于存储根目录 |
| content_format | 内容格式标识 | 当前固定为 "markdown" |
| content_size | 内容大小(字节) | 用于前端展示和性能预估 |

### 3.2 ProcessingStatus 状态值

| 状态 | 含义 | 触发条件 |
|------|------|----------|
| PENDING | 等待处理 | 文档上传后初始状态 |
| PROCESSING | 正在转换 | 任务开始执行时 |
| COMPLETED | 转换完成 | 内容成功保存后 |
| FAILED | 转换失败 | 发生不可恢复错误时 |

### 3.3 ConversionResult 字段

| 字段 | 含义 | 说明 |
|------|------|------|
| markdown | 转换后的 Markdown 文本 | 主要内容 |
| page_count | 原文档页数 | PDF 有实际页数,其他格式默认 1 |
| images | 提取的图片列表 | 图片文件的相对路径 |
| error | 错误信息 | 转换失败时填写 |

---

## 4. Lifecycle & Ownership (生命周期与归属)

### 4.1 Document 内容相关字段的生命周期

```
Document 创建 (上传时)
    |
    | content_path = null
    | status = PENDING
    v
处理任务启动
    |
    | status = PROCESSING
    v
转换引擎执行
    |
    v
转换成功 ──────────────────> 转换失败
    |                           |
    | 保存 Markdown 文件          | status = FAILED
    | content_path = "xxx/content.md"  | error_message = "..."
    | content_size = 12345         |
    | status = COMPLETED           v
    v                          [结束]
[结束]
```

### 4.2 数据归属

| 数据 | 创建者 | 更新者 | 删除时机 |
|------|--------|--------|----------|
| Document 实体 | DocumentService | 本模块(状态/路径) | 用户删除文档时 |
| Markdown 文件 | 本模块 | 不更新(只读) | Document 删除时级联删除 |
| 图片文件 | 本模块 | 不更新(只读) | Document 删除时级联删除 |

### 4.3 存储位置

| 数据类型 | 存储位置 | 路径示例 |
|----------|----------|----------|
| 原始上传文件 | 文件系统 | data/documents/{id}/original.pdf |
| 转换后 Markdown | 文件系统 | data/documents/{id}/content.md |
| 提取的图片 | 文件系统 | data/documents/{id}/images/001.jpg |
| Document 元数据 | PostgreSQL | documents 表 |

---

## 5. 数据一致性约束

### 5.1 文件与数据库一致性

- content_path 非空时,对应的文件必须存在
- Document 删除时,必须同步删除对应的目录和文件
- 转换失败时,content_path 保持为空

### 5.2 状态一致性

- status = COMPLETED 时,content_path 必须非空
- status = FAILED 时,error_message 应包含失败原因
- 状态只能单向流转,不可回退(COMPLETED 不能变回 PROCESSING)

---

## 6. 与现有数据模型的关系

### 6.1 现有 Document 实体字段

本模块复用现有字段:
- document_id: 唯一标识
- title: 文档标题
- content_type: 文件类型(DocumentType 枚举)
- file_path: 原始文件路径
- status: 处理状态(ProcessingStatus 枚举)
- page_count: 页数
- error_message: 错误信息

### 6.2 新增字段

本模块需要扩展:
- content_path: 内容文件路径
- content_format: 内容格式
- content_size: 内容大小
