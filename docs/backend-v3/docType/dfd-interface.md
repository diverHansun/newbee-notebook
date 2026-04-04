# dfd-interface.md — 文档类型扩展模块

> 前置：本文档只描述阶段一的数据流和接口边界；阶段二的专用解析器不在本次接口定义范围内。

## Context & Scope

本模块在阶段一涉及四个关键边界：

- **类型识别边界**
  - 扩展名如何映射到 `DocumentType`
- **上传准入边界**
  - 哪些扩展名允许进入 Library
- **转换路由边界**
  - `.pptx/.epub` 由哪个 converter 接管
- **前端提示边界**
  - 用户如何得知系统支持这两种格式

## Data Flow Description

### 上传流

1. 用户在前端 Library 页面选择 `.pptx` 或 `.epub` 文件
2. 前端通过 `POST /api/v1/documents/library/upload` 上传文件
3. 后端上传存储层先检查扩展名白名单
4. 白名单通过后，`document_service.upload_to_library()` 调用 `DocumentType.from_extension(ext)`
5. 数据库中的 `content_type` 分别写入 `"pptx"` 或 `"epub"`
6. 后续 notebook 绑定和异步处理逻辑不变

### 转换流

1. Worker 读取文档原文件路径
2. `DocumentProcessor.convert(file_path)` 根据扩展名获取可用 converter
3. 对于 `.pptx/.epub`：
   - `MinerU` converter 的 `can_handle()` 返回 `False`
   - `MarkItDownConverter.can_handle()` 返回 `True`
4. `MarkItDownConverter.convert()` 返回 Markdown
5. Markdown 进入后续存储、索引、检索、总结链路

### 质量增强流（本次不实施）

如果后续进入阶段二，则会在“转换流”的第 3 步前插入专用 converter：

```text
PPTX/EPUB
  -> StructuredConverter (future)
  -> MarkItDown fallback
```

## Interface Definition

### 后端：DocumentType.from_extension()

- 输入：不带点的扩展名，如 `pptx`、`epub`
- 输出：`DocumentType.PPTX`、`DocumentType.EPUB`
- 兜底：未知扩展名保持现有行为

### 后端：上传白名单

- 位置：[local_storage.py](D:/Projects/NotebookLM/newbee-notebook/newbee_notebook/infrastructure/storage/local_storage.py)
- 输入：上传文件扩展名
- 输出：
  - 支持类型：允许保存并返回 `(relative_path, size, ext)`
  - 不支持类型：抛出 `ValueError("Unsupported file type: .ext")`
- 本次新增：`pptx`、`epub`

### 后端：MarkItDownConverter.can_handle()

- 输入：带点扩展名，如 `.pptx`、`.epub`
- 输出：`bool`
- 本次新增：`.epub -> True`
- 现状保持：`.pptx -> True`

### 后端：DocumentProcessor 路由语义

- `.pdf`
  - 维持 `MinerU -> MarkItDown fallback`
- `.doc/.docx`
  - 维持现有兼容逻辑
- `.pptx/.epub`
  - 阶段一固定为 `MarkItDown only`

### 前端：文件输入与支持格式文案

- `accept` 属性应与后端支持范围保持一致
- 上传区域需要明确展示 `.pptx/.epub` 已支持
- 前端文案只承担提示职责，不承担真实安全校验职责

## Data Ownership & Responsibility

| 数据/规则 | 创建方 | 消费方 | 备注 |
|---|---|---|---|
| 扩展名到 `DocumentType` 的映射 | `document_type.py` | `document_service.py` | 类型注册权威来源 |
| 允许上传的扩展名集合 | `local_storage.py` | 上传接口 | 上传安全边界 |
| 实际转换路由 | `processor.py` | Worker | 决定 `.pptx/.epub` 是否走 MinerU |
| `MarkItDown` 支持白名单 | `markitdown_converter.py` | `DocumentProcessor` | 决定是否能接住 `.epub` |
| 支持格式提示 | 前端页面 + i18n | 用户 | 仅用于 UX，同步后端语义 |

## Regression Points

以下点必须作为本次实现的接口级回归检查：

1. `.pdf` 仍然优先走 MinerU
2. `.doc/.docx` 既有行为不回退
3. `.pptx/.epub` 上传后，`content_type` 不得错误降级为 `txt`
4. 上传白名单不应意外放开其它未支持格式
5. 前后端对支持格式的展示和实际行为不能脱节
