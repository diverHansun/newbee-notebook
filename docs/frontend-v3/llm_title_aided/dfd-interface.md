# llm_title_aided 前端模块 dfd-interface.md

本文档描述本前端模块与外部模块的数据流与接口边界。本文档基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md) 与 [data-model.md](data-model.md)。

---

## 一、Context & Scope（上下文与范围）

`frontend-v3/llm_title_aided` 模块只涉及"设置面板上一个 toggle 与三条 i18n 串"的范围，依赖：

- 后端 Config API：`GET /config/models`、`PUT /config/mineru`、`POST /config/mineru/reset`，已实施完成。
- 现有 [model-config-panel.tsx](../../../frontend/src/components/layout/model-config-panel.tsx) 的 React Query + useState draft 模式。
- 现有 [config.ts](../../../frontend/src/lib/api/config.ts) 的 API client 与类型层。
- 现有 [strings.ts](../../../frontend/src/lib/i18n/strings.ts) 的 i18n 字串体系。

不涉及：MinerU 转换流程、LLM 调用链、后端运行时文件写入。

---

## 二、Data Flow Description（数据流描述）

### 1. 初次渲染流

1. 用户打开 control panel 中的 Model 视图。
2. `model-config-panel` 触发 `useQuery(["models-config"])`，调用 `getModelsConfig()`。
3. 后端返回 `ModelsConfigResponse`，其中 `mineru.title_aided_enabled` 是布尔字段。
4. `useEffect` 将响应通过 `toMinerUDraft` 拷贝为 MinerU Draft，包含 `title_aided_enabled`。
5. JSX 中根据 `draft.mode === "local" && draft.local_enabled` 决定是否渲染 toggle 节。
6. toggle 的 aria-checked 与视觉态由 `draft.title_aided_enabled` 决定。
7. 若 `draft.title_aided_enabled === true && configQuery.data?.llm.api_key_set === false`，渲染一行小字提示。

输出目标：MinerU 卡片 DOM。

关键约束：

- mode 与 local_enabled 都是 draft 来源，不查独立 API。
- 提示文案来自 i18n，不硬编码。

### 2. 切换开关流

1. 用户点击 toggle。
2. handler 计算 `next = !draft.title_aided_enabled`。
3. 立即 `setMineruDraft({ ...draft, title_aided_enabled: next })`（乐观更新）。
4. 调用 `mineruMutation.mutate({ title_aided_enabled: next })`。
5. mutation 成功：onSuccess 用响应再次跑一遍 `setMineruDraft(toMinerUDraft(next))`，权威值压住乐观值。
6. mutation 失败：catch 分支回滚 draft 到上一次 snapshot；现有面板的统一 error banner 显示错误信息。

输出目标：后端 `mineru.title_aided_enabled` 持久化、UI 状态。

关键约束：

- 切换时 PUT body 只含 `title_aided_enabled`，不携带 mode。
- 失败回滚必须以 snapshot 为基准，不基于切换前的 draft（避免连击两次后回滚错位）。

### 3. 切换 mode 流（与本模块的关系）

1. 用户切换 mode segmented control。
2. mineruMutation 发出 `{ mode: "cloud" }` 或 `{ mode: "local" }`。
3. mutation 成功后，draft 更新为新 mode。
4. JSX 重新求值 visibility predicate：
   - 切到 cloud → toggle 节整体不再渲染（但 draft.title_aided_enabled 字段保留，未被前端清空）。
   - 切到 local → toggle 节再次出现，显示后端持久化的最新 title_aided_enabled 值。

关键约束：

- 切到 cloud 不触发对 title_aided_enabled 的清写；后端持久值保留，下次切回 local 仍可见用户上次状态。

### 4. Reset 流

1. 用户点击 "Restore Defaults"。
2. `resetMinerUMutation` 调 `POST /config/mineru/reset`。
3. 后端响应包含 `defaults`，其中含 `title_aided_enabled: false`（后端默认）。
4. 现有 reset onSuccess 流程刷新 query，再 toMinerUDraft，UI 自然反映回默认值。

关键约束：

- 本模块不另写 reset 入口；与 mode 共用一个 "Restore Defaults" 按钮。

---

## 三、Interface Definition（接口定义）

### 1. 读取（沿用现有）

- 名称：`getModelsConfig`
- 路径：`GET /config/models`
- 输入：无
- 输出：`ModelsConfigResponse`，其中 `mineru.title_aided_enabled: boolean` 为本模块新增依赖字段。
- 同步特性：同步 fetch，由 React Query 缓存。

### 2. 更新（扩展现有 payload）

- 名称：`updateMinerUConfig`
- 路径：`PUT /config/mineru`
- 输入：`UpdateMinerUPayload`，本模块用到 `{ title_aided_enabled?: boolean }` 单字段；保留对 mode 字段的既有用法。
- 输出：`MinerUConfig`，包含最新的 `title_aided_enabled`。
- 同步特性：同步返回；前端使用 React Query mutation。
- 错误语义：后端 `UpdateMinerURequest` 校验"mode 与 title_aided_enabled 至少有一个非 None"。前端 toggle 永远只发 title_aided_enabled，命中校验。其他失败由现有错误 banner 处理。

### 3. Reset（沿用现有）

- 名称：`resetMinerUConfig`
- 路径：`POST /config/mineru/reset`
- 输入：无
- 输出：`ResetResponse`，其 `defaults.title_aided_enabled` 为后端默认。
- 同步特性：同步返回。

### 4. 内部接口（组件层）

模块没有跨组件接口；所有数据流都在 model-config-panel.tsx 内部完成。

---

## 四、Data Ownership & Responsibility（数据归属与责任）

### 数据创建

- MinerU Config Snapshot：由 `getModelsConfig` 创建，归属 React Query。
- MinerU Draft：由 `useEffect` + `toMinerUDraft` 创建，归属 model-config-panel useState。
- Update MinerU Payload：由 toggle handler 即时创建，归属 handler 局部。

### 数据更新与销毁

- Snapshot：仅由 React Query 在 invalidate / refetch / mutation onSuccess 时更新。
- Draft：仅由用户操作 + mutation onSuccess + onError 回滚更新；panel unmount 时销毁。
- Payload：mutation 完成后即丢弃。

### 责任边界

- 后端 `llm_title_aided` 模块负责开关的真值与持久化；前端只负责呈现与触发更新。
- LLM 配置模块负责 `api_key_set` 的真值；本模块只读取该信号用于派生提示文案。
- model-config-panel 负责整个 panel 的 layout、错误 banner、加载态；本模块只在 MinerU 卡片内嵌入一个 toggle 节。

### 与其他面板段的隔离

- 本模块不读 LLM / Embedding / ASR draft；不写它们的 mutation。
- 提示文案仅依赖 `configQuery.data?.llm.api_key_set`，与 llm draft 解耦。
