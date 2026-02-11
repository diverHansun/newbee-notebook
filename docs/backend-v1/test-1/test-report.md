# 后端 v1 第一轮集成测试报告

## 测试环境

- 平台: Windows 11 (WSL2) + Docker
- MinerU: CPU 模式 (medimind/mineru-api:cpu)
- 容器: PostgreSQL 16 (pgvector), Elasticsearch 8.19, Redis 7.2, Celery Worker, MinerU API
- FastAPI: 本机运行 (localhost:8000)

## 测试范围

| 分类 | 端点数 | 测试状态 |
|------|--------|----------|
| Health | 4 | 通过 |
| Library | 2 | 通过 |
| Notebooks | 5 | 通过 |
| Documents | 7 | 通过 |
| Sessions | 5 | 通过 |
| Chat (4种模式) | 7 | 通过 |
| Admin | 3 | 通过 |

## 测试用例

### 用例 1: 文本类 PDF (Clean Code, 3MB, 462页)

- 上传: 通过
- MinerU 处理: 超时回退到 PyPdf (详见问题 1)
- PyPdf 回退结果: 711 chunks, 904KB markdown -- 文本PDF回退可用
- Chat Ask 模式: 正常回答, 检索到相关文档
- Chat/Explain/Conclude 模式: 均正常

### 用例 2: 扫描类 PDF (计算机操作系统, 118MB, 410页)

- 上传: 通过
- MinerU 处理: 超时回退到 PyPdf (详见问题 1)
- PyPdf 回退结果: 1 chunk, 86 bytes -- 扫描PDF回退不可用, 无法提取文本
- MinerU 实际处理: 在后台继续运行约 89 分钟后完成, 返回 200 OK, 但结果被丢弃

## 发现的问题

### 问题 1 (严重): MinerU httpx 超时导致扫描PDF处理失败

**现象**: Celery worker 日志显示 "MinerU service appears unavailable ()", 回退到 PyPdf.

**根本原因**: `mineru_converter.py` 中 httpx 超时设为 600 秒. MinerU 在 CPU 模式下处理大 PDF 需要远超 10 分钟:

- 文本 PDF (462页): 实际需要 ~20 分钟 (Layout + OCR pipeline)
- 扫描 PDF (410页): 实际需要 ~89 分钟 (完整 OCR pipeline)

超时后客户端断开, MinerU 仍在后台继续处理, 结果最终被丢弃.

**影响**: 文本 PDF 因 PyPdf 回退可用, 影响较小; 扫描 PDF 无法提取文本, 影响严重.

**涉及文件**:
- `newbee_notebook/configs/document_processing.yaml` (第7行)
- `newbee_notebook/infrastructure/document_processing/converters/mineru_converter.py` (第73行)

**修复方案**: 将读取超时设为无限制 (None), 仅保留连接超时 (5秒) 用于快速检测 MinerU 不可达. 配置中用 0 表示不限制.

### 问题 2 (中等): 中文文件名存入数据库时出现乱码

**现象**: 上传 "计算机操作系统.pdf" 后, 数据库中 title 字段为乱码.

**根本原因**: `document_service.py:141` 直接使用 `upload.filename` 作为 title, 未经编码解码处理. 而 `local_storage.py` 中已有 `_decode_filename()` 函数做了 latin1->utf8 的修复, 但该函数仅用于文件存储路径, 未应用于数据库 title.

**涉及文件**:
- `newbee_notebook/application/services/document_service.py` (第141行)
- `newbee_notebook/infrastructure/storage/local_storage.py` (第21-42行, 已有解码函数)

**修复方案**: 在 `document_service.py` 中对 title 也调用 `_decode_filename()`.

### 问题 3 (低): 删除文档节点时 await 同步方法导致报错

**现象**: Celery worker 日志显示 "Delete pgvector nodes failed: object NoneType can't be used in 'await' expression".

**根本原因**: `document_tasks.py:165,178` 对 `VectorStoreIndex.delete_ref_doc()` 使用了 `await`, 但该方法是同步方法, 返回 None. 同一文件中 `insert_nodes()` 正确地未使用 `await`.

**涉及文件**:
- `newbee_notebook/infrastructure/tasks/document_tasks.py` (第165行, 第178行)

**修复方案**: 移除 `await`, 改为直接同步调用.

## 额外观察

### MinerU 模型缓存正常

第二次请求未重新下载模型, 模型初始化时间从 99 秒降至 23 秒. Docker volume `mineru_cache` 正确挂载到 `/root/.cache`.

### MinerU OCR pipeline 完整运行

扫描 PDF 的完整处理链:

1. Layout Predict (384 pages)
2. MFD Predict (公式检测)
3. Formula OCR
4. Table-OCR (1,404 items)
5. Table-wireless/wired Predict (49 items)
6. OCR-det Predict (384 pages)
7. OCR-rec Predict (20,650 items)
8. Processing pages (410 pages)

所有阶段均 100% 完成, 最终返回 200 OK.
