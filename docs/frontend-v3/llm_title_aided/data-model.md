# llm_title_aided 前端模块 data-model.md

本文档描述本前端模块在 TypeScript 层的核心概念。模块极轻，本份文档比同级 backend 文档更短，仅锁定与开关相关的几个数据形态。

---

## 一、Core Concepts（核心概念）

### 1. MinerU Config Snapshot

后端 `/config/models` 响应中 `mineru` 对象的 TypeScript 投影。

它是 React Query 缓存层 `["models-config"]` 的一部分，只读。组件不直接修改它，而是通过 mutation 触发后端写入并在 onSuccess 中刷新它。

### 2. MinerU Draft

设置面板内部的"用户编辑中"草稿态。

来源是 MinerU Config Snapshot 的复制；用户操作（切 mode、切 title_aided）先写到 draft，再触发 mutation；mutation 失败时 draft 回滚到上一次 snapshot。

### 3. Update MinerU Payload

发往后端 `PUT /config/mineru` 的请求体。

支持 `mode` 与 `title_aided_enabled` 双可选；前端在切换开关时只填 `title_aided_enabled` 单字段，不一并携带 mode。

### 4. LLM Api Key Hint Signal

派生自 `models-config.llm.api_key_set` 的布尔值。

用于决定开关下方是否要展示"启用后需要 LLM API key 才生效"的提示。这是前端展示派生值，不持久化。

### 5. Toggle Visibility Predicate

由 MinerU Draft 派生的可见性谓词：`draft.mode === "local" && draft.local_enabled === true`。

它是模块对 goals-duty G2（仅 local 时显示）的运行期实现。

---

## 二、Entity / Value Object 区分

### Value Object（全部）

| 概念 | 说明 |
|------|------|
| MinerU Config Snapshot | React Query 缓存中的不可变快照，每次 fetch 都是新对象 |
| MinerU Draft | 组件 useState 拥有的可变草稿；切换 mode 或开关时整体替换 |
| Update MinerU Payload | mutation 调用时即时构造，调用结束后丢弃 |
| LLM Api Key Hint Signal | 渲染期派生值 |
| Toggle Visibility Predicate | 渲染期派生值 |

模块没有 Entity；所有数据都是 React Query / useState 管理的 value。

---

## 三、Key Data Fields（关键数据字段）

### MinerU Config Snapshot（前端类型）

- `mode`：当前 MinerU 模式，`"cloud" | "local"`。
- `source`：配置来源（env / db / default），仅展示用途。
- `local_enabled`：当前部署是否允许 local 模式。
- `title_aided_enabled`：本模块新增字段；用户开关的服务端真值。
- `api_key_set`：仅 cloud 模式相关，可能为 null。

### MinerU Draft

- 与 MinerU Config Snapshot 字段一致（不含 source 也行，但保持一致便于对照）。
- 切换 toggle 时 `title_aided_enabled` 立即更新，再异步调 mutation。

### Update MinerU Payload

- `mode?: string`
- `title_aided_enabled?: boolean`
- 切换开关时仅设 `title_aided_enabled`；切换 mode 时仅设 `mode`；不会同时携带。

### LLM Api Key Hint Signal

- 派生自 `configQuery.data?.llm.api_key_set`。
- 当用户已开启 `title_aided_enabled=true` 且 `api_key_set=false` 时，提示"启用后需要 LLM API key 才能真正生效"。
- 当 `title_aided_enabled=false` 时，提示文字隐藏；不打扰未开启此功能的用户。

---

## 四、Lifecycle & Ownership（生命周期与归属）

### MinerU Config Snapshot
- 创建：`getModelsConfig` 在 panel 挂载或 invalidate 时。
- 销毁：React Query 缓存替换或 unmount。
- 归属：React Query。

### MinerU Draft
- 创建：configQuery.data 到达后 `setMineruDraft(toMinerUDraft(...))`。
- 更新：用户每次操作 + mutation onSuccess。
- 回滚：mutation onError 时回到上一次 snapshot。
- 销毁：panel unmount。
- 归属：model-config-panel 组件 useState。

### Update MinerU Payload
- 创建：用户切换 toggle 时即时构造。
- 销毁：mutation 调用结束。
- 归属：toggle handler。

---

## 五、数据边界

### 本前端模块拥有

- 前端 TypeScript 中 `MinerUConfig.title_aided_enabled` 与 `UpdateMinerUPayload.title_aided_enabled` 字段语义。
- model-config-panel 内部 MinerUDraft 的 title_aided_enabled 槽位。
- LLM Api Key Hint Signal 的派生规则。

### 本前端模块不拥有

- 后端 `mineru.title_aided_enabled` 的存储、默认值、cloud/local 边界（属于 backend llm_title_aided）。
- LLM Runtime Config 的解析与持久化（属于 LLM 配置模块 / LLM 设置面板段）。
- MinerU mode 切换的服务端逻辑（属于 backend MinerU 配置模块）。
