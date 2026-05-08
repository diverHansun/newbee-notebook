# llm_title_aided 前端模块 goals-duty.md

本文档定义 `frontend-v3/llm_title_aided` 前端模块的设计目标与职责边界。

该模块在设置面板的 "MinerU Configuration" 卡片中，新增一个 "文档标题辅助识别" 开关，对接 [backend-v4/llm_title_aided](../../backend-v4/llm_title_aided/goals-duty.md) 已实施完成的后端能力。

---

## 一、模块定位

**一句话说明**：`frontend-v3/llm_title_aided` 是 backend `llm_title_aided` 的 UI 入口，把后端 `mineru.title_aided_enabled` 设置投影到设置面板上的一个开关，仅在 MinerU mode = local 时显示。

**如果没有这个模块**：

- 后端 `mineru.title_aided_enabled` 字段已存在但用户无法在前端切换，只能改 DB 或环境变量。
- 用户不知道本地 GPU 模式下还有这层标题层级增强能力。
- 与 LLM 的强相关关系（复用聊天 LLM 配置）没有提示，用户在没有 LLM API key 时也可能误开。

---

## 二、Design Goals（设计目标）

### G1：把"是否启用本地 LLM 标题分级增强"以单一开关呈现

用户只需理解"开/关"。所有"模型选择 / api_key / base_url 复用聊天 LLM"的细节由后端处理，前端不暴露。

### G2：UI 入口紧贴 MinerU mode

开关只在 MinerU mode = local 时出现；mode = cloud 时完全隐藏，避免与 backend goals-duty G1/G2 的"only local"边界相违。

### G3：与现有 model-config-panel 的交互范式一致

切换、reset、错误回滚、加载状态、disabled 时的视觉处理都沿用现有 LLM / Embedding / ASR / MinerU 卡片在面板内的同一套 React Query mutation 模式。

### G4：在没有可用 LLM API key 时给出可见提示

backend goals-duty G5 / D2 已经做了"无 LLM key 则不写入完整 title aided 配置"的兜底。前端在用户主动开启此开关但 LLM api_key_set=false 时也应额外给出文字提示，让用户知道"开了也不会真生效"。

### G5：i18n 与现有面板对齐

新增的全部文案（开关标签、说明文字、提示文字）走 `uiStrings.controlPanel.*` 命名空间，简体中文 + 英文双语对齐既有文案风格。

---

## 三、Duties（职责）

### D1：扩展 frontend config 类型

在 [frontend/src/lib/api/config.ts](../../../frontend/src/lib/api/config.ts) 中扩展 `MinerUConfig` 与 `UpdateMinerUPayload`，让 `title_aided_enabled` 在前端 TypeScript 层成为合法字段。

### D2：在 model-config-panel 中渲染开关

在 MinerU Configuration 卡片下方，紧邻 mode segmented control，渲染 toggle 控件并绑定到 mineru draft state；仅在 mode = local 时显示。

### D3：把切换转成 UpdateMinerU PUT 请求

切换时通过 `updateMinerUConfig({ title_aided_enabled })` 发送增量更新；失败时回滚 draft，让 UI 重新映射服务端真实状态。

### D4：参与 reset 联动

按下 "Restore Defaults" 时，由现有 resetMinerU mutation 一并把 title_aided_enabled 拉回后端默认值，无需额外按钮。

### D5：根据 LLM api_key_set 给出文字提示

当用户开关被打开、但当前 LLM 配置 `api_key_set` 为 false 时，开关下方显示一行小字提示："启用后需要 LLM API key 才能真正生效"。

### D6：在 mode=cloud 时不渲染

不写"开关 disabled" 的视觉，而是直接条件渲染、整体不出现，避免误以为可在 cloud 模式下使用此能力。

### D7：i18n 文案

新增以下 uiStrings 键并在 zh + en 中提供文本：
- `mineruTitleAidedLabel`
- `mineruTitleAidedDescription`
- `mineruTitleAidedRequiresLLMKey`

---

## 四、Non-Duties（非职责）

### N1：不展示模型选择 / api key / base_url

backend goals-duty G3 / G4 已规定 title aided 复用聊天 LLM 配置，不新增配置项。前端尊重这一边界，不在 MinerU 卡片里塞任何 LLM 相关配置控件。

### N2：不在 cloud 模式提供任何可视入口

不画 disabled 开关、不在 tooltip 中暗示"切到 local 就能用"。用户认识到 local 与 cloud 的能力边界是 MinerU mode 切换本身的职责。

### N3：不实现独立 reset 按钮

按 backend goals-duty D7 / 现有面板风格，title_aided 的 reset 复用 MinerU 卡片的 "Restore Defaults"。

### N4：不做 LLM 可用性深度检查

前端不会主动 ping LLM；LLM api_key_set 信号来自既有 `/config/models` 响应。任何更深的"LLM 是否真能调通"都属于 LLM 模块自己的职责。

### N5：不参与文档处理流程

开关只是"用户意图"。文档转换流程是否真启用 title aided 由后端运行时（document task → Runtime Guard → MinerU Title Config Writer）决定，前端不模拟、不查询、不展示其状态。

### N6：不在 onboarding 或全局 banner 暴露此能力

仅作为 MinerU 卡片下的小开关存在，不做"功能引导气泡""新功能提醒"等额外 UI。

---

## 五、设计约束与假设

### 约束

1. 后端已实施：`MinerUConfigResponse.title_aided_enabled: bool`、`UpdateMinerURequest.title_aided_enabled: bool | None`、reset 默认值返回。前端必须严格按此契约对接，不修改后端契约。
2. UpdateMinerURequest 校验是 mode 与 title_aided_enabled "至少有一个非 None"。前端只发送 title_aided_enabled 单字段更新即可命中。
3. UI 容器是 [frontend/src/components/layout/model-config-panel.tsx](../../../frontend/src/components/layout/model-config-panel.tsx)，复用其内部 React Query + draft state 模式。
4. 既有面板使用自定义 SegmentedControl 组件，目前没有现成的 Toggle/Switch 组件。

### 假设

1. 用户已经先选中 MinerU mode = local，再去关心 title aided。开关默认隐藏在 cloud 模式下不会引起困惑。
2. backend goals-duty G7 已规定 Zhipu 默认模型已是 glm-5v-turbo；本前端模块不重复处理"切换 LLM provider 时的默认模型修正"。
3. 现有 i18n 加键流程是修改 `uiStrings`（zh + en 两份），不需要外接 i18n 平台。

---

## 六、与其他模块的关系

| 模块 | 关系 | 说明 |
|------|------|------|
| backend `llm_title_aided` | 上游契约提供方 | 后端已暴露 mineru.title_aided_enabled 读 / 写 / reset |
| frontend `model-config-panel` | 宿主 | 在其 MinerU 卡片中渲染开关，复用其 mutation/draft/i18n 体系 |
| frontend `lib/api/config` | 协作 | 扩展 MinerUConfig 与 UpdateMinerUPayload 类型 |
| frontend `lib/i18n/strings` | 协作 | 新增三条 uiStrings 键 |
| frontend `img-upload`（同期开发） | 无依赖 | 共享设置面板宿主，但开关与图片上传走完全独立路径 |

---

## 七、文档自检

- [x] 一句话能说清模块意义：把后端 mineru.title_aided_enabled 投影成 setting panel 里的一个开关。
- [x] 明确只在 mode=local 时出现。
- [x] 明确不重复 backend 已守住的边界（不暴露 LLM 配置、不做独立 reset）。
- [x] 与现有面板交互范式一致，不引入新的状态管理或 UI 抽象。
- [x] Duties 都能在 architecture / data-model / dfd-interface / test 文档中找到落点。
