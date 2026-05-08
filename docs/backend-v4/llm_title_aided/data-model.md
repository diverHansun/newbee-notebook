# llm_title_aided 模块 data-model.md

本文档描述 `llm_title_aided` 模块中的核心概念与数据归属。该文档是精简概念词典，不定义 ORM、类结构或完整字段清单。

---

## 一、Core Concepts（核心概念）

### 1. MinerU Title Aided Setting

用户对 MinerU 本地标题分级增强的意图开关。

它表示“用户是否希望 local/GPU 文档解析启用 LLM 标题层级增强”，不表示该能力一定会在当前任务中实际生效。

### 2. Effective MinerU Config

后端运行时解析出的 MinerU 有效配置。

它把 DB、环境变量和默认值合并后，告诉文档处理链路当前是 `cloud` 还是 `local`，本地 MinerU 是否可用，以及 title aided 开关是否开启。

### 3. LLM Runtime Config

聊天 LLM 的有效运行时配置。

该概念已经存在于现有 LLM 模块中，本模块只消费它，不重新定义它。对 title aided 来说，它提供 provider、model、api_key、base_url 等信息。

### 4. MinerU Title Aided Runtime Config

写给本地 `mineru-api` 读取的 runtime 配置片段。

它是从 `Effective MinerU Config` 和 `LLM Runtime Config` 推导出来的结果，用于表达 MinerU 所需的 `llm-aided-config.title_aided`。

### 5. MinerU Runtime Config File

worker/API 容器与本地 `mineru-api` 容器共享的配置文件。

该文件位于 ignored runtime 目录，例如 `data/mineru/mineru-runtime.json`。它可能包含 API key，因此属于敏感运行时文件，不属于代码仓库产物。

### 6. Title Level Result

MinerU local 解析输出中的标题层级结果。

它通常表现为 content list 中的 `text_level`，或 middle JSON / markdown heading 中的标题等级。该结果由 MinerU 生成，本模块不在 Newbee 侧直接改写。

---

## 二、Entity / Value Object 区分

### Entity

| 概念 | 身份 | 生命周期 |
|------|------|----------|
| MinerU Title Aided Setting | app_settings key | 由 Config API 创建、更新、重置 |
| MinerU Runtime Config File | 文件路径 | 由 title aided 配置写入器重写或禁用 |

### Value Object

| 概念 | 说明 |
|------|------|
| Effective MinerU Config | 每次读取时计算得到，不单独持久化 |
| LLM Runtime Config | 由 LLM 模块解析得到，本模块只消费 |
| MinerU Title Aided Runtime Config | 从有效配置推导得到，写入 runtime 文件 |
| Title Level Result | MinerU 输出中的结果值，本模块只观察或验证 |

---

## 三、Key Data Fields（关键数据字段）

### MinerU Title Aided Setting

- `title_aided_enabled`：用户是否希望启用 local title aided。
- `source`：该配置来自 DB、环境变量还是默认值。

### Effective MinerU Config

- `mode`：当前 MinerU 模式，取值为 `cloud` 或 `local`。
- `local_enabled`：当前部署是否允许 local 模式。
- `title_aided_enabled`：用户开关在有效配置中的值。
- `api_key_set`：仅用于 cloud 的 MinerU API key 状态；local 模式为 not applicable。

### LLM Runtime Config

- `provider`：聊天 LLM provider，例如 `qwen` 或 `zhipu`。
- `model`：聊天 LLM 当前模型，例如 `qwen3.5-plus` 或 `glm-5v-turbo`。
- `api_key`：调用 LLM 的密钥。该字段敏感，只能在内存和 runtime config 文件中使用。
- `base_url`：OpenAI-compatible endpoint。
- `temperature` / `top_p` / `max_tokens`：聊天 LLM 参数。title aided v1 不把这些参数写入 MinerU runtime config，也不提供独立 UI；MinerU 内部调用策略保持其自身默认行为。

### MinerU Title Aided Runtime Config

- `enable`：写给 MinerU 的实际启用状态。
- `model`：复用聊天 LLM 当前模型。
- `api_key`：复用聊天 LLM 当前 provider 的 API key。
- `base_url`：复用聊天 LLM 当前 provider 的 base URL。
- `enable_thinking`：v1 不作为用户配置项。只有在实现阶段确认某 provider 必须固定关闭思考模式才能稳定返回 JSON 时，才可作为内部兼容字段写入，并需要测试覆盖。

### MinerU Runtime Config File

- `config_version`：保留 MinerU 兼容配置版本或 Newbee runtime 标识。
- `llm-aided-config.title_aided`：MinerU title aided 配置片段。
- `models-dir`：如需要兼容 MinerU 原始配置，可保留或合并现有模型目录配置。

### Title Level Result

- `text`：标题文本，由 MinerU 输出。
- `text_level`：标题层级，由 MinerU title aided 影响。
- `page_idx` / 页码信息：用于验收分析，不作为本模块持久状态。

---

## 四、Lifecycle & Ownership（生命周期与归属）

### 1. 用户开关生命周期

1. 用户在设置面板修改 MinerU title aided 开关。
2. Config API 将开关写入 `app_settings`。
3. 文档处理任务读取 `Effective MinerU Config`。
4. reset MinerU 配置时，该开关恢复默认值。

归属：Config API 与 config_db。

### 2. LLM 配置生命周期

1. 用户在 LLM 设置面板选择 provider/model。
2. LLM 配置模块解析有效 provider/model/api_key/base_url。
3. title aided 模块在 local 文档转换前消费该配置。

归属：LLM 模块。本模块只读取，不写入。

### 3. runtime 文件生命周期

1. 文档任务准备 local MinerU 解析时，title aided 编排器计算 runtime config。
2. 编排器将 runtime config 原子写入 `data/mineru/mineru-runtime.json`。
3. 本地 `mineru-api` 在解析阶段读取该文件。
4. local 模式下，开关关闭或缺少 LLM API key 时，必须写入 disabled config 覆盖旧状态；cloud 模式可以跳过 runtime 文件写入。

归属：title aided 配置写入器。

### 4. 标题层级结果生命周期

1. MinerU local 完成版面分析并收集标题候选。
2. MinerU local 调用 LLM，获得标题层级。
3. MinerU 将层级写回 middle JSON / content list / markdown。
4. Newbee 存储并索引 MinerU 输出结果。

归属：MinerU local API。Newbee 不直接改写结果。

---

## 五、数据边界

### 本模块拥有的数据

- `mineru.title_aided_enabled` 的配置语义。
- `data/mineru/mineru-runtime.json` 的写入与禁用策略。
- title aided 生效/跳过的诊断状态。

### 本模块不拥有的数据

- 聊天 LLM provider/model/api_key/base_url 的来源规则。
- MinerU cloud API 请求与结果。
- MinerU 原始标题候选识别结果。
- 最终 `text_level` 的具体判定算法。
- embedding、chunking、索引数据。

---

## 六、数据安全约束

1. API key 只允许存在于内存和 ignored runtime config 文件中。
2. 日志只记录 provider、model、enabled、skip reason 等非密钥信息。
3. 前端 API 只返回各自配置摘要中的 `api_key_set`，不返回具体 key；MinerU 的 `api_key_set` 表示 cloud MinerU key，LLM 的 `api_key_set` 表示聊天 LLM key。
4. runtime config 文件必须位于 git ignored 目录。
5. 文档处理 metadata 不应记录完整 title aided runtime config。

---

## 七、文档自检

- [x] 概念数量保持克制，没有引入多余领域对象。
- [x] 每个概念都能在 architecture.md 或后续数据流中找到位置。
- [x] 明确了用户开关与实际生效状态的区别。
- [x] 明确了 API key 的归属和安全边界。
- [x] 明确了 Newbee 不拥有最终标题层级算法。
