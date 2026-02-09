# Improve-4 实施计划

## 1. 实施目标

在保持业务主流程不变的前提下，完成以下交付：

1. 文档未就绪返回标准错误（`E4001` + HTTP `409`）。
2. 文档状态机落地并实现中间态可观测。
3. 脚本分层规则落地并统一命令入口文档。

## 2. 范围与非范围

## 2.1 本阶段范围

1. Chat 接口错误语义统一（非流式 + 流式）。
2. Document 异步处理状态流转修正。
3. 脚本目录规范与文档规范收敛。

## 2.2 非范围

1. 前端 UI 改造（仅提供可消费后端契约）。
2. 大规模重构异常体系（先落地最小可行版本）。
3. 检索算法与模型能力调整。

## 3. 任务拆分

## 3.1 任务 A：错误处理契约落地（P0）

目标：彻底消除“文档未就绪导致 500”。

实施项：

1. 新增业务异常类型（含 `error_code/http_status/details`）。
2. 新增全局异常处理器（统一错误格式）。
3. 在 ChatService 增加模式可用性统一校验（至少覆盖 `ask/explain/conclude`）。
4. 非流式 API 返回 `409 + E4001`。
5. 流式 API 返回 `error` 事件，payload 结构与非流式一致。

预期修改文件（初版）：

1. `medimind_agent/application/services/chat_service.py`
2. `medimind_agent/api/routers/chat.py`
3. `medimind_agent/api/main.py`
4. `medimind_agent/api/middleware/error_handler.py`（新增）
5. `medimind_agent/common/exceptions.py`（新增或放置于现有公共目录）

## 3.2 任务 B：状态机与事务边界修正（P0）

目标：对外可见 `pending` 与 `processing`，并避免重复处理。

实施项：

1. 关联文档入队时写 `pending` 并提交。
2. Worker 领取任务时原子切换为 `processing` 并提交。
3. 处理完成写 `completed`，失败写 `failed` 并提交。
4. 增加并发保护：重复任务遇到 `processing/completed` 直接跳过。
5. 管理端重处理接口与状态机保持一致。

预期修改文件（初版）：

1. `medimind_agent/application/services/notebook_document_service.py`
2. `medimind_agent/application/services/document_service.py`
3. `medimind_agent/infrastructure/tasks/document_tasks.py`
4. `medimind_agent/infrastructure/persistence/repositories/document_repo_impl.py`
5. `medimind_agent/domain/value_objects/document_status.py`（如需补充注释与约束）

## 3.3 任务 C：脚本分层与入口文档统一（P1）

目标：形成可长期执行的脚本规范，避免目录继续混乱。

实施项：

1. 固化分层规则（backend/frontend/global）。
2. 统一推荐调用方式（后端优先 `python -m medimind_agent.scripts.*`）。
3. 新增脚本索引文档（建议 `scripts/README.md`）。
4. 校正文档中冲突命令示例。

预期修改文件（初版）：

1. `quickstart.md`
2. `README.md`
3. `scripts/README.md`（新增）
4. `docs/backend-v1/improve-4/*.md`

## 4. 测试计划

## 4.1 接口与行为测试

1. 文档处于 `pending/processing` 时调用 `ask/explain/conclude`：
   - 返回 HTTP `409`
   - `error_code = E4001`
   - 包含 `details.blocking_document_ids`
2. 文档完成后调用上述模式：
   - 返回 `200`
   - sources 正常
3. 流式接口同场景：
   - 返回 `error` 事件
   - `error_code = E4001`

## 4.2 状态流转测试

1. 上传后状态为 `uploaded`。
2. 关联后立即可见 `pending`。
3. Worker 执行时可见 `processing`。
4. 成功结束为 `completed`；失败结束为 `failed`。
5. 重复入队同一文档不会并发重复处理。

## 4.3 回归测试

1. `chat` 模式不受影响。
2. 文档内容读取接口行为不变。
3. Admin 接口（`reprocess-pending` / `reindex` / `index-stats`）结果符合新状态机。

## 5. 验收标准

1. 不再出现“文档未就绪导致 500”。
2. 轮询可以稳定观察 `pending` 和 `processing` 中间态。
3. 错误响应符合 `error_code/message/details` 统一格式。
4. 文档中的脚本命令无冲突，执行路径清晰。

## 6. 风险与缓解

1. 风险：状态机改动影响历史任务兼容。
   - 缓解：保持对 `uploaded/pending/failed` 入队兼容，新增转换逻辑仅前向增强。
2. 风险：全局异常处理器引入后影响现有 FastAPI 默认错误格式。
   - 缓解：仅对业务异常应用统一格式，保留验证错误最小兼容映射。
3. 风险：脚本命令变更造成团队短期习惯成本。
   - 缓解：保留兼容入口并在文档标注迁移期。

## 7. 执行顺序建议

1. 先完成任务 A（错误处理契约），快速消除 500。
2. 再完成任务 B（状态机与事务边界），确保前端可观测性。
3. 最后完成任务 C（脚本分层与文档收敛），统一工程使用习惯。

