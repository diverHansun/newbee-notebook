# llm_title_aided 模块 goals-duty.md

本文档定义 `llm_title_aided` 模块的设计目标与职责边界。

该模块面向 Newbee Notebook 的本地 MinerU GPU 文档解析链路，用于把 MinerU 本地运行时已有的 `llm-aided-config.title_aided` 能力接入到现有文档处理流程中。

---

## 一、模块定位

**一句话说明**：`llm_title_aided` 模块是 Newbee Notebook 对 MinerU 本地标题层级增强能力的后端接入层；它只在 MinerU local/GPU 模式下启用，复用聊天 LLM 的 provider / model / api_key / base_url，把配置同步给本地 `mineru-api`，让 MinerU 在生成中间 JSON 时自行修正标题层级。

**如果没有这个模块**：

- MinerU 默认解析经常只能稳定识别一级标题，二级、三级、四级标题的 `text_level` 容易混乱或退化。
- 用户需要手工维护 MinerU 容器内的 `mineru.json`，无法通过 Newbee 的设置面板统一控制。
- 文档解析和聊天 LLM 配置会割裂，用户会困惑为什么同一个系统里要单独配置一套标题增强模型。
- 本地 GPU 模式与 cloud 模式的能力边界不清晰，容易误以为 MinerU 云端 API 也支持同样的 `llm_title_aided` 字段。

---

## 二、Design Goals（设计目标）

### G1：只接入本地 MinerU 能力

模块只服务 `MINERU_MODE=local` 的本地 GPU 解析链路。本地 `mineru-api` 是执行 MinerU 模型与 `llm-aided-config.title_aided` 的运行时归属。

### G2：不改造 cloud 模式

MinerU cloud API 当前没有公开的 `llm_title_aided` 请求字段，因此本模块不对 cloud 模式注入参数，也不在 Newbee 侧强行做标题后处理。

### G3：复用聊天 LLM 配置

标题增强使用用户已经在 LLM 设置面板中选择的 provider / model / api_key / base_url，不新增一套面向标题分级的模型、密钥或 endpoint 配置。

### G4：用户只面对一个简单开关

用户只需要理解“是否启用 MinerU 本地 LLM 标题分级增强”。模型选择仍然属于聊天 LLM 配置，不把 MinerU 内部 prompt、base_url、api_key、temperature 等细节暴露为独立 UI。

### G5：增强失败不破坏基础文档解析

当本地标题增强无法安全启用时，例如当前 LLM provider 缺少 API key，系统应避免写入不完整的 MinerU title aided 配置，并保留基础 MinerU 文档解析能力。

### G6：标题层级增强不等于标题发现

模块的目标是改善 MinerU 已识别标题候选的层级判断，而不是让 LLM 重新识别 PDF 中所有标题。标题候选仍由 MinerU 原始版面分析负责。

### G7：记录 Zhipu 默认模型的关联变更

Zhipu 默认聊天模型调整为 `glm-5v-turbo`，用于替代当前 `glm-5` 默认值。该调整归属于 LLM preset 策略，本模块只记录它与 title aided 复用聊天 LLM 配置的关系；后续 `docs/backend-v4/img-upload` 的图片上传能力由独立批次负责。

---

## 三、Duties（职责）

### D1：管理标题增强开关

在后端运行时配置中维护 `mineru.title_aided_enabled` 之类的开关状态，并通过现有配置 API 暴露给设置面板。

### D2：判断生效条件

只有同时满足以下条件时，模块才允许标题增强进入文档处理链路：

- MinerU 当前模式为 `local`
- 当前部署允许本地 MinerU
- 用户启用了标题增强开关
- 当前聊天 LLM 配置可以解析出 provider / model / api_key / base_url

### D3：复用聊天 LLM runtime config

在文档处理任务进入 MinerU local 转换前，读取当前聊天 LLM 的 runtime 配置，并把其中的 provider、model、api_key、base_url 转成 MinerU 本地可读取的 title aided 配置。

### D4：同步 MinerU 本地 title aided 配置

负责把 Newbee 的开关与聊天 LLM 配置同步成 MinerU 支持的配置形态：

```json
{
  "llm-aided-config": {
    "title_aided": {
      "enable": true,
      "api_key": "...",
      "base_url": "...",
      "model": "..."
    }
  }
}
```

具体同步方式、配置文件位置、容器挂载和刷新策略在 `architecture.md` 中定义。

### D5：保持 cloud 模式无副作用

当 MinerU 当前模式为 `cloud` 时，本模块不改变 cloud converter 请求参数，不追加本地后处理，不要求本地 `mineru-api` 运行。

### D6：保留 MinerU 输出契约

模块不改变 Newbee 已有的文档解析输出格式。解析结果仍然通过 markdown、image assets、metadata assets、content list、model output 等现有路径进入存储与索引流程。

### D7：协同更新 Zhipu 默认模型策略

把 Zhipu LLM 默认模型从 `glm-5` 调整为 `glm-5v-turbo`，并确保配置重置、可选模型列表和前端默认选择逻辑保持一致。

### D8：记录可诊断状态

当标题增强未生效或被跳过时，后端应留下可诊断的日志信息，但不得输出 API key 或完整敏感配置。

---

## 四、Non-Duties（非职责）

### N1：不支持 MinerU cloud title aided

本模块不为 MinerU cloud 模式设计 `llm_title_aided` 能力。cloud 模式是否支持该能力以 MinerU 官方 API 为准。

### N2：不实现 Newbee 自有标题分级算法

本阶段不在 Newbee 侧实现独立的标题层级后处理算法，不自行重写 content list 或 markdown heading。

### N3：不重新识别标题候选

模块不把正文重新分类成标题，也不做 OCR、版面检测或视觉标题识别。标题候选仍由 MinerU 负责。

### N4：不新增单独的 LLM title aided 配置页

不单独暴露 title aided provider、model、api_key、base_url、prompt、temperature 等配置项。

### N5：不管理用户的 LLM 密钥录入

API key 的来源仍然是现有环境变量和聊天 LLM 配置解析链路。本模块只消费解析后的 runtime config。

### N6：不负责本地 GPU 模型推理本身

GPU 推理、MinerU 模型加载、`hybrid-auto-engine` 执行、显存清理仍属于本地 `mineru-api` 服务与 Docker GPU 部署职责。

### N7：不承诺标题层级 100% 准确

`llm_title_aided` 是 MinerU 对标题层级判断的增强，不是确定性规则系统。不同 LLM 模型、文档排版、标题候选质量都会影响结果。

### N8：不改变嵌入与索引职责

模块只影响文档转换阶段的标题层级质量，不直接修改 embedding、chunking、Elasticsearch、pgvector 等索引模块职责。

---

## 五、设计约束与假设

### 约束

1. MinerU 本地 API `/file_parse` 当前没有请求级 `title_aided` 表单字段，title aided 由 MinerU 运行时配置读取。
2. MinerU cloud API 当前没有公开 `llm_title_aided` 字段，cloud 模式保持原样。
3. Newbee 当前已有 LLM 配置 API 和 runtime config 解析逻辑，本模块应复用，不另起配置系统。
4. 本地 GPU 部署通过 `docker-compose.gpu.yml` 启用 `mineru-api`，cloud 部署不依赖本地 `mineru-api`。
5. API key 不允许写入日志、前端响应或普通文档处理 metadata。

### 假设

1. 用户需要的是“标题层级更合理”，而不是“所有疑似标题都被重新发现”。
2. 用户可以接受标题增强只在 local/GPU 模式生效。
3. 设置面板中 LLM provider/model 的选择是用户对当前系统 LLM 的统一偏好。
4. Zhipu 默认模型切换到 `glm-5v-turbo` 不会破坏现有聊天配置；图片上传能力由 `img-upload` 模块单独设计。
5. 如果用户手动输入其他模型名，系统尊重用户选择，不偷偷替换为隐藏标题模型。

---

## 六、与其他模块的关系

| 模块 | 关系 | 说明 |
|------|------|------|
| Config API | 上游/入口 | 暴露 MinerU 标题增强开关，维护 Zhipu 默认模型与可选模型列表 |
| LLM runtime config | 被依赖 | 提供 provider / model / api_key / base_url |
| Document task | 调用方 | 文档转换前同步 MinerU 与 LLM runtime 配置 |
| DocumentProcessor | 协作方 | 只在 local converter 链路中触发标题增强配置准备 |
| MinerULocalConverter | 协作方 | 仍负责调用本地 `/file_parse`，不承载 cloud 行为 |
| MinerU local API | 外部运行时 | 实际执行 `llm_aided_title()` 并生成带层级的中间 JSON |
| MinerU cloud converter | 非参与方 | 保持现有 cloud v4 API 请求与结果解析逻辑 |
| setting_panel | 轻量入口 | 只增加开关，不新增单独 title aided 模型配置 |
| img-upload | 旁路规划 | 本批次不实现图片上传，仅避免与其默认模型方向冲突 |

---

## 七、文档自检

- [x] 可以用一句话说明模块存在意义：把 MinerU 本地 LLM 标题层级增强接入 Newbee 文档解析链路。
- [x] 明确只服务 local/GPU 模式，不服务 cloud 模式。
- [x] 明确复用聊天 LLM 配置，不新增单独 title aided 配置。
- [x] 明确 title aided 改善的是标题层级，不负责重新发现标题。
- [x] 明确 Zhipu 默认模型调整与后续图片上传能力的关系。
- [x] Duties 可被后续 architecture / dfd-interface / test 文档验证。
