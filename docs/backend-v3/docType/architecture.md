# architecture.md — 文档类型扩展模块

> 前置：本文档基于当前 `backend-v3` 代码现状与本轮调研结论编写，目标是先稳定支持 `.pptx/.epub` 的上传、检索、总结，再评估是否需要更高精度的专用解析链路。

## Architecture Overview

当前文档处理链路并不是“PDF 走 MinerU，其余全部天然可用”。

- `MinerU cloud` 当前只支持 `.pdf/.doc/.docx`
- `MinerU local` 当前只支持 `.pdf`
- `MarkItDown` 是现阶段 `.pptx/.epub` 唯一可落地、且已在依赖中存在的后端解析器

因此，本次设计采用**两阶段方案**：

1. **阶段一：稳定接入**
   - 把 `.pptx/.epub` 正式纳入上传、类型识别、转换、索引、总结链路
   - 解析路径统一走 `MarkItDown`
   - 不新增新的后端服务，不扩展 MinerU 的支持范围
   - 目标是“可稳定上传、可稳定转 Markdown、可稳定进入检索和总结”

2. **阶段二：质量增强（条件触发）**
   - 若阶段一验证发现 `MarkItDown` 在 `.pptx/.epub` 上的结构保真度不足，再新增专用 converter
   - 方向参考 `Burner-X/js`：按格式分流，而不是把 `.pptx/.epub` 强行塞进 OCR 服务
   - 该阶段不属于本次实施范围

## Research Summary

本轮调研得到的关键结论：

- `MarkItDown 0.1.4` 已内置 `_pptx_converter.py` 和 `_epub_converter.py`
- `PPTX` 链路基于 `python-pptx`，能力不只是抽纯文本，还包含标题、表格、图表、notes 等信息
- `EPUB` 链路基于 `container.xml -> OPF -> manifest/spine -> HTML to Markdown`
- `Burner-X/js` 的启发重点是“专用 parser 分流”，不是“为 `.pptx/.epub` 再找一个 OCR 服务”

这意味着：

- **阶段一优先使用 `MarkItDown` 是合理的**
- `Burner-X/js` 更适合作为阶段二的专用 converter 设计参考，而不是阶段一直接照搬

## Design Pattern & Rationale

### 1. 类型注册、上传准入、转换路由、转换实现分离

当前系统已经天然分为四层职责：

- **类型注册层**
  - [document_type.py](D:/Projects/NotebookLM/newbee-notebook/newbee_notebook/domain/value_objects/document_type.py)
  - 定义系统“认得哪些扩展名”

- **上传准入层**
  - [local_storage.py](D:/Projects/NotebookLM/newbee-notebook/newbee_notebook/infrastructure/storage/local_storage.py)
  - 定义系统“允许上传哪些扩展名”

- **转换路由层**
  - [processor.py](D:/Projects/NotebookLM/newbee-notebook/newbee_notebook/infrastructure/document_processing/processor.py)
  - 定义“每种扩展名走哪条 converter 链”

- **转换实现层**
  - [markitdown_converter.py](D:/Projects/NotebookLM/newbee-notebook/newbee_notebook/infrastructure/document_processing/converters/markitdown_converter.py)
  - 定义“某个 converter 自己能处理哪些扩展名，以及如何封装结果”

本次改动延续这一分层，不把职责混到一个文件里。

### 2. 阶段一不引入新的专用 converter

原因不是“专用 converter 没价值”，而是：

- 当前 `MarkItDown` 已有可用实现
- 我们的首要目标是稳定打通端到端链路
- 过早新增专用 parser，会把本次任务从“接入新格式”升级成“重写文档转换体系”

因此阶段一保持：

- `PDF`：`MinerU -> MarkItDown fallback`
- `DOC/DOCX`：按现有 MinerU cloud / MarkItDown 逻辑
- `PPTX/EPUB`：`MarkItDown only`

### 3. 阶段二保留插拔点

如果后续要借鉴 `Burner-X/js`，推荐新增：

- `PptxStructuredConverter`
- `EpubStructuredConverter`

并将其插入 `MarkItDownConverter` 之前，形成：

- `PPTX`：`StructuredConverter -> MarkItDown fallback`
- `EPUB`：`StructuredConverter -> MarkItDown fallback`

这样可以保留现有 fallback 能力，而不是一次性替换掉成熟链路。

## Module Structure & File Layout

### 阶段一需要修改

```text
后端
newbee_notebook/
  domain/
    value_objects/
      document_type.py             — 注册 `.pptx/.epub`
  infrastructure/
    storage/
      local_storage.py             — 上传扩展名白名单补齐
    document_processing/
      processor.py                 — 保持现有路由，补充/确认测试
      converters/
        markitdown_converter.py    — 补 `.epub` 白名单，必要时补 `page_count` 封装

前端
frontend/src/
  app/
    library/
      page.tsx                     — 上传 accept 与提示文案
  lib/
    i18n/
      strings.ts                   — 支持格式文案

测试
newbee_notebook/tests/unit/
  test_document_processing_processor.py
  ...新增上传/类型相关测试
```

### 阶段一明确不改

- MinerU cloud/local converter 支持范围
- Celery 任务编排
- RAG 切块、索引、检索实现
- Notebook / Library 数据模型
- 新增外部文档解析服务

## Architectural Constraints & Trade-offs

### 收益

- 实现成本低
- 风险可控
- 与现有依赖完全兼容
- 能最快把 `.pptx/.epub` 带入上传、检索、总结闭环

### 代价

- `.pptx/.epub` 的结构保真度上限受 `MarkItDown` 约束
- 复杂 EPUB 样式、图片语义、特殊版式未必完美
- 如果后续需要更强结构化输出，仍需追加阶段二

### 结论

阶段一以“稳定可用”为最优先目标，阶段二才讨论“结构语义增强”。

## Regression Boundaries

本次实现必须确保以下旧链路不被破坏：

1. `PDF` 的 MinerU 主链路不变
2. `DOC/DOCX` 的现有兼容策略不变
3. 既有支持类型 `.pdf/.txt/.md/.csv/.xls/.xlsx/.doc/.docx` 不回归
4. 未知扩展名仍按现有策略处理，不引入新的宽松或激进行为
5. Library 上传、Worker 转换、索引、总结的调用顺序不变

## Implementation Boundary

本次实施边界明确如下：

- 做：
  - `.pptx/.epub` 正式加入后端类型体系
  - `.pptx/.epub` 正式加入上传白名单
  - `.epub` 补入 `MarkItDownConverter._supported`
  - 前端上传入口显示为支持 `.pptx/.epub`
  - 单元测试和最小转换测试补齐

- 可做但不强承诺：
  - `PPTX page_count` 的 best-effort 修正

- 不做：
  - 新增 `PPTX/EPUB` 专用 converter
  - 为 `.pptx/.epub` 接入 MinerU
  - 深度保留图片、批注、复杂样式的结构语义
