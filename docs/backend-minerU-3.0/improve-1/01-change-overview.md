# 01 · 变更概览

本文列出本轮 MinerU 3.0 适配的**全部变更点**，配合每一项的官方依据与设计取舍说明。详细设计见各分域文档。

---

## 变更汇总表

| # | 变更域 | 目标文件 | 变更类型 | 紧迫度 |
|---|---|---|---|---|
| 1 | Docker | `docker/mineru/Dockerfile.gpu` | 版本升级（vLLM + mineru） | 高（前置） |
| 2 | Docker | `docker/mineru/Dockerfile.cpu` | 版本升级（mineru core） | 高（前置） |
| 3 | Docker | `docker-compose.gpu.yml` | healthcheck 端点修复 | 高 |
| 4 | 本地转换器 | `newbee_notebook/infrastructure/document_processing/converters/mineru_local_converter.py` | 新增 3 个构造器参数 + form_data 透传 | 中 |
| 5 | 云端转换器 | `newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py` | 新增 5 个构造器参数 + payload 扩展 | 中 |
| 6 | 配置 | `newbee_notebook/configs/document_processing.yaml` | 新增 8 个 YAML 配置项 | 中 |
| 7 | 编排 | `newbee_notebook/infrastructure/document_processing/processor.py` | 新参数从 YAML 透传到转换器 | 中 |
| 8 | *(ZIP 解析)* | `_parse_result_zip` 方法 | 无需修改（代码审查验证） | 无 |

---

## 按变更域分组的要点

### 变更 1 · Dockerfile.gpu 升级

- **当前**：`docker.m.daocloud.io/vllm/vllm-openai:v0.11.0` + `mineru[core]>=2.7.0`。
- **目标**：`docker.m.daocloud.io/vllm/vllm-openai:v0.11.2` + `mineru[core]>=3.0.0`。
- **官方依据**：`mineru/docker/global/Dockerfile` 使用 `vllm/vllm-openai:v0.11.2` + `mineru[core]>=3.0.0`。
- **理由**：mineru 3.0 是 breaking 版本，VLM 推理引擎从同步改为 async（`aio_do_parse`），若不升级则 `hybrid-auto-engine` 新路径失效；vLLM 0.11.2 修复了 Blackwell 架构（RTX 50xx）的调度问题。

### 变更 2 · Dockerfile.cpu 同步升级

- **当前**：`mineru[api,pipeline]>=2.7.0`。
- **目标**：`mineru[api,pipeline]>=3.0.0`。
- **理由**：保持 GPU/CPU 版本一致，避免分叉维护；官方 pipeline 后端在 3.0 也有优化。
- **风险**：pipeline 在 3.0 有内部调整，需在升级后跑一次完整 smoke test（用同一份样本 PDF 对比升级前后的 markdown 输出）。

### 变更 3 · docker-compose.gpu.yml healthcheck 修复

- **当前**：`curl -f http://localhost:8000/docs >/dev/null 2>&1 || exit 1`。
- **目标**：`curl -f http://localhost:8000/health || exit 1`。
- **官方依据**：`mineru/mineru/cli/fast_api.py` 第 1498 行 `@app.get(path="/health")`；`mineru/docker/compose.yaml` 的 healthcheck 也使用 `/health`。
- **理由**：`/health` 是专门的健康检查端点，返回结构化状态（`{"status": "healthy", "queued_tasks": N, ...}`）；旧的 `/docs` 在生产环境关闭 FastAPI 文档（`MINERU_API_ENABLE_FASTAPI_DOCS=0`）时返回 404，导致容器永久 unhealthy。

### 变更 4 · MinerULocalConverter 新增 3 个参数

| 参数 | 默认值 | 作用 |
|---|---|---|
| `parse_method` | `"auto"` | PDF 解析策略：`auto`（自动判断）/ `txt`（直接文本抽取，快）/ `ocr`（强制 OCR，扫描件准） |
| `formula_enable` | `True` | 数学公式识别开关 |
| `table_enable` | `True` | 表格识别开关 |

- **官方依据**：`mineru/mineru/cli/fast_api.py` 第 806-823 行的 `parse_method` / `formula_enable` / `table_enable` Form 参数定义。
- **设计取舍**：三个参数全部走 `__init__` 构造器注入，不引入 config dataclass；与现有 `backend` / `lang_list` 等参数的风格保持一致。

### 变更 5 · MinerUCloudConverter 新增 5 个参数

| 参数 | 默认值 | 作用 |
|---|---|---|
| `model_version` | `None` | `pipeline` / `vlm` / `MinerU-HTML`；`None` 表示不传，由 API 使用默认值 |
| `enable_formula` | `True` | 公式识别 |
| `enable_table` | `True` | 表格识别 |
| `is_ocr` | `None` | `None` 表示不传（API 自动判断）；显式 `True/False` 强制开关 |
| `language` | `"ch"` | OCR 语言，与本地模式保持一致 |

- **官方依据**：<https://mineru.net/apiManage/docs> 的 `POST /api/v4/file-urls/batch` 请求参数定义。
- **设计取舍**：
  - `model_version` 和 `is_ocr` 用 `None` 表示"不在 payload 中出现"，让 API 服务端使用默认值；这样官方升级默认行为时我们的代码无需跟改。
  - `language` 默认 `"ch"` 与本地模式 `lang_list` 的首项保持一致，避免两种模式下语言行为不一致带来的用户困惑。
  - `model_version` 三种模式的选择不在前端 Settings Panel 暴露，仅在配置文件中修改（运维/管理员侧能力），详细差异见 [04-云端转换器.md](./04-云端转换器.md)。

### 变更 6 · document_processing.yaml 新增配置项

共 8 个新配置项，参见 [05-配置层.md](./05-配置层.md) 的完整 diff。

### 变更 7 · processor.py 透传逻辑

在 `DocumentProcessor.__init__` 中：

- `MinerULocalConverter(...)` 调用新增 3 个参数的读取与透传（参见 [processor.py:121-138](../../../newbee_notebook/infrastructure/document_processing/processor.py#L121-L138)）。
- `MinerUCloudConverter(...)` 调用新增 5 个参数的读取与透传（参见 [processor.py:90-107](../../../newbee_notebook/infrastructure/document_processing/processor.py#L90-L107)）。
- `model_version` 与 `is_ocr` 的空字符串 → `None` 转换逻辑在这一层处理。

### 变更 8 · ZIP 解析层（无需修改）

- **新版 ZIP 结构**：从 v3.0 起，ZIP 内路径变为 `{pdf_name}/{backend_dir_name}/{file}.md` 两层嵌套（旧版通常为单层或平铺）。
- **代码验证**：[mineru_local_converter.py:307-328](../../../newbee_notebook/infrastructure/document_processing/converters/mineru_local_converter.py#L307-L328) 的 `_parse_result_zip` 通过动态读取 `.md` 文件的父目录作为 prefix（`PurePosixPath(markdown_path).parent`），无论 ZIP 是单层还是两层嵌套都能正确剥离前缀。
- **结论**：无需修改，但在 [06-实施步骤.md](./06-实施步骤.md) 的验收环节需要用新版本实际跑一次确认。

---

## 本轮显式不做的事情

记录此处是为了把未来的工作边界也写清楚，避免在本分支上 scope creep：

| 未做 | 原因 | 后续追踪 |
|---|---|---|
| v1 Agent Lightweight API（免费、无 Auth） | 不返回图片资产，降级语义复杂 | 待 improve-2 讨论 |
| 前端 Settings Panel 暴露新参数 | 本轮属于基础设施升级，不改变用户可见行为 | 待 UX 统一设计后再做 |
| Cloud v4 单文件端点（`/api/v4/extract/task`） | 当前 batch 端点用 `[{"name": file_name}]` 已等效单文件，无收益 | 不计划 |
| v4 `extra_formats`（DOCX/HTML/LaTeX 导出） | 当前管道以 Markdown 为唯一中间格式 | 不计划 |
| v4 `callback` webhook | 当前轮询方式已满足需求，webhook 增加基础设施复杂度 | 不计划 |
| KIE SDK 接入 | 独立的知识信息抽取服务，与文档转 Markdown 场景不匹配 | 不计划 |

---

## 下一步

阅读顺序建议：

1. [02-docker-infrastructure.md](./02-docker-infrastructure.md) — Docker 层变更（前置，必须先完成）
2. [03-local-converter.md](./03-local-converter.md) — 本地转换器代码 diff
3. [04-cloud-converter.md](./04-cloud-converter.md) — 云端转换器代码 diff 与 model_version 详解
4. [05-config-layer.md](./05-config-layer.md) — YAML 与 processor.py 透传
5. [06-implementation-steps.md](./06-implementation-steps.md) — 完整实施顺序与验收方式
