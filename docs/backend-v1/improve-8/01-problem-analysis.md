# 01 - 问题分析：文档处理流水线的单体困境

## 1. 问题发现

在对 MinerU（远程 PDF→Markdown 转换服务）进行压力测试时，发现以下操作限制：

### 1.1 测试场景

上传 3 个 PDF 文档到 Library（总计 ~252 MB）进行 MinerU 转换稳定性测试：

| 文档 | 大小 |
|------|------|
| 计算机操作系统.pdf | 117.4 MB |
| 人工智能及其应用.pdf | 96.3 MB |
| 荣格心理学入门.pdf | 38.4 MB |

### 1.2 遇到的问题

**目标**：仅测试 MinerU 远程 PDF→Markdown 转换，不需要 RAG 索引或 ES 索引。

**实际情况**：无法做到。

- `POST /documents/library/upload` — 仅上传文件，状态停在 `uploaded`，**不触发任何处理**
- `POST /notebooks/{id}/documents` — 触发**完整流水线**（MinerU + splitting + pgvector + ES），且要求先创建 Notebook
- `POST /admin/reprocess-pending` — 同样触发**完整流水线**
- `POST /admin/documents/{id}/reindex` — 同样触发**完整流水线**

**结论**：当前架构没有任何入口可以单独触发文档转换。

## 2. 当前架构分析

### 2.1 单体处理函数

[document_tasks.py](../../../newbee_notebook/infrastructure/tasks/document_tasks.py) 中的 `_process_document_async()` 是一个六阶段不可拆分的单体函数：

```python
async def _process_document_async(document_id: str):
    # 阶段 1: converting — MinerU/MarkItDown 转换
    conversion_result = await _PROCESSOR.process_and_save(document_id, source_path)
    
    # 阶段 2: splitting — Markdown 分块
    nodes = _load_markdown_nodes(content_path, document)
    
    # 阶段 3: embedding — 空操作（实际嵌入在 pgvector insert 时完成）
    
    # 阶段 4: indexing_pg — 向量索引
    await _index_pg_nodes(nodes)
    
    # 阶段 5: indexing_es — 全文索引
    await _index_es_nodes(nodes)
    
    # 阶段 6: finalizing — 更新元数据
    await doc_repo.update_status(document_id, status=COMPLETED, ...)
```

所有阶段在同一个 try/except 块中顺序执行，没有任何跳过机制。

### 2.2 触发入口分析

| 入口 | 调用的 Task | 阶段范围 | 可控粒度 |
|------|------------|----------|---------|
| notebook 关联 | `process_document_task` | 完整 6 阶段 | 不可拆分 |
| admin reprocess | `process_pending_documents_task` | 完整 6 阶段 | 不可拆分 |
| admin reindex | `process_document_task` | 完整 6 阶段 | 不可拆分 |

### 2.3 状态机的缺失

当前状态机只有 5 个状态：

```
UPLOADED → PENDING → PROCESSING → COMPLETED
                                → FAILED
```

问题在于 `PROCESSING` 是一个**黑盒状态**——无法从外部判断文档处于哪个处理阶段（是正在转换，还是正在索引？），只能通过 `processing_stage` 字段间接猜测。更关键的是，**缺少"转换完成但未索引"这一稳定中间态**。

### 2.4 processing_stage 硬编码

处理阶段值（`converting`, `splitting`, `indexing_pg`, `indexing_es` 等）是散落在代码中的**硬编码字符串**，没有枚举约束：

```python
# 当前代码中的硬编码字符串
await _set_stage("converting")    # 字符串
await _set_stage("splitting")     # 字符串
await _set_stage("indexing_pg")   # 字符串
```

## 3. 影响范围

### 3.1 开发/测试影响

- 无法独立测试 MinerU 转换的稳定性和性能
- 无法对已转换文档单独建索引
- 失败后只能整体重试，即使只是索引阶段失败（MinerU 转换可能耗时 10+ 分钟）
- 压力测试必须等待完整流水线，包含不相关的 pgvector/ES 依赖

### 3.2 运维影响

- MinerU 服务独立部署，可能与 pgvector/ES 分别出故障，但无法分别重试
- 批量重处理 (`reprocess-pending`) 会重跑已完成的转换阶段，浪费资源
- 无法先批量转换文档再按需索引，灵活性不足

### 3.3 产品影响

- 用户上传文档后必须等待完整流水线完成才能看到转换结果
- 文档不属于任何 Notebook 时完全无法处理（Library 中的"冷文档"问题）
- 没有管理界面可以对文档进行细粒度的状态管理

## 4. 软件工程原则分析

### 4.1 违反单一职责原则 (SRP)

`_process_document_async()` 承担了 3 种不同职责：
1. **文档转换**（I/O密集：调用外部 MinerU API 或本地 MarkItDown）
2. **文本处理**（CPU密集：Markdown 读取 + 文本分块）
3. **存储索引**（I/O密集：pgvector 写入 + ES 写入）

这三种职责的失败模式、重试策略、资源需求完全不同。

### 4.2 违反开闭原则 (OCP)

新增处理阶段或修改阶段顺序需要直接修改 `_process_document_async()` 函数体，无法通过扩展实现。

### 4.3 缺少正交分解

当前设计将"文件格式转换"和"搜索索引构建"两个正交关注点耦合在同一个执行路径中。Notebook 关联不应该是转换的唯一触发条件。

## 5. 改进目标

1. **可独立触发**：MinerU/MarkItDown 转换、pgvector 索引、ES 索引都可以独立执行
2. **状态可观测**：引入 `CONVERTED` 中间态，明确区分"已转换未索引"和"已完成"
3. **类型安全**：processing_stage 使用枚举而非硬编码字符串
4. **智能补齐**：Notebook 关联时自动检测缺失阶段，只补齐而非全部重跑
5. **向后兼容**：现有完整流水线和 API 行为保持不变，新能力通过新端点暴露
