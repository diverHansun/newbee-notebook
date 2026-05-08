# llm_title_aided 前端模块 architecture.md

本文档描述 `frontend-v3/llm_title_aided` 前端模块的内部结构与设计选择。设计严格服从 [goals-duty.md](goals-duty.md)：单一开关、仅在 MinerU mode=local 时显示、复用现有面板交互范式、不暴露 LLM 配置。

---

## 一、Architecture Overview（总体架构）

模块极轻，没有独立组件目录或独立 hook。它表现为对既有 [model-config-panel.tsx](../../../frontend/src/components/layout/model-config-panel.tsx) 的**点状扩展**：

1. **API Type Extension（API 类型扩展）**：在 `lib/api/config.ts` 中给 `MinerUConfig` 与 `UpdateMinerUPayload` 加 `title_aided_enabled` 字段。
2. **MinerU Draft Slice（MinerU 草稿切片扩展）**：在 model-config-panel 内部的 `MinerUDraft` 类型与 `toMinerUDraft` 转换函数中加入该字段。
3. **Toggle Section（开关展示节）**：在 MinerU 卡片中、mode segmented control 下方，条件渲染（仅 mode=local）一个 toggle + 描述文字 + 可选 LLM key 提示。
4. **Update Mutation Reuse（更新 mutation 复用）**：直接复用现有 `mineruMutation`，调用方式为 `mineruMutation.mutate({ title_aided_enabled: next })`。
5. **i18n Slot（i18n 槽位）**：在 `lib/i18n/strings.ts` 的 `uiStrings.controlPanel` 命名空间增 3 个键。

### 高层依赖关系

```text
user toggles switch
  -> setMineruDraft(...) (optimistic UI)
  -> mineruMutation.mutate({ title_aided_enabled })
    -> updateMinerUConfig PUT /config/mineru
      -> ModelsConfigResponse.mineru.title_aided_enabled
    -> onSuccess: setMineruDraft(toMinerUDraft(next))
    -> onError: revert draft, surface error banner

user presses Restore Defaults
  -> resetMinerUMutation
    -> POST /config/mineru/reset
      -> defaults include title_aided_enabled
    -> existing onSuccess flow refreshes draft

panel mounts
  -> getModelsConfig
    -> mineru.title_aided_enabled is part of payload
    -> toMinerUDraft maps to draft
    -> render reflects current value
```

### 显示条件

```text
mineruDraft.mode === "local"
  AND
mineruDraft.local_enabled === true
  → render toggle section

mineruDraft.mode === "cloud"
  OR
mineruDraft.local_enabled === false
  → toggle section not rendered
```

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. Point Extension：尽量贴住宿主组件

不为这个开关单独建组件文件、单独 hook 或单独子目录。理由：开关的生命周期、错误处理、reset 都与宿主 model-config-panel 的 MinerU 卡片完全一致；抽出独立组件会引入重复的 mutation 与 draft 同步逻辑，代价大于收益。

服务于 goals-duty **G3（与现有面板交互范式一致）**。

### 2. Conditional Render Over Disabled State

在 mode!=local 时整体不渲染，而不是渲染 disabled 开关。理由：goals-duty N2 明确不做 cloud 模式下的暗示；条件渲染 = 一行 ternary，比 disabled + tooltip 简单且语义更清晰。

服务于 goals-duty **G2 / N2**。

### 3. Single PUT Field

`updateMinerUConfig` 已支持 `mode` 与 `title_aided_enabled` 都为可选；前端切换开关时只发送 `title_aided_enabled`，不携带 mode。理由：避免在切换开关瞬间因为 draft 脏读导致 mode 被误覆盖。

### 4. 不引入新 Toggle 组件库

复用 SegmentedControl 范式，自行实现一个轻量 `<button role="switch" aria-checked>` 即可。理由：项目目前没有 Switch 组件，引入新依赖（如 Radix UI）只为这一个开关不划算；自实现 + ARIA 即可满足无障碍要求。

服务于 architecture-guide 的"不引入未必要的设计模式 / 组件抽象"原则。

### 5. LLM Key Hint Is a Reactive Computation, Not Cross-Module Ask

LLM api_key_set 已在同一份 `getModelsConfig` 响应里返回。提示文字基于 `llmDraft.api_key_set || configQuery.data?.llm.api_key_set` 派生，不需要新发一个 LLM 探活请求。

服务于 goals-duty **G4 / D5**。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

模块没有专属目录，散落在既有前端结构里。本节列出"将被改动的文件"与"改动性质"。

```text
frontend/src/
├ lib/
│  ├ api/
│  │  └ config.ts                    扩展 MinerUConfig + UpdateMinerUPayload
│  └ i18n/
│     └ strings.ts                   新增 3 条 uiStrings.controlPanel.* 键
└ components/
   └ layout/
      ├ model-config-panel.tsx       扩展 MinerUDraft / toMinerUDraft / 渲染 toggle
      └ model-config-panel.test.tsx  增加 toggle 渲染条件 + 切换行为测试
```

新增/扩展的工件：

| 工件 | 类型 | 角色 |
|------|------|------|
| `MinerUConfig.title_aided_enabled` | TS 类型字段 | 前端读模型 |
| `UpdateMinerUPayload.title_aided_enabled` | TS 类型字段 | 前端写模型 |
| `MinerUDraft.title_aided_enabled` | 内部 draft 字段 | 草稿态 |
| `toMinerUDraft` | 函数扩展 | DTO→draft 映射 |
| MinerU 卡片内的 toggle 节 | JSX | UI 表层 |
| `uiStrings.controlPanel.mineruTitleAidedLabel` 等 3 键 | i18n | 文案 |

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 1. 不抽出独立组件文件

**取舍**：放弃了"未来若开关增加可复用性更好"的预设，接受 model-config-panel.tsx 多 30 行 JSX 的代价。
**理由**：目前可见的演进方向不是"让 toggle 在多处复用"，而是"在 MinerU 卡片里继续叠加更多 local-only 字段"，独立组件化反而失焦。

### 2. 不引入第三方 Switch 组件

**取舍**：放弃了 Radix Switch / shadcn Switch 等成熟组件，接受手写 `<button role="switch">` 的代价。
**理由**：项目当前未引入这些库；为单个开关引入会触发依赖审计、tree shaking 评估、视觉风格对齐等问题，不划算。

### 3. 条件渲染选择按 mineruDraft.mode 而非 backend snapshot

**取舍**：放弃了"按服务端最新 mineru.mode 渲染"的方案，接受按本地 draft 渲染（用户切换 mode 后开关会立即出现/消失，但还没 PUT 完成）。
**理由**：与现有 mode segmented control 的 optimistic 行为一致，避免出现 mode 已切换但开关延迟一帧才出现的视觉抖动。

### 4. 不区分 reset 是否影响 title aided

**取舍**：放弃了"为 title aided 单独提供 reset"的方案，接受 reset 把 mode 与 title_aided_enabled 一同回退。
**理由**：与现有 mineruResetMutation 一致；用户语义上 "Restore Defaults" 就是整张卡片回到默认，符合直觉。

### 5. LLM key 提示是文字而非阻断切换

**取舍**：放弃了"LLM 没 key 时就 disable 开关"的方案，接受用户可以打开但不真正生效的状态。
**理由**：backend goals-duty G5 已经做了"无 key 则不写入完整配置"的兜底；前端再阻断会让用户困惑"为什么开关不让我点"，提示文字让用户保留意图、补 key 即可生效。
