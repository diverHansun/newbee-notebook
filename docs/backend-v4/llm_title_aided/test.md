# llm_title_aided 模块 test.md

本文档说明 `llm_title_aided` 模块在实现阶段应如何验证。测试策略遵循 [docs-plan/test-guide.md](../../../docs-plan/test-guide.md) 与 [docs-test/](../../../docs-test/README.md) 的项目级测试方法论。

---

## 一、Module Test Profile（模块测试档案）

- 模块原型：混合型模块
  - 配置解析与 runtime config writer：服务编排 / 外部依赖封装
  - Config API：桥接 / 适配模块
  - Docker GPU runtime adapter：基础设施模块
  - 本地 MinerU + LLM 实机处理：外部依赖集成验收
- 主要测试类型：unit、contract、smoke
- 次要测试类型：integration（仅用于真实 local MinerU + LLM 验收）
- Mock 边界：
  - unit：mock DB settings、文件系统直接依赖、LLM runtime config、日志；不访问真实网络，不做真实文件 I/O。
  - contract：真实 FastAPI router/TestClient；mock 配置服务或 settings 依赖。
  - smoke：读取 Docker compose / Dockerfile / patch 文件，不启动外部 API。
  - integration：真实本地 `mineru-api`、真实 PDF、真实 LLM API；基础 marker 为 `integration`，叠加 `requires_api`、`slow`，不进入日常 CI。
- Marker 规范：
  - 每个测试文件必须且只能有一个基础 marker：`unit`、`contract`、`smoke` 或 `integration`。
  - 推荐在文件顶部用 `pytestmark = pytest.mark.<type>` 标注基础 marker。
  - `slow` 与 `requires_api` 只能作为叠加 marker，不替代基础 marker。
- 测试归属目录：
  - `newbee_notebook/tests/unit/core/common/`
  - `newbee_notebook/tests/unit/core/llm/`
  - `newbee_notebook/tests/unit/infrastructure/document_processing/`
  - `newbee_notebook/tests/contract/api/`
  - `newbee_notebook/tests/smoke/`
  - `newbee_notebook/tests/integration/document_processing/`（可选、默认跳过）

---

## 二、Test Scope（测试范围）

### 覆盖

- MinerU 配置中 `title_aided_enabled` 的默认值、DB 覆盖、环境变量覆盖和 reset 行为。
- Config API 对 `title_aided_enabled` 的读取、更新、重置响应契约。
- Zhipu 默认模型从 `glm-5` 切换为 `glm-5v-turbo` 的后端默认值、available preset、前端默认选择逻辑。
- local-only guard：只有 local 模式才准备 title aided runtime。
- cloud 模式旁路：不写 cloud 请求字段，不触发 Newbee 后处理，不要求本地 `mineru-api`。
- LLM runtime config 复用：provider/model/api_key/base_url 从聊天 LLM 配置读取。
- runtime config writer：生成 MinerU 需要的 `llm-aided-config.title_aided`，并原子写入 ignored runtime 文件。
- 缺少 LLM API key 时，title aided 被禁用并覆盖旧 enabled runtime，但基础 MinerU local 解析链路不被破坏。
- Docker GPU runtime：`mineru-api` 能读取共享 runtime config，并使用 Newbee 本地 adapter。
- 实机验收：启用 `glm-5v-turbo` 后，样例 PDF 的标题层级分布明显优于未启用 baseline。

### 不覆盖

- MinerU cloud API 的 title aided 功能，因为当前不支持也不接入。
- Newbee 自研标题层级算法，因为本批次不实现。
- LLM 模型本身的准确率承诺，只验证接入链路和可观察改善。
- `docs/backend-v4/img-upload/` 相关图片上传与多模态聊天能力，该能力由独立文档与独立实现批次覆盖。
- embedding、chunking、Elasticsearch、pgvector 的质量变化。

---

## 三、Critical Scenarios（关键场景）

### 正常路径：local + 开关开启 + LLM 配置完整

预期：

- document task 在 local 转换前准备 title aided runtime config。
- runtime config 中 `enable=true`，model/base_url 来自聊天 LLM 配置。
- API key 不出现在日志或前端响应中。
- MinerULocalConverter 仍按现有 `/file_parse` 请求发送 PDF，不新增 title aided 表单字段。
- 本地 MinerU 输出中标题层级由 MinerU runtime 自行生成。

### 正常路径：cloud + 开关开启

预期：

- title aided 准备逻辑跳过。
- MinerUCloudConverter 请求参数保持现状。
- 不要求本地 `mineru-api` 运行。
- 不对 cloud 结果进行 Newbee 后处理。

### 正常路径：local + 开关关闭

预期：

- runtime config 必须写入 disabled 状态，覆盖任何旧的 `enable=true` 文件。
- local MinerU 基础解析继续。
- 输出结果与普通 local MinerU 行为一致。

### 异常路径：local + 开关开启 + LLM API key 缺失

预期：

- title aided 不启用。
- 日志记录 provider/model 和 skip reason。
- 不记录 API key。
- 文档转换继续尝试基础 MinerU local 解析。
- 前端通过现有 LLM 配置摘要中的 `llm.api_key_set=false` 诊断密钥状态；不要把聊天 LLM key 状态混入 MinerU cloud `api_key_set`。
- runtime config 必须写入 disabled 状态，覆盖任何旧的 `enable=true` 文件。

### 异常路径：runtime config 写入中断

预期：

- 不留下半写 JSON。
- 已存在的有效 runtime config 不被破坏，或被安全禁用。
- unit 测试通过 mock 文件系统直接依赖验证原子写入调用顺序；如需用真实 `tmp_path` 验证文件系统行为，应归入 integration。

### 边界路径：用户手动选择非默认模型

预期：

- title aided 使用用户当前聊天 LLM model。
- 系统不偷偷切换到隐藏 title aided 模型。
- 仅 Zhipu 默认值和 preset 默认选择变为 `glm-5v-turbo`。

### 边界路径：多并发 local parse

预期：

- v1 文档和测试明确依赖 GPU compose 的单并发约束。
- smoke 测试验证 compose 中 worker concurrency 和 MinerU API concurrency 的默认约束。
- 如果后续提升并发，必须重新评估共享 runtime config 策略。

---

## 四、Contract Specification（契约规约）

### GET /api/v1/config/models

成功响应中 MinerU 配置包含：

- `mode`
- `source`
- `local_enabled`
- `api_key_set`
- `title_aided_enabled`

契约要求：

- `title_aided_enabled` 是 boolean。
- local 模式下 MinerU `api_key_set` 为 not applicable。
- 响应不包含 title aided API key、base_url 或 hidden model。

### PUT /api/v1/config/mineru

请求语义：

- 可更新 `mode`。
- 可更新 `title_aided_enabled`。
- 不接收 provider/model/api_key/base_url。

成功响应：

- 返回更新后的 MinerU 配置摘要。

错误响应：

- 非法 mode 返回 400。
- local 未启用时请求 local 返回 400。

契约要求：

- 只切换 title aided 开关时，不应改变 LLM 配置。
- 切换到 cloud 时，title aided 开关可保留用户意图，但不产生 cloud 生效行为。

### POST /api/v1/config/mineru/reset

成功响应：

- 删除 `mineru.*` DB 覆盖。
- 返回默认 MinerU 配置。
- `title_aided_enabled` 恢复默认值，建议默认 `false`。

契约要求：

- 不重置聊天 LLM provider/model。
- 不删除 LLM API key 环境变量。

### GET /api/v1/config/models/available

契约要求：

- LLM preset 中 Zhipu 默认候选包含 `glm-5v-turbo`。
- 前端切换 provider 到 zhipu 时默认选择 `glm-5v-turbo`。
- `glm-5v-turbo` 是聊天 LLM 默认模型，不是 title aided 专用配置。

### Runtime Config File Contract

文件语义：

- `data/mineru/mineru-runtime.json` 由 title aided writer 写入。
- 本地 `mineru-api` 只读该文件。

契约要求：

- enabled 时包含 `llm-aided-config.title_aided.enable=true`。
- disabled 或 skipped 时不得留下不完整 `api_key/base_url/model` 配置。
- local disabled/skipped 时必须覆盖旧 enabled runtime，避免继续调用旧 LLM 配置。
- 写入过程原子化。
- 文件路径位于 git ignored 目录。

### Local MinerU API Contract

请求语义：

- `/file_parse` 请求仍只包含现有 backend、return flags、page range、lang_list 等字段。

契约要求：

- 不新增 title aided 表单字段。
- title aided 行为由本地 `mineru-api` runtime config 决定。

---

## 五、Integration Points（集成点测试）

### Config API 与 app_settings

验证重点：

- `mineru.title_aided_enabled` 可以持久化。
- reset 删除 `mineru.*` 后恢复默认值。
- local_enabled guard 不被绕过。

测试类型：contract + unit。

### Document task 与 LLM runtime config

验证重点：

- local + enabled 时会读取聊天 LLM runtime config。
- cloud 时不会读取或要求 LLM runtime config。
- LLM API key 缺失时返回 skipped 状态。

测试类型：unit。

### LLM runtime resolver 与 key 状态

验证重点：

- title aided 准备逻辑以 `resolve_llm_runtime_config()` 为准。
- 当 runtime resolver 可通过 provider-specific fallback 取得 API key 时，title aided 不被 Config API 摘要误判为缺 key。
- Config API 仍只向前端返回 `api_key_set` 摘要，不返回 key。

测试类型：unit + contract。

### Title Aided Writer 与文件系统

验证重点：

- 原子写入。
- 禁用状态输出。
- 不泄露 API key 到日志。
- JSON 结构符合 MinerU 预期。

测试类型：unit；如果使用真实 `tmp_path` 验证文件系统原子替换，则归入 integration。

### Docker GPU compose 与 mineru-api

验证重点：

- `mineru-api` 挂载 `data/mineru/`。
- 设置 `NEWBEE_MINERU_TITLE_AIDED_CONFIG_JSON`，并确认没有覆盖 MinerU 原生 tools config。
- 使用 Newbee patched GPU image。
- Dockerfile 显式复制并应用 runtime adapter patch。
- 保持单并发默认约束。

测试类型：smoke。

### 本地 MinerU + LLM + 样例 PDF

验证重点：

- 使用真实本地 `mineru-api`。
- 使用真实 Zhipu 或 Qwen API key。
- 处理样例 PDF 指定页段。
- 对比 title aided off/on 的 `text_level` 分布。

测试类型：integration + `slow` + `requires_api`，默认不在普通 CI 执行。

---

## 六、Verification Strategy（验证策略）

### 自动化测试分层

#### unit

建议文件：

- `newbee_notebook/tests/unit/core/common/test_config_db.py`
- `newbee_notebook/tests/unit/core/llm/test_llm_config.py`
- `newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_title_aided.py`
- `newbee_notebook/tests/unit/infrastructure/tasks/test_document_tasks_title_aided.py`

关注：

- 默认值与 DB/env 优先级。
- runtime config 推导。
- 缺失 API key 的 skip 逻辑。
- 原子写入和日志脱敏。

#### contract

建议文件：

- `newbee_notebook/tests/contract/api/test_config_api_endpoints.py`

关注：

- HTTP 请求/响应结构。
- 错误状态码。
- `title_aided_enabled` 字段稳定性。
- Zhipu preset 默认值。

#### smoke

建议文件：

- `newbee_notebook/tests/smoke/test_docker_compose_stack.py`
- 可选：`newbee_notebook/tests/smoke/test_mineru_title_aided_runtime_adapter.py`

关注：

- GPU compose 环境变量和 volume。
- Dockerfile patch 应用路径。
- runtime config 文件路径约定。
- 单并发保护。

#### frontend（后续批次）

本次代码实施为 backend-only，以下前端测试在 setting_panel 批次执行。

建议文件：

- `frontend/src/components/layout/model-config-panel.test.tsx`

关注：

- MinerU title aided 开关会进入更新 payload。
- provider 切换到 zhipu 时默认模型为 `glm-5v-turbo`。
- 不出现单独的 title aided provider/model/api_key/base_url 表单。

#### integration

建议文件：

- `newbee_notebook/tests/integration/document_processing/test_mineru_title_aided_local_pipeline.py`
- 可选：`newbee_notebook/tests/integration/document_processing/test_mineru_title_aided_runtime_file.py`（仅当需要真实文件系统原子替换验证时）

标记：

- `@pytest.mark.integration`
- `@pytest.mark.slow`
- `@pytest.mark.requires_api`

关注：

- 真实 PDF 处理。
- 真实 local MinerU。
- 真实外部 LLM。
- 可选真实 runtime config 文件替换验证。
- 结果改善，而不是严格断言每个标题等级都完美。

### 推荐执行命令

日常开发：

```bash
pytest -m "unit or contract"
```

本模块相关快速验证：

```bash
pytest newbee_notebook/tests/unit/core/common/test_config_db.py \
       newbee_notebook/tests/unit/core/llm/test_llm_config.py \
       newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_title_aided.py \
       newbee_notebook/tests/contract/api/test_config_api_endpoints.py
```

Docker/GPU 配置冒烟：

```bash
pytest newbee_notebook/tests/smoke/test_docker_compose_stack.py
```

真实 MinerU + LLM 验收：

```bash
pytest -m "integration and requires_api and slow" \
       newbee_notebook/tests/integration/document_processing/test_mineru_title_aided_local_pipeline.py
```

### 手工验收规范

使用样例 PDF：

```text
C:\Users\Hansun2026\Downloads\数字电子技术基础简明教程_11695986.pdf
```

建议页段：

```text
15-35
```

验收步骤：

1. 关闭 title aided，使用 local/GPU 模式处理页段，记录 `text_level` 分布。
2. 开启 title aided，LLM provider 选择 zhipu，model 使用 `glm-5v-turbo`。
3. 重新处理同一页段，记录 `text_level` 分布。
4. 对比标题层级是否从“几乎全为 1 级”改善为包含合理的 2/3/4 级。
5. 抽查章节标题，确认一级、二级、三级标题没有大面积混淆。
6. 检查日志中没有 API key。
7. 切换到 cloud 模式，确认不依赖本地 `mineru-api` title aided 行为。

通过标准：

- local title aided on 的结果出现明显多级标题分布。
- 如果出现 5 级及以上标题，应记录为模型/提示风险并进入人工分析；本批次不得在 Newbee 侧后处理改写 content list 或 markdown 来强行裁剪层级。
- 文档转换成功保存 markdown 与 metadata assets。
- cloud 模式行为保持原样。

---

## 七、测试自检

- [x] 已判定模块原型为混合型，并按类型拆分 unit / contract / smoke / integration。
- [x] 测试目录归属符合 docs-test 规范。
- [x] 每个关键职责都有对应验证场景。
- [x] Config API 包含契约测试说明。
- [x] runtime config writer 包含 API key 脱敏和原子写入测试说明。
- [x] cloud 旁路与 local-only guard 都有测试覆盖。
- [x] 每个测试文件有且仅有一个基础 marker，真实外部 API 测试额外标记 `requires_api`、`slow`，不进入日常 CI。
- [x] 明确 `docs/backend-v4/img-upload/` 不属于本批次测试范围。
