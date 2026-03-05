# 前端 UI 设计: Control Panel 模型配置面板

本文档定义前端 Control Panel 中"模型"标签页的交互设计、组件结构、API 对接和 i18n 扩展方案。

---

## 1. 当前状态

### 1.1 Control Panel 结构

`control-panel.tsx` 的导航分为两组:

- **ACTIVE_ITEMS**: `language`, `theme` (功能已实现)
- **DISABLED_ITEMS**: `model`, `rag`, `mcp`, `skills` (标记 "Coming soon")

`model` 当前是 `DisabledNavItem` 类型，渲染为 `is-disabled` 样式，带 `comingSoon` 徽章。

### 1.2 TypeScript 类型约束

```typescript
type ControlPanelTab = "language" | "theme" | "about";  // 仅包含已激活项

type ControlPanelNavIconName =
  | ControlPanelTab
  | "model" | "rag" | "mcp" | "skills";   // 包含所有导航项
```

`ControlPanelTab` 用于 `activeTab` 状态管理和 `onSelectTab` 回调参数，激活 `model` 需要将其加入此类型。

### 1.3 现有 UI 模式

已实现的 `language` 和 `theme` 标签页使用统一的卡片模式:

```
control-panel-card
  ├── control-panel-card-title     (标题)
  ├── control-panel-card-hint      (说明文字)
  └── control-panel-card-body      (控件容器)
        └── SegmentedControl       (分段切换)
```

模型配置面板沿用此模式，通过多张卡片分区展示。

---

## 2. 类型变更

### 2.1 扩展 `ControlPanelTab`

```typescript
// 改造前
export type ControlPanelTab = "language" | "theme" | "about";

// 改造后
export type ControlPanelTab = "language" | "theme" | "model" | "about";
```

### 2.2 调整导航分组

将 `model` 从 `DISABLED_ITEMS` 移入 `ACTIVE_ITEMS`:

```typescript
// 改造前
const ACTIVE_ITEMS: ActiveNavItem[] = [
  { key: "language" },
  { key: "theme" },
  { key: "about" },
];

const DISABLED_ITEMS: DisabledNavItem[] = [
  { key: "model" },
  { key: "rag" },
  { key: "mcp" },
  { key: "skills" },
];

// 改造后
const ACTIVE_ITEMS: ActiveNavItem[] = [
  { key: "language" },
  { key: "theme" },
  { key: "model" },
  { key: "about" },
];

const DISABLED_ITEMS: DisabledNavItem[] = [
  { key: "rag" },
  { key: "mcp" },
  { key: "skills" },
];
```

### 2.3 ActiveNavItem 类型更新

```typescript
type ActiveNavItem = {
  key: ControlPanelTab;  // 自动包含 "model"
};

type DisabledNavItem = {
  key: "rag" | "mcp" | "skills";  // 移除 "model"
};
```

---

## 3. 模型面板布局

### 3.1 整体结构

模型面板由两张独立卡片组成，使用 `control-panel-stack` 容器纵向排列:

```
activeTab === "model"
└── control-panel-stack
    ├── LLM 配置卡片         (LLMConfigCard)
    │   ├── 标题 + 恢复默认按钮
    │   ├── Provider 切换
    │   ├── 模型选择 (输入框 + 预设下拉)
    │   ├── Temperature 滑块
    │   ├── Max Tokens 数值输入
    │   └── Top-p 滑块
    │
    └── Embedding 配置卡片    (EmbeddingConfigCard)
        ├── 标题 + 恢复默认按钮
        ├── Provider 切换
        ├── 模式切换 (仅 qwen3-embedding)
        ├── 模型显示
        └── 切换影响提示
```

### 3.2 LLM 配置卡片

```
┌──────────────────────────────────────────────┐
│  LLM 配置                     [恢复默认]     │
│                                              │
│  Provider                                    │
│  ┌──────┐ ┌──────┐                           │
│  │ Qwen │ │Zhipu │                           │
│  └──────┘ └──────┘                           │
│                                              │
│  模型                                        │
│  ┌──────────────────────────────────┐ ┌──┐  │
│  │ qwen3.5-plus                     │ │▼ │  │
│  └──────────────────────────────────┘ └──┘  │
│  (支持自由输入或从预设列表选择)               │
│                                              │
│  Temperature                          0.70   │
│  ├────────────●──────────────────┤           │
│  0.0                            2.0          │
│                                              │
│  Max Tokens                      32768       │
│  ┌──────────────────────────────────┐        │
│  │ 32768                            │        │
│  └──────────────────────────────────┘        │
│                                              │
│  Top-p                            0.80       │
│  ├──────────────────●────────────┤           │
│  0.0                            1.0          │
└──────────────────────────────────────────────┘
```

#### 模型输入控件

"模型"字段是本方案的核心交互，采用 ComboBox 模式:

- **输入框**: 允许用户直接键入任意模型名称
- **下拉预设**: 点击右侧箭头或聚焦时展示预设选项
- **预设联动**: 选择预设项时自动填充输入框，并切换对应 provider

预设列表:

| 显示名称 | 模型名 | Provider |
|----------|--------|----------|
| Qwen 3.5 Plus | qwen3.5-plus | qwen |
| GLM-4.7-Flash | glm-4.7-flash | zhipu |

选择预设时自动同步 Provider 选择，例如选择 "GLM-4.7-Flash" 后 Provider 自动切换到 "Zhipu"。

#### 参数控件

| 参数 | 控件类型 | 范围 | 步进 | 显示精度 |
|------|----------|------|------|----------|
| Temperature | Slider | 0.0 - 2.0 | 0.05 | 2 位小数 |
| Max Tokens | Number Input | 1 - 131072 | 1024 | 整数 |
| Top-p | Slider | 0.0 - 1.0 | 0.05 | 2 位小数 |

参数控件旁显示当前数值，支持键盘输入精确值。

### 3.3 Embedding 配置卡片

```
┌──────────────────────────────────────────────┐
│  Embedding 配置                 [恢复默认]    │
│                                              │
│  Provider                                    │
│  ┌──────────────┐ ┌──────┐                   │
│  │Qwen3 Embedding│ │Zhipu │                   │
│  └──────────────┘ └──────┘                   │
│                                              │
│  模式 (仅 Qwen3 Embedding 可见)              │
│  ┌──────┐ ┌──────┐                           │
│  │ 本地 │ │ API  │                            │
│  └──────┘ └──────┘                           │
│                                              │
│  模型: text-embedding-v4                     │
│  维度: 1024 (不可修改)                        │
│                                              │
│  ┌─────────────────────────────────────────┐ │
│  │ 切换 Embedding 仅影响后续新文档的索引。   │ │
│  │ 已索引文档需通过重新索引才能迁移。        │ │
│  └─────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

#### 条件显示逻辑

| Provider | 可见控件 | 隐藏控件 |
|----------|----------|----------|
| qwen3-embedding | 模式切换 + 模型 + 维度 | - |
| zhipu | 模型 + 维度 | 模式切换 |

当 `provider=qwen3-embedding` 时:

- `mode=local`: 模型显示为本地模型目录名 (如 `Qwen3-Embedding-0.6B`)
- `mode=api`: 模型显示为 API 模型名 (如 `text-embedding-v4`)

当 `provider=zhipu` 时:

- 模型固定显示 `embedding-3`，无模式切换

#### Embedding 切换提示

底部的警告信息始终可见，使用 `control-panel-card-hint` 样式 (与 language/theme 的提示文字一致)。内容根据语言:

- 中文: "切换 Embedding 仅影响后续新文档的索引。已索引文档需通过重新索引才能迁移。"
- English: "Switching Embedding only affects future document indexing. Re-index is required to migrate existing documents."

---

## 4. 交互流程

### 4.1 初始加载

```
用户打开 Control Panel -> 点击"模型"标签
  |
  v
useQuery("models-config") -> GET /api/v1/config/models
useQuery("models-available") -> GET /api/v1/config/models/available
  |
  v
表单填充当前值 (provider, model, temperature, ...)
预设列表渲染 (来自 available 接口)
```

两个查询并行发起。loading 状态下显示骨架屏或 loading 提示。

### 4.2 LLM 配置变更

```
用户修改 Provider / Model / Temperature / ...
  |
  v
表单状态更新 (本地 state)
  |
  v (失焦 或 确认操作)
useMutation -> PUT /api/v1/config/llm
  |
  ├── 成功: 更新 queryClient 缓存，显示成功反馈
  └── 失败: 回滚本地 state，显示错误信息
```

#### 变更策略

考虑两种方案:

1. **即时保存 (推荐)**: 每个控件变更后自动保存，类似系统偏好设置。优点是操作直觉，缺点是请求频繁。
   - 针对 Slider 控件: 使用 `onChangeEnd` 事件 (鼠标释放时) 触发，避免拖拽过程中频繁请求。
   - 针对输入框: 使用 debounce (500ms) 或失焦时触发。

2. **手动保存**: 底部放置"保存"按钮，用户点击后一次性提交。优点是减少请求，缺点是多一步操作。

推荐方案一 (即时保存)，与现有 language/theme 切换的交互模式一致。

### 4.3 Embedding 配置变更

```
用户切换 Embedding Provider 或 Mode
  |
  v
显示确认提示: "切换将影响后续文档索引，确定吗?"
  |
  ├── 确认: useMutation -> PUT /api/v1/config/embedding
  └── 取消: 回滚
```

Embedding 切换需额外的确认步骤，因为影响范围较大 (已索引文档不可见于新 provider)。

### 4.4 恢复默认

```
用户点击"恢复默认"
  |
  v
显示确认提示: "确定将 LLM/Embedding 配置恢复为系统默认值?"
  |
  ├── 确认: useMutation -> POST /api/v1/config/llm/reset 或 embedding/reset
  │   |
  │   v
  │   更新表单为返回的 defaults 值
  │   invalidateQueries(["models-config"])
  └── 取消: 无操作
```

---

## 5. 组件拆分

### 5.1 新增组件

| 组件 | 路径 | 职责 |
|------|------|------|
| `ModelConfigPanel` | `components/layout/model-config-panel.tsx` | 模型标签页顶层组件 |
| `LLMConfigCard` | `components/layout/model-config-panel.tsx` | LLM 配置卡片 |
| `EmbeddingConfigCard` | `components/layout/model-config-panel.tsx` | Embedding 配置卡片 |
| `ModelComboBox` | `components/ui/model-combo-box.tsx` | 模型输入 + 预设下拉组合控件 |
| `SliderField` | `components/ui/slider-field.tsx` | 带标签和数值显示的 Slider 控件 |

### 5.2 组件层次

```
ControlPanel (control-panel.tsx)
  └── activeTab === "model"
      └── ModelConfigPanel
          ├── LLMConfigCard
          │   ├── SegmentedControl (provider)
          │   ├── ModelComboBox (model + presets)
          │   ├── SliderField (temperature)
          │   ├── NumberInput (max_tokens)
          │   └── SliderField (top_p)
          └── EmbeddingConfigCard
              ├── SegmentedControl (provider)
              ├── SegmentedControl (mode, 条件显示)
              └── 只读字段 (model, dim)
```

### 5.3 在 `control-panel.tsx` 中集成

```tsx
{activeTab === "model" && <ModelConfigPanel />}
```

`ModelConfigPanel` 作为独立模块导入，保持 `control-panel.tsx` 简洁。

---

## 6. API 客户端

### 6.1 新增 `lib/api/config.ts`

```typescript
import { apiFetch } from "./client";

// === 类型定义 ===

export interface LLMConfig {
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  source: string;
}

export interface EmbeddingConfig {
  provider: string;
  mode: string | null;
  model: string;
  dim: number;
  source: string;
}

export interface ModelsConfig {
  llm: LLMConfig;
  embedding: EmbeddingConfig;
}

export interface PresetModel {
  name: string;
  label: string;
}

export interface AvailableModels {
  llm: {
    providers: string[];
    presets: PresetModel[];
    custom_input: boolean;
  };
  embedding: {
    providers: string[];
    modes: string[];
    api_models: PresetModel[];
    local_models: string[];
  };
}

export interface UpdateLLMPayload {
  provider: string;
  model: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
}

export interface UpdateEmbeddingPayload {
  provider: string;
  mode?: string;
  api_model?: string;
}

export interface ResetResponse {
  message: string;
  defaults: Record<string, unknown>;
}

// === API 函数 ===

export async function getModelsConfig(): Promise<ModelsConfig> {
  return apiFetch<ModelsConfig>("/config/models");
}

export async function getAvailableModels(): Promise<AvailableModels> {
  return apiFetch<AvailableModels>("/config/models/available");
}

export async function updateLLMConfig(payload: UpdateLLMPayload): Promise<LLMConfig> {
  return apiFetch<LLMConfig>("/config/llm", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function updateEmbeddingConfig(
  payload: UpdateEmbeddingPayload,
): Promise<EmbeddingConfig> {
  return apiFetch<EmbeddingConfig>("/config/embedding", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function resetLLMConfig(): Promise<ResetResponse> {
  return apiFetch<ResetResponse>("/config/llm/reset", { method: "POST" });
}

export async function resetEmbeddingConfig(): Promise<ResetResponse> {
  return apiFetch<ResetResponse>("/config/embedding/reset", { method: "POST" });
}
```

### 6.2 TanStack Query Hooks

在 `ModelConfigPanel` 中使用:

```typescript
// 读取当前配置
const configQuery = useQuery({
  queryKey: ["models-config"],
  queryFn: getModelsConfig,
  staleTime: 60_000,
});

// 读取可用选项
const availableQuery = useQuery({
  queryKey: ["models-available"],
  queryFn: getAvailableModels,
  staleTime: Infinity,  // 启动后不变
});

// 更新 LLM
const llmMutation = useMutation({
  mutationFn: updateLLMConfig,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["models-config"] }),
});

// 更新 Embedding
const embeddingMutation = useMutation({
  mutationFn: updateEmbeddingConfig,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["models-config"] }),
});

// 恢复默认
const resetLLMMutation = useMutation({
  mutationFn: resetLLMConfig,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["models-config"] }),
});

const resetEmbeddingMutation = useMutation({
  mutationFn: resetEmbeddingConfig,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["models-config"] }),
});
```

---

## 7. i18n 扩展

### 7.1 新增 i18n 字符串

在 `lib/i18n/strings.ts` 的 `controlPanel` 部分新增:

```typescript
// LLM 配置
llmConfig: { zh: "LLM 配置", en: "LLM Configuration" },
llmProvider: { zh: "Provider", en: "Provider" },
llmModel: { zh: "模型", en: "Model" },
llmModelHint: { zh: "从预设中选择，或输入自定义模型名称", en: "Select a preset or enter a custom model name" },
temperature: { zh: "Temperature", en: "Temperature" },
maxTokens: { zh: "Max Tokens", en: "Max Tokens" },
topP: { zh: "Top-p", en: "Top-p" },

// Embedding 配置
embeddingConfig: { zh: "Embedding 配置", en: "Embedding Configuration" },
embeddingProvider: { zh: "Provider", en: "Provider" },
embeddingMode: { zh: "模式", en: "Mode" },
embeddingModeLocal: { zh: "本地", en: "Local" },
embeddingModeApi: { zh: "API", en: "API" },
embeddingModel: { zh: "模型", en: "Model" },
embeddingDim: { zh: "维度", en: "Dimension" },
embeddingSwitchWarning: {
  zh: "切换 Embedding 仅影响后续新文档的索引。已索引文档需通过重新索引才能迁移。",
  en: "Switching Embedding only affects future document indexing. Re-index is required to migrate existing documents.",
},

// 通用
restoreDefaults: { zh: "恢复默认", en: "Restore Defaults" },
restoreDefaultsConfirm: { zh: "确定恢复为系统默认配置?", en: "Restore to system defaults?" },
embeddingSwitchConfirm: {
  zh: "切换将影响后续文档索引，确定继续?",
  en: "This will affect future document indexing. Continue?",
},
configSaved: { zh: "配置已保存", en: "Configuration saved" },
configResetDone: { zh: "已恢复默认配置", en: "Configuration reset to defaults" },
```

---

## 8. 样式扩展

### 8.1 新增 CSS 规则

在 `control-panel.css` 中追加:

```css
/* 恢复默认按钮 */
.control-panel-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.control-panel-reset-btn {
  font-size: var(--font-sm);
  color: var(--color-text-muted);
  cursor: pointer;
  background: none;
  border: none;
  padding: 2px 8px;
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
}

.control-panel-reset-btn:hover {
  color: var(--color-text);
  background: var(--color-bg-hover);
}

/* Slider 字段 */
.control-panel-slider-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.control-panel-slider-header {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-sm);
}

.control-panel-slider-value {
  font-variant-numeric: tabular-nums;
  color: var(--color-text-muted);
}

/* 数值输入字段 */
.control-panel-number-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.control-panel-number-input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-input);
  color: var(--color-text);
  font-size: var(--font-sm);
}

/* 警告提示 */
.control-panel-warning {
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--color-bg-warning);
  color: var(--color-text-warning);
  font-size: var(--font-sm);
  line-height: 1.4;
}

/* ComboBox */
.model-combo-box {
  position: relative;
}

.model-combo-box-input {
  width: 100%;
  padding: 6px 32px 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-input);
  color: var(--color-text);
  font-size: var(--font-sm);
}

.model-combo-box-toggle {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-muted);
}

.model-combo-box-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--color-bg-popover);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  box-shadow: var(--shadow-popover);
  z-index: 10;
  max-height: 200px;
  overflow-y: auto;
}

.model-combo-box-option {
  padding: 8px 12px;
  cursor: pointer;
  font-size: var(--font-sm);
}

.model-combo-box-option:hover {
  background: var(--color-bg-hover);
}

/* 只读字段行 */
.control-panel-readonly-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: var(--font-sm);
}

.control-panel-readonly-label {
  color: var(--color-text-muted);
}
```

---

## 9. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/components/layout/control-panel.tsx` | 修改 | 扩展 `ControlPanelTab` 类型，移动 model 到 ACTIVE_ITEMS，添加 model 面板渲染 |
| `src/components/layout/model-config-panel.tsx` | 新增 | ModelConfigPanel / LLMConfigCard / EmbeddingConfigCard |
| `src/components/ui/model-combo-box.tsx` | 新增 | ComboBox 组件 |
| `src/components/ui/slider-field.tsx` | 新增 | Slider 封装组件 |
| `src/components/layout/control-panel.css` | 修改 | 追加模型面板相关样式 |
| `src/lib/api/config.ts` | 新增 | 配置 API 客户端函数和类型 |
| `src/lib/i18n/strings.ts` | 修改 | 追加模型配置相关 i18n 字符串 |
