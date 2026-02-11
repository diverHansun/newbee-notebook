# Backend-v1 收尾：重命名实施报告

## 1. 实施范围（已执行）

1. 包目录重命名：`medimind_agent/` -> `newbee_notebook/`
2. 包导入重命名：`medimind_agent.*` -> `newbee_notebook.*`
3. 项目包名重命名：`medimind-agent` -> `newbee-notebook`
4. 类名重命名：
   - `MediMindAgent` -> `NewbeeNotebookAgent`
   - `MediMindException` -> `NewbeeNotebookException`
   - `medimind_exception_handler` -> `newbee_notebook_exception_handler`
5. 容器/网络/默认配置命名调整：
   - 容器名前缀：`medimind-*` -> `newbee-notebook-*`
   - 网络名：`medimind_network` -> `newbee_notebook_network`
   - DB 默认名：`medimind` -> `newbee_notebook`
   - ES 默认索引：`medimind_docs` -> `newbee_notebook_docs`
6. 文档范围：
   - 已同步 `docs/backend-v1/**`
   - 未批量改动 `docs/ai-core-v1`、`docs/demo` 等非本轮范围文档

## 2. 关键文件

1. `pyproject.toml`
2. `pytest.ini`
3. `docker-compose.yml`
4. `main.py`
5. `newbee_notebook/**`
6. `docs/backend-v1/**`

## 3. 测试执行（.venv）

## 3.1 导入冒烟

命令：

1. `.\.venv\Scripts\python.exe -c "import newbee_notebook; import newbee_notebook.api.main; print('import-smoke-ok')"`

结果：

1. 通过（`import-smoke-ok`）

## 3.2 backend-v1 目标单测

命令：

1. `.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests/unit/test_document_processing_processor.py newbee_notebook/tests/unit/test_document_service_content_guard.py newbee_notebook/tests/unit/test_chat_service_guards.py newbee_notebook/tests/unit/test_delete_document_nodes_task.py`

结果：

1. `15 passed`

## 3.3 全量 unit

命令：

1. `.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests/unit`

结果：

1. `121 passed`

## 3.4 tests 目录回归

命令：

1. `.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests`

结果：

1. `121 passed`

说明：

1. `newbee_notebook/tests/integration/test_chat_engine_integration.py` 当前为脚本式集成验证，不是 pytest 测试函数，因此 pytest 不会计入 collected。
2. 该脚本可用模块方式执行，但本地运行在构建 ChatEngine 阶段出现既有运行时错误（`index is None`），不属于本次命名重构直接引入。

## 3.5 Postman 集合校验

命令：

1. `.\.venv\Scripts\python.exe -m json.tool postman_collection.json`

结果：

1. 通过

## 4. 残留项说明

`docs/backend-v1` 内仍有 `medimind/mineru-api` 文本，属于 MinerU 镜像仓库名（非包路径、非容器名、非 DB/ES 默认值），本轮保留：

1. `docs/backend-v1/improve-2/04-docker-changes.md`
2. `docs/backend-v1/test-1/test-report.md`

