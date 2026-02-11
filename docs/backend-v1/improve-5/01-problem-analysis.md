# Improve-5 问题分析

## 1. 问题一：熔断触发条件过于激进

### 1.1 现象

当前实现中，MinerU 请求出现一次网络/超时异常就会触发熔断，并进入固定 cooldown 窗口。

### 1.2 代码证据

1. 默认 cooldown 配置为 300 秒：`newbee_notebook/configs/document_processing.yaml`
2. 单次异常即可设置 `_mineru_unavailable_until`：`newbee_notebook/infrastructure/document_processing/processor.py`

### 1.3 影响

1. 大文件偶发超时会放大为整段不可用窗口。
2. 明明可恢复的瞬时网络抖动，被等同为服务不可用。
3. 前端体验表现为“长时间处理中但无实质推进”。

### 1.4 根因

熔断判定缺少失败计数维度，仅按“是否失败一次”判断，容错粒度不足。

---

## 2. 问题二：`processing` 内部阶段不可观测

### 2.1 现象

状态机主链路已具备 `uploaded -> pending -> processing -> completed/failed`，但 `processing` 阶段内部无法区分：

1. 转换阶段（MinerU/Markdown）
2. 切分阶段（split）
3. Embedding 阶段
4. pgvector 入库阶段
5. ES 入库阶段

### 2.2 影响

1. 失败排障成本高，无法快速定位卡点。
2. 前端只能展示“处理中”，不能展示细粒度提示。
3. 失败重试无法做针对性策略（如仅重试索引阶段）。

### 2.3 根因

数据库模型和任务流程仅维护“主状态”，缺少子阶段字段和阶段级提交点。

---

## 3. 问题三：PDF 降级链路与目标场景不匹配

### 3.1 现象

当前处理链路为 `MinerU -> PyPDF -> MarkItDown`，其中 PyPDF 仅适合有文本层的 PDF，对扫描件能力有限。

### 3.2 影响

1. MinerU 不可用时，扫描件 PDF 处理成功率明显下降。
2. 与“电子书/大型资料以 PDF 为主”的核心使用场景不一致。

### 3.3 根因

历史降级策略沿用 PyPDF 优先，但当前场景中更需要“结构化 PDF 转 Markdown”的兜底方案。

---

## 4. 问题四：本地与运行时依赖存在偏差

### 4.1 现象（环境一致性风险）

历史联调中曾出现本地与容器依赖不一致，导致：

1. `markitdown==0.1.4` 可导入，但 PDF 关键依赖在部分环境缺失。
2. `MarkItDown().convert(pdf)` 在某些环境报 `MissingDependencyException`。
3. 本地可运行与容器可运行结果不一致。

### 4.2 影响

1. 本地联调可能误判“MarkItDown PDF 不可用”。
2. 容器与本地行为不一致时，排障难度上升。

### 4.3 根因

缺少统一依赖校验流程，且未将“实际运行环境（celery-worker）”作为唯一判定基准。

---

## 5. 结论

improve-5 需要同时处理三类一致性问题：

1. 可用性一致性：熔断策略从“单次失败”升级为“连续失败阈值”。
2. 状态一致性：`processing` 内部阶段从黑盒改为可观测状态机。
3. 运行一致性：PDF 兜底链路改为 MarkItDown，并确保本地/容器依赖一致。

此外，在回归测试中还暴露出第四类问题需要补充治理：

4. 检索作用域一致性：四模式与 Chat ES tool 必须严格收敛到 notebook 文档，避免全局索引噪声与 missing document warning 放大。
