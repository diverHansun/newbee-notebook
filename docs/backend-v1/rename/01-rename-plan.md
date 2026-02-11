# Backend-v1 收尾：`newbee_notebook` -> `newbee_notebook` 重命名计划

## 1. 目标与边界

1. 后端包目录从 `newbee_notebook` 重命名为 `newbee_notebook`。
2. Python 包名与模块入口同步重命名，保证本地运行、Celery、测试命令可继续执行。
3. 对齐 `docs/backend-v1` 阶段文档，完成 backend-v1 最后一步收尾。
4. 先做路径与引用重命名，不在本轮强制改业务逻辑。

## 2. 扫描基线（2026-02-11）

通过 `rg -l -e "newbee_notebook" -e "newbee-notebook"` 扫描得到：

1. 命中文件总数：`152`
2. 包内文件：`115`（`newbee_notebook/**`）
3. `docs/backend-v1`：`21`
4. 其他文档：`8`
5. 根目录/运维入口文件：`8`

明细文件清单已输出到：

1. `docs/backend-v1/rename/affected-files-newbee-notebook-path.txt`

## 3. 必改文件层级

## 3.1 代码与测试（阻断级）

1. 整个目录重命名：`newbee_notebook/` -> `newbee_notebook/`
2. 所有绝对导入：`from newbee_notebook...` / `import newbee_notebook...` -> `newbee_notebook...`
3. Celery task name 字符串中的模块路径（例如 `newbee_notebook.infrastructure.tasks...`）
4. `main.py` 入口导入路径
5. `pytest.ini` 的 `testpaths`
6. `newbee_notebook/tests/conftest.py` 中基于包目录的路径拼接

## 3.2 运行与构建入口（高优先）

1. `pyproject.toml`
2. `uv.lock`
3. `docker-compose.yml`（celery `-A` 路径、SQL 挂载路径）
4. `quickstart.md`
5. `POSTMAN_GUIDE.md`
6. `scripts/README.md`

## 3.3 backend-v1 文档（本阶段必须同步）

`docs/backend-v1` 内所有出现 `newbee_notebook` 的文档全部替换为 `newbee_notebook`，以保持实施文档与代码一致。

## 4. 实施步骤（执行顺序）

## 阶段 A：安全基线

1. 记录当前 `git status` 与未跟踪目录状态（当前有 `MinerU/` 未跟踪，保持不动）。
2. 再次生成命中清单，确保改动前后可对比。

## 阶段 B：目录与代码路径重命名

1. 重命名目录：`newbee_notebook` -> `newbee_notebook`
2. 批量替换 Python 代码中的包导入路径。
3. 替换 Celery task name 字符串中的旧模块路径。
4. 修正测试目录引用与配置。

## 阶段 C：工程入口与文档命令同步

1. 修改 `pyproject.toml` 项目名与包发现配置。
2. 更新 `uv.lock` 中本项目包名。
3. 修改 `docker-compose.yml` 中旧模块路径与挂载路径。
4. 同步更新 `quickstart.md`、`POSTMAN_GUIDE.md`、`scripts/README.md` 里的命令示例。
5. 同步更新 `docs/backend-v1/**` 内的包路径引用。

## 阶段 D：回归验证（按 backend-v1 基线）

先执行语法与导入冒烟：

1. `.\.venv\Scripts\python.exe -c "import newbee_notebook; import newbee_notebook.api.main"`

执行 backend-v1 相关单测回归（原 improve-4/5 基线迁移到新路径）：

1. `.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests/unit/test_document_processing_processor.py newbee_notebook/tests/unit/test_document_service_content_guard.py newbee_notebook/tests/unit/test_chat_service_guards.py newbee_notebook/tests/unit/test_delete_document_nodes_task.py`
2. `.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests/unit`
3. `.\.venv\Scripts\python.exe -m pytest -q newbee_notebook/tests/integration`
4. `python -m json.tool postman_collection.json`

与历史基线对照：

1. 已知历史失败项（`test_selector.py` 相关）若仍存在，记录为“历史遗留”；不应新增由重命名引入的失败。

## 5. 风险点与控制

1. 风险：遗漏字符串路径（代码能编译但运行时 `ModuleNotFoundError`）。
   控制：重命名后执行 `rg "newbee_notebook|newbee-notebook"` 必须清零或仅保留明确历史文档。
2. 风险：Celery worker 启动参数未同步。
   控制：`docker-compose.yml` 变更后做一次 `celery -A ... --help` 冒烟。
3. 风险：文档命令与实际代码不一致。
   控制：本轮把 `docs/backend-v1` 内命令全部同步。

## 6. 待你确认的范围决策

1. 是否仅重命名“后端包路径”与 `docs/backend-v1`，其余历史文档（`docs/ai-core-v1`、`docs/demo` 等）先不批量替换？
2. 是否同步做“品牌词重命名”（`Newbee Notebook` 文案、`newbee-notebook-*` 容器名、默认 DB 名 `newbee_notebook`、默认 ES 索引 `newbee_notebook_docs`）？
3. 是否在本轮改类名/异常名（例如 `NewbeeNotebookAgent`、`NewbeeNotebookException`）？建议作为下一轮语义重构，避免与路径改名耦合。

---

确认以上范围后，我将按阶段 B -> C -> D 一次性执行并回传测试结果与回归结论。
