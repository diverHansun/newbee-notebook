# Improve-5 方案设计

## 1. 设计目标

1. 熔断策略从“单次失败”改为“连续失败阈值触发”。
2. 保持超时配置简单可控，避免参数泛滥。
3. 细化 `processing` 内部阶段，提升 ES/Embedding 可观测性。
4. PDF 降级链路切换为 MarkItDown（启用 PDF 能力依赖）。

## 2. 方案一：连续失败阈值熔断

### 2.1 熔断规则

1. MinerU 连续失败计数达到阈值（默认 5）后，进入 cooldown。
2. cooldown 期间跳过 MinerU，直接走降级链路。
3. 任意一次 MinerU 成功后，连续失败计数清零并恢复闭合状态。

### 2.2 推荐配置（简化）

仅保留三项主要可调参数：

1. `MINERU_V4_TIMEOUT`（默认 120s）
2. `MINERU_FAIL_THRESHOLD`（默认 5）
3. `MINERU_COOLDOWN_SECONDS`（默认 120s）

说明：

1. `connect timeout` 固定为 5s（不暴露额外配置）。
2. `read timeout` 使用 `MINERU_V4_TIMEOUT`。
3. 上传/下载维持较高传输超时（沿用当前大文件保护思路）。

---

## 3. 方案二：`processing` 子阶段状态机

### 3.1 主状态保持不变

继续沿用：

`uploaded -> pending -> processing -> completed/failed`

### 3.2 新增子阶段字段

建议新增字段：

1. `processing_stage`：字符串，记录当前子阶段。
2. `stage_updated_at`：时间戳，记录阶段更新时间。
3. `processing_meta`：JSON 文本，记录附加信息（可选，未来用于进度百分比）。

### 3.3 子阶段定义

建议枚举：

1. `converting`
2. `splitting`
3. `embedding`
4. `indexing_pg`
5. `indexing_es`
6. `finalizing`

### 3.4 提交策略

1. 每次阶段切换都独立提交，保证轮询可见。
2. 阶段失败时写入 `failed` + `error_message` + `processing_stage`。
3. 对索引写入做补偿清理，避免“部分成功”脏数据。

---

## 4. 方案三：PDF 兜底切换为 MarkItDown

### 4.1 链路调整

PDF 处理链路调整为：

`MinerU -> MarkItDown(PDF) -> failed`

说明：

1. 不再默认优先 PyPDF。
2. PyPDF 可保留为临时兼容开关（默认关闭）或后续移除。

### 4.2 MarkItDown PDF 启用要求

1. 运行环境需具备 `markitdown[pdf]`（或 `markitdown[all]`）对应依赖。
2. 启动时执行依赖预检（当前 `markitdown==0.1.4` 重点校验 `pdfminer.six`）。
3. 若依赖缺失，日志输出明确错误并回退到可用策略。

### 4.3 场景边界说明

1. 扫描版/图片 PDF 仍建议优先使用 GPU 版本地 MinerU（OCR）。
2. 云端不可用时，纯降级链路对扫描件效果会下降（用户指南明确提示）。

---

## 5. 方案四：依赖一致性与部署策略

### 5.1 依赖优先级

1. `celery-worker` 容器依赖是生产运行真值。
2. 本地 `.venv` 依赖用于开发验证，需尽量与容器对齐。

### 5.2 一致性策略

1. `requirements.txt` 与 `pyproject.toml` 中 `markitdown` 规格保持一致。
2. 新增依赖自检脚本（本地/容器共用）：
   - 校验 `markitdown` 版本
   - 校验 `pdfminer` 可导入
3. 在启动文档和用户指南中明确“本地可用 ≠ 容器可用”的校验方法。

---

## 6. 观测与日志

建议统一结构化日志字段：

1. `document_id`
2. `processing_stage`
3. `from_status`
4. `to_status`
5. `mineru_fail_count`
6. `circuit_state`
7. `duration_ms`
8. `error_code`

---

## 7. Notebook 作用域一致性补充设计

### 7.1 目标

确保 `chat/ask/explain/conclude` 四模式在 RAG/ES 检索过程只使用当前 Notebook 文档。

### 7.2 关键策略

1. 统一后过滤：凡是无法保证预过滤可靠的链路，都在检索结果层执行 `allowed_doc_ids` 后过滤。
2. Chat ES tool 双保险：查询层 terms filter + 返回层 doc_id 后过滤。
3. 作用域变更即时生效：`ChatMode` 在 notebook 文档范围变化时重建工具实例。
4. 告警降噪：缺失 document source 按 doc_id 聚合记录，减少重复 warning。

### 7.3 语义边界

1. Notebook 取消关联：只移除 notebook-document 关系，不删除 Library 文档。
2. Library 删除文档：删除源文档并触发索引清理。
