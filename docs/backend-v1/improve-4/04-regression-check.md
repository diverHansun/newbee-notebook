# Improve-4 回归检验（对照 improve-1 ~ improve-3）

## 1. 检验目标

确认 improve-4 实施后：

1. 修复 improve-3 暴露问题（500、处理中状态不可见、脚本入口混乱）。
2. 不破坏 improve-1（Library-first）与 improve-2（MinerU 三模式）的既有行为。
3. API 契约与错误码语义对齐 ai-core-v1。

## 2. 对照范围

对照文档：

1. `docs/backend-v1/improve-1/README.md`
2. `docs/backend-v1/improve-1/01-architecture.md`
3. `docs/backend-v1/improve-1/02-api-design.md`
4. `docs/backend-v1/improve-2/README.md`
5. `docs/backend-v1/improve-2/01-architecture.md`
6. `docs/backend-v1/improve-2/04-docker-changes.md`
7. `docs/backend-v1/improve-3/01-design.md`
8. `docs/backend-v1/improve-3/test-report.md`
9. `docs/ai-core-v1/08-error-handling.md`

## 3. 回归结果

## 3.1 improve-1（Library-first 与状态流转）

结论：主流程保持兼容，状态机语义增强为“可观测”。

检查项：

1. Library-first 上传流程未改变：
   - 上传仍为 `uploaded`（不触发处理）。
2. Notebook 关联触发处理仍成立：
   - 关联后写 `pending` 并入队。
3. 状态链路从“可跳变”修正为显式状态机：
   - `uploaded -> pending -> processing -> completed/failed`。
4. 管理端重建索引路径与状态机一致：
   - reindex 先写 `pending` 再入队。

对应代码：

1. `newbee_notebook/application/services/notebook_document_service.py`
2. `newbee_notebook/infrastructure/tasks/document_tasks.py`
3. `newbee_notebook/api/routers/admin.py`
4. `newbee_notebook/domain/value_objects/document_status.py`

## 3.2 improve-2（MinerU 三模式与 Docker 约束）

结论：无行为回归，Docker 文件无需改动。

检查项：

1. 本次改动未触达 MinerU converter/processor 选择逻辑。
2. 未修改 `docker-compose.yml` 与 `docker-compose.gpu.yml`。
3. 与 improve-2 的 profile 机制、cloud/local 模式边界保持一致。

说明：

1. improve-4 聚焦错误语义与状态机，不改变部署拓扑。
2. 因无新增环境变量与容器依赖，本轮 Docker 配置保持原样。

## 3.3 improve-3（V4 链路与测试报告问题修复）

结论：核心问题已落地修复。

问题 1：文档未就绪触发 500

1. 新增统一业务异常：`DocumentProcessingError`（`E4001`，HTTP `409`）。
2. ChatService 在检索依赖模式做前置校验并抛结构化错误。
3. FastAPI 全局异常处理器统一输出 `error_code/message/details`。

问题 2：处理中状态不可见

1. 入队前显式写 `pending` 并提交。
2. Worker 以原子条件更新领取 `processing`，并立即提交。
3. 长耗时处理结束后提交 `completed` 或 `failed`。

问题 3：脚本入口不一致

1. 明确三层脚本职责：`scripts/`、`newbee_notebook/scripts/`、`frontend/scripts/`。
2. 后端脚本示例统一为 `python -m newbee_notebook.scripts.<name>`。

## 4. API 契约与 Postman 回归

结论：已同步更新测试集合，覆盖未就绪分支。

更新点：

1. Ask 非流式：支持 `200` 或 `409`，并校验 `E4001`。
2. 三个流式用例（chat/explain/conclude）：支持 `200` 或 `409`，并校验 `E4001`。

文件：

1. `postman_collection.json`

## 5. 自动化验证结果

执行命令：

1. `python -m json.tool postman_collection.json`
2. `.\\.venv\\Scripts\\python.exe -m pytest -q newbee_notebook/tests/unit/test_chat_service_guards.py`
3. `.\\.venv\\Scripts\\python.exe -m pytest -q newbee_notebook/tests/unit`

结果：

1. JSON 校验通过。
2. 新增守卫测试通过（3/3）。
3. 单元测试总计 `106`，通过 `103`，失败 `3`。
4. 失败项均为既有测试基线问题：
   - `newbee_notebook/tests/unit/test_selector.py` 中 `SessionManager` 构造参数已变化（与 improve-4 改动无直接关联）。

## 6. 残余风险与建议

1. 现有 `test_selector.py` 需要单独修复或迁移到当前 `SessionManager` 构造签名。
2. 建议下一步在真实后端环境执行端到端轮询验证：
   - 观察 `uploaded -> pending -> processing -> completed` 的可见性。
3. 建议用 Postman 复测 `ask/explain/conclude` 在“未就绪/已就绪”两类场景，确认前端联调契约稳定。

