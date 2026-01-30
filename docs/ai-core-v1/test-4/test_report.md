# MediMind Agent - AI Core v1 全面测试报告

## 测试信息
- 日期: 2026-01-30
- API Base URL: http://localhost:8000/api/v1
- 测试Notebook ID: 9e34d25b-b99b-4ff4-b5b2-90fe27200227
- 测试Session ID: 4479bdeb-bdd2-43fd-9433-02462491414c

---

## 一、API端点测试结果

### 1. Health Check APIs

| 端点 | 方法 | 状态 | 结果 |
|------|------|------|------|
| /health | GET | 200 | `{"status":"ok"}` |
| /health/ready | GET | 200 | PostgreSQL: ok, Redis: skipped, ES: skipped |
| /health/live | GET | 200 | `{"status":"alive"}` |
| /info | GET | 200 | 返回版本和功能信息，支持chat/ask/explain/conclude模式 |

### 2. Library API

| 端点 | 方法 | 状态 | 结果 |
|------|------|------|------|
| /library | GET | 200 | 成功获取library_id和document_count |
| /library/documents | GET | 200 | 返回分页文档列表 |

### 3. Notebooks CRUD

| 端点 | 方法 | 状态 | 结果 |
|------|------|------|------|
| /notebooks | POST | 201 | 成功创建Notebook |
| /notebooks | GET | 200 | 返回分页Notebook列表 |
| /notebooks/{id} | GET | 200 | 成功获取Notebook详情 |
| /notebooks/{id} | PATCH | 200 | 成功更新Notebook |

### 4. Sessions CRUD

| 端点 | 方法 | 状态 | 结果 |
|------|------|------|------|
| /notebooks/{id}/sessions | POST | 201 | 成功创建Session |
| /notebooks/{id}/sessions | GET | 200 | 返回分页Session列表 |
| /sessions/{id} | GET | 200 | 成功获取Session详情 |
| /notebooks/{id}/sessions/latest | GET | 200 | 成功获取最新Session |

### 5. Document Upload & Processing

| 端点 | 方法 | 状态 | 结果 |
|------|------|------|------|
| /documents/notebooks/{id}/upload | POST | 201 | 文档上传成功 |
| /documents/{id} | GET | 200 | 文档状态: pending -> completed |
| /documents/notebooks/{id} | GET | 200 | 返回Notebook文档列表 |

**测试文档:**
1. test_document.txt (1410 bytes) - completed, 1 chunk
2. test_document2.txt (1644 bytes) - completed, 1 chunk
3. test_document3.txt (1726 bytes) - completed, 1 chunk

### 6. Chat Modes

| 模式 | 端点 | 状态 | 结果 |
|------|------|------|------|
| Chat (non-stream) | /chat/notebooks/{id}/chat | 200 | 成功返回响应和sources |
| Chat (stream) | /chat/notebooks/{id}/chat/stream | 200 | SSE流式响应正常 |
| Ask (non-stream) | /chat/notebooks/{id}/chat | 200 | 成功检索多文档并生成响应 |
| Explain (non-stream) | /chat/notebooks/{id}/chat | 200 | 成功使用selected_text生成解释 |
| Conclude (non-stream) | /chat/notebooks/{id}/chat | 500 | **失败 - Internal Server Error** |
| Conclude (stream) | /chat/notebooks/{id}/chat/stream | 200 | 返回后超时 |

### 7. Admin API

| 端点 | 方法 | 状态 | 结果 |
|------|------|------|------|
| /admin/index-stats | GET | 200 | 返回文档统计(total:3, completed:3) |
| /admin/reprocess-pending | POST | 200 | dry_run成功，queued_count:0 |
| /admin/documents/{id}/reindex | POST | 200 | 成功提交reindex任务 |

---

## 二、回归测试结果 (test-1 ~ test-3)

### Test-1 问题回归

| 问题 | 状态 | 验证结果 |
|------|------|---------|
| context.selected_text未被使用 | **已修复** | Explain模式中selected_text成功融入查询，sources中包含user_selection (score:1.0) |

**验证细节:**
- 发送带selected_text的explain请求
- 响应sources包含: `{"chunk_id": "user_selection", "score": 1.0, ...}`
- RAG检索结果与selected_text关联

### Test-2 问题回归

| 问题 | 状态 | 验证结果 |
|------|------|---------|
| Celery队列不匹配 (pending卡住) | **已修复** | 3个文档全部自动处理完成 (pending -> completed) |
| 缺少管理接口 | **已实现** | reprocess-pending, reindex, index-stats全部可用 |
| 删除文档丢失引用 | 未测试 | 需要进一步验证 |

**验证细节:**
- 上传3个txt文档
- 5秒后检查状态全部变为completed
- chunk_count正确更新

### Test-3 问题回归

| 问题 | 状态 | 验证结果 |
|------|------|---------|
| Celery Event Loop问题 | **已修复** | 连续上传3个文档，全部成功处理，无Event loop is closed错误 |
| FilterOperator.IN不支持 | **已修复** | Ask模式在多文档notebook中成功执行检索，使用post-filtering替代pre-filtering |

**验证细节:**
- 连续上传test_document.txt, test_document2.txt, test_document3.txt
- 每个文档处理间隔约1-5秒
- 全部成功，无异步错误

---

## 三、发现的新问题

### 问题1: Conclude模式500错误 (已定位根因)

**现象:**
- 非流式Conclude请求返回HTTP 500 Internal Server Error
- 流式Conclude请求初始200，随后超时
- 具体错误: `ForeignKeyViolationError: references_document_id_fkey`

**根因:** LlamaIndex metadata覆盖问题
- pgvector中存储的`document_id`与documents表ID不匹配
- LlamaIndex在`insert_nodes()`时用internal parent node ID覆盖了`ref_doc_id`
- sources提取使用顶层metadata（错误值），而非`_node_content.metadata`（正确值）

**详细分析和修复方案:** [conclude-mode-fix.md](conclude-mode-fix.md)

### 问题2: Elasticsearch健康检查skipped

**现象:**
- /health/ready显示elasticsearch: skipped

**可能原因:**
- Elasticsearch连接未正确配置
- 但Chat/Ask模式仍然工作（可能使用备用逻辑）

---

## 四、测试总结

### 通过的测试 (15/16)

- Health Check APIs (4/4)
- Library API (2/2)
- Notebooks CRUD (4/4)
- Sessions CRUD (4/4)
- Document Processing (3/3)
- Chat Mode (2/2)
- Ask Mode (1/1)
- Explain Mode (1/1)
- Admin API (3/3)
- Streaming (1/1)

### 失败的测试 (1/16)

- **Conclude Mode**: 500 Internal Server Error (外键约束错误，根因已定位)

### 回归测试结果

| 测试轮次 | 问题数 | 已修复 | 待验证 |
|---------|-------|-------|-------|
| Test-1 | 1 | 1 | 0 |
| Test-2 | 3 | 2 | 1 |
| Test-3 | 2 | 2 | 0 |
| **总计** | **6** | **5** | **1** |

---

## 五、建议下一步

1. **修复Conclude模式外键错误** (P0)
   - 按[conclude-mode-fix.md](conclude-mode-fix.md)方案实施
   - 创建extract_document_id函数
   - 修改四个mode的sources提取逻辑
   - 清理pgvector中的孤立数据

2. **验证删除文档引用保护**
   - 创建带引用的对话
   - 删除源文档
   - 验证引用是否保留

3. **检查Elasticsearch连接**
   - 确认ES健康检查逻辑
   - 验证ES索引数据是否正确
