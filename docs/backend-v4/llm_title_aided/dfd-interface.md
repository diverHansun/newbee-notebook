# llm_title_aided 模块 dfd-interface.md

本文档描述 `llm_title_aided` 模块与外部模块之间的数据流和接口边界。本文档基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md) 和 [data-model.md](data-model.md)。

---

## 一、Context & Scope（上下文与范围）

`llm_title_aided` 模块位于 Newbee Notebook 的文档转换链路中，连接以下模块：

- 设置面板与 Config API：负责用户开关和默认模型配置。
- config_db 与 LLM runtime config：负责解析 MinerU 与聊天 LLM 的有效配置。
- document task 与 DocumentProcessor：负责在文档转换前准备本地 MinerU runtime。
- MinerULocalConverter：负责调用本地 `mineru-api`。
- 本地 `mineru-api`：负责读取 runtime config，并在 MinerU 解析内部执行 `llm_aided_title()`。
- MinerU cloud converter：只作为旁路存在，不参与 title aided。

本文档只描述 local/GPU 模式下 title aided 配置如何进入 MinerU 本地运行时，以及 cloud 模式如何保持无副作用。不描述图片上传、多模态聊天、embedding、索引、MinerU cloud API 内部实现。

---

## 二、Data Flow Description（数据流描述）

### 1. 配置读取与展示流

1. 前端设置面板请求当前模型配置。
2. Config API 从 config_db 读取 `Effective MinerU Config` 与 LLM 配置摘要。
3. config_db 合并 DB、环境变量与默认值，返回 MinerU 当前 mode、local_enabled、title_aided_enabled、MinerU cloud api_key_set；LLM key 状态仍由现有 LLM 配置摘要表达。
4. Config API 返回给前端。
5. 前端展示 MinerU mode 与 title aided 开关，不展示独立 title aided 模型配置。

输出目标：设置面板。

关键约束：

- 前端只能看到配置摘要中的 `api_key_set`，不能看到 API key；不要把 LLM key 状态混入 MinerU cloud key 字段。
- title aided 开关只是用户意图，不代表当前任务一定实际启用。

### 2. 配置更新流

1. 用户在设置面板修改 MinerU mode 或 title aided 开关。
2. 前端调用 Config API 的 MinerU 配置更新接口。
3. Config API 校验 mode 是否为 `cloud` 或 `local`。
4. 如果请求 `local` 但当前部署未启用 local，Config API 拒绝更新。
5. Config API 将 `mineru.mode` 与 `mineru.title_aided_enabled` 写入 `app_settings`。
6. config_db 将有效 MinerU 配置投影到当前进程环境。
7. Config API 返回新的 MinerU 配置摘要。

输出目标：app_settings、当前 API 进程环境、前端设置面板。

关键约束：

- 切换到 cloud 不触发 title aided 后处理。
- 打开 title aided 不会立即调用 LLM；它只影响后续 local 文档转换。

### 3. Zhipu 默认模型配置流

1. Config API 的 available models 返回 LLM preset。
2. Zhipu 默认 preset 使用 `glm-5v-turbo`。
3. 前端在用户切换 LLM provider 到 zhipu 时，选择 `glm-5v-turbo` 作为默认模型。
4. LLM 配置 reset 时，后端默认配置也恢复到 `glm-5v-turbo`。

输出目标：LLM 设置面板与 LLM runtime config。

关键约束：

- `glm-5v-turbo` 是聊天 LLM 的 Zhipu 默认模型，不是隐藏 title aided 专用模型。
- 用户手动输入其他模型时，title aided 尊重用户选择。

### 4. Local 文档转换准备流

1. document task 开始处理 PDF 文档。
2. task 从 DB 同步 `Effective MinerU Config`。
3. 如果 mode 不是 `local`，title aided 准备流结束。
4. 如果 mode 是 `local` 但 title_aided_enabled 为 false，必须写入 disabled runtime config 覆盖旧 enabled 状态，然后继续基础 MinerU 解析。
5. 如果 mode 是 `local` 且开关为 true，task 读取聊天 `LLM Runtime Config`。
6. 如果 LLM runtime config 无法取得 API key，title aided 准备流记录 skip reason，必须写入 disabled runtime config 覆盖旧 enabled 状态，并保持基础解析可继续。
7. 如果 LLM runtime config 完整，LLM Config Bridge 生成 `MinerU Title Aided Runtime Config`。
8. MinerU Title Config Writer 将 runtime config 原子写入 `data/mineru/mineru-runtime.json`。
9. task 创建 DocumentProcessor 并进入 local converter。

输出目标：共享 runtime config 文件、DocumentProcessor。

关键约束：

- API key 只写入 ignored runtime 文件，不写入日志。
- title aided 准备失败不应让整个文档转换直接失败，除非失败破坏了基础 MinerU 调用所需环境。

### 5. Local MinerU 解析流

1. MinerULocalConverter 将 PDF 发给本地 `mineru-api` 的 `/file_parse`。
2. 本地 `mineru-api` 通过 Newbee runtime adapter 在解析阶段读取 `data/mineru/mineru-runtime.json`。
3. MinerU local 完成版面分析，得到标题候选。
4. 当 runtime config 中 `title_aided.enable=true` 时，MinerU 调用 LLM。
5. LLM 根据标题文本、行高、页码返回标题层级。
6. MinerU 将层级写回 middle JSON，并生成 markdown、content list、model output 等结果。
7. MinerULocalConverter 解析 ZIP 结果并返回 `ConversionResult`。
8. DocumentProcessor 按现有流程保存 markdown、image assets 和 metadata assets。

输出目标：Newbee 文档存储与后续索引流程。

关键约束：

- Newbee 不在本阶段二次改写 content list 或 markdown。
- local `mineru-api` 容器需要能访问 LLM base_url。
- v1 依赖 GPU compose 单并发，避免多个任务抢写共享 runtime config。

### 6. Cloud 文档转换旁路流

1. document task 读取到 mode 为 `cloud`。
2. title aided 准备流直接跳过。
3. DocumentProcessor 使用 MinerUCloudConverter。
4. MinerUCloudConverter 按现有 v4 Smart Parsing API 提交、轮询、下载 ZIP、解析结果。
5. Newbee 保存 cloud 结果。

输出目标：Newbee 文档存储与后续索引流程。

关键约束：

- cloud 请求不包含 title aided 字段。
- cloud 模式不要求本地 `mineru-api` 存在。
- cloud 结果不经过 Newbee title aided 后处理。

---

## 三、Interface Definition（接口定义）

### 1. Config API：读取模型配置

逻辑接口：`GET /api/v1/config/models`

输入含义：

- 当前用户请求读取模型配置。

输出含义：

- `mineru.mode`
- `mineru.local_enabled`
- `mineru.title_aided_enabled`
- `mineru.api_key_set`
- `llm.api_key_set`（来自现有 LLM 配置摘要，用于诊断 title aided 是否能复用聊天 LLM）
- 当前 LLM provider/model 摘要

同步特性：HTTP 同步接口。

契约重点：

- 不返回任何 API key。
- local 模式的 MinerU API key 状态应为 not applicable。

### 2. Config API：更新 MinerU 配置

逻辑接口：`PUT /api/v1/config/mineru`

输入含义：

- MinerU mode。
- title aided 开关。

输出含义：

- 更新后的 `Effective MinerU Config` 摘要。

同步特性：HTTP 同步接口。

契约重点：

- `mode=local` 但 local 未启用时拒绝。
- `title_aided_enabled` 应可在 mode 不变时单独更新。
- 更新接口不接收 provider/model/api_key/base_url。

### 3. Config API：重置 MinerU 配置

逻辑接口：`POST /api/v1/config/mineru/reset`

输入含义：

- 用户请求恢复 MinerU 配置默认值。

输出含义：

- 默认 mode、local_enabled、title_aided_enabled。

同步特性：HTTP 同步接口。

契约重点：

- 删除 `mineru.*` 持久配置。
- 不影响 LLM provider/model 配置。

### 4. LLM Runtime Config 读取接口

逻辑接口：`resolve_llm_runtime_config(session)`

输入含义：

- 数据库 session。

输出含义：

- 聊天 LLM 的 provider、model、api_key、base_url、temperature、max_tokens、top_p。

异步特性：异步内部接口。

契约重点：

- 缺少 API key 时返回明确错误。
- title aided 模块只消费结果，不改变 LLM 配置。
- title aided 启用判定以该 runtime resolver 为准，不以 Config API 的 `resolve_llm_api_key()` 摘要状态替代，避免 OPENAI-compatible fallback 规则不一致。

### 5. Title Aided Runtime 准备接口

逻辑接口：`prepare_mineru_title_aided_runtime(effective_mineru_config, llm_runtime_config)`

输入含义：

- MinerU 有效配置。
- 聊天 LLM runtime config。

输出含义：

- title aided 是否启用。
- runtime 文件是否写入。
- skip reason 或诊断状态。

同步特性：内部同步或异步接口均可；实际实现应匹配 document task 调用方式。

契约重点：

- cloud mode 返回 skipped。
- local mode + disabled 开关返回 disabled，并原子写入 disabled runtime config。
- local mode + missing API key 返回 skipped/disabled，不暴露 key，并原子写入 disabled runtime config。
- local mode + valid LLM config 原子写入 runtime config。

### 6. Runtime Config File

逻辑接口：`data/mineru/mineru-runtime.json`

输入含义：

- Newbee 写入 MinerU title aided runtime 配置。

输出含义：

- 本地 `mineru-api` 读取 `llm-aided-config.title_aided`。

交互特性：文件系统共享接口。

契约重点：

- 文件路径位于 git ignored 目录。
- 写入必须原子化。
- 文件可能包含 API key，不得被日志或测试快照打印。

### 7. Local MinerU API

逻辑接口：`POST /file_parse`

输入含义：

- PDF 文件。
- backend、page range、return flags、language 等现有参数。

输出含义：

- ZIP 格式的 markdown、metadata assets、images。

同步特性：HTTP 同步接口，实际内部可能排队执行。

契约重点：

- Newbee 不新增请求级 title aided 字段。
- title aided 由本地 `mineru-api` runtime config 决定。

### 8. Docker GPU Runtime Contract

逻辑接口：`docker-compose.gpu.yml`

输入含义：

- 本地 GPU 部署配置。

输出含义：

- `mineru-api` 可以读取共享 runtime config。
- `mineru-api` 使用 Newbee patched GPU 镜像。

契约重点：

- cloud compose 不依赖该 runtime。
- GPU compose 需要挂载 `data/mineru/`。
- `NEWBEE_MINERU_TITLE_AIDED_CONFIG_JSON` 指向共享 runtime config 文件；不改写 MinerU 原生 `MINERU_TOOLS_CONFIG_JSON`。
- Dockerfile 必须应用 Newbee runtime adapter patch，否则本地 `mineru-api` 可能仍只在 import 阶段读取旧配置。

---

## 四、Data Ownership & Responsibility（数据归属与责任）

| 数据 | 创建者 | 更新者 | 消费者 | 责任边界 |
|------|--------|--------|--------|----------|
| `mineru.title_aided_enabled` | Config API | Config API / reset | config_db、前端 | 用户意图开关 |
| `Effective MinerU Config` | config_db | 每次读取重新计算 | Config API、document task | 不单独持久化 |
| `LLM Runtime Config` | LLM 模块 | LLM 配置 API / env | title aided 编排器、聊天链路 | title aided 只读 |
| `MinerU Title Aided Runtime Config` | title aided 编排器 | 文档转换前重算 | runtime file writer | 从有效配置推导 |
| `data/mineru/mineru-runtime.json` | title aided writer | title aided writer | local `mineru-api` | 敏感运行时文件 |
| `/file_parse` 请求 | MinerULocalConverter | 每次转换创建 | local `mineru-api` | 不含 title aided 字段 |
| `Title Level Result` | local MinerU | local MinerU | Newbee 存储/索引 | Newbee 不改写 |
| cloud ZIP 结果 | MinerU cloud | MinerU cloud | MinerUCloudConverter | 不参与 title aided |

---

## 五、数据流自检

- [x] 可以清楚说明配置从设置面板到 app_settings 的流向。
- [x] 可以清楚说明聊天 LLM 配置如何进入本地 MinerU runtime。
- [x] cloud 模式没有被注入 title aided 参数或后处理。
- [x] 所有接口都服务于明确数据流。
- [x] API key 只进入内存和 ignored runtime 文件。
- [x] 明确了最终标题层级结果归 MinerU local 生成。
