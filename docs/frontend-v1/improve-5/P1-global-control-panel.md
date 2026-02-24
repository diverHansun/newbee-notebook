# P1: 全局控制面板

## 问题描述

当前前端存在以下体验问题：

1. **语言切换入口不一致**：中文/EN 切换控件仅在 Notebook 详情页的 header 中，Notebooks 列表页和 Library 页没有切换入口，违反界面一致性原则
2. **header 空间占用**：语言切换 SegmentedControl 占据了 header 右侧区域，随着功能增多（主题、模型等）header 会持续膨胀
3. **缺少全局配置入口**：主题切换、模型选择、RAG 参数等配置无处安放

## 设计目标

引入一个固定在页面左下角的全局控制面板 Icon，点击后弹出 Split Popover 面板，统一承载所有全局配置功能。

## 交互模式

### Icon

- 位置：页面左下角固定定位，与当前 Next.js Dev Tools 图标位置一致（生产环境后者不存在）
- 样式：圆形按钮，内含 Newbee Notebook 品牌图标（初期使用文字缩写"NB"或蜜蜂图形占位，后续替换为正式品牌图标）
- 尺寸：40px x 40px
- 层级：`z-index: 9999`，确保不被页面内容及 Next.js 15 开发工具浮层遮挡
- 所有页面可见：挂载在根布局 `layout.tsx` 层级

### Split Popover 面板

面板从 Icon 位置向上弹出，分为左右两区（借鉴 Clash Verge 设置界面的左导航 + 右内容排版）：

```
+--------------------+-------------------------------------+
| 🌐 语言            |                                     |
|                    |  ┌─────────────────────────────────┐ |
| 🎨 主题            |  │  界面语言                        │ |
|                    |  │  切换后立即生效，刷新后保持       │ |
| ⚙️ 模型  即将推出   |  │                                 │ |
|                    |  │  [  中文  ] [   EN   ]           │ |
| 📊 RAG   即将推出   |  └─────────────────────────────────┘ |
|                    |                                     |
| 🔌 MCP   即将推出   |                                     |
|                    |                                     |
| ⚡ Skills 即将推出  |                                     |
|                    |                                     |
|--------------------+                                     |
| ℹ️ 关于             |                                     |
+--------------------+-------------------------------------+
```

**左侧导航区**：
- 宽度约 110px，背景色略深于右侧，与右侧以一条浅色分隔线隔开
- 每个菜单项为水平排列的 `[图标] 文字标签`（图标在左，文字在右），行高约 40px
- 当前选中项有高亮背景（`hsl(var(--accent))` 圆角矩形）
- 菜单项列表：语言、主题、模型、RAG、MCP、Skills | 关于
- "关于" 与上方菜单项之间有分隔线，固定在导航区底部
- "模型"、"RAG"、"MCP"、"Skills" 以灰色文字显示，右侧附小字 "即将推出"，不可点击、无 hover 效果
- 可点击项：语言、主题、关于（improve-5 阶段）

**右侧内容区**：
- 宽度约 340px
- 根据左侧选中的 Tab 动态渲染对应模块的卡片内容
- 内容采用 **卡片分组** 布局：每个设置项/信息组包裹在圆角卡片（`border-radius: 8px`、`background: hsl(var(--card))`）中
- 卡片内每个设置项为一行：标签左对齐 + 控件右对齐
- 占位模块（模型/RAG/MCP/Skills）不可通过左侧导航选中，无需渲染右侧内容

**面板整体**：
- 总宽度约 450px，高度自适应内容（最大高度 `max-height: 70vh`，超出时右侧内容区可滚动）
- 圆角 12px、阴影 `box-shadow: 0 8px 32px rgba(0,0,0,0.12)`，与整体设计语言一致
- 点击面板外部自动关闭
- ESC 键关闭

## 各配置模块设计

### 模块一：语言

从 Notebook 详情页 header 中迁移语言切换功能到此面板。

**右侧内容**（卡片布局）：

```
┌─────────────────────────────────────┐
│  界面语言                            │
│  切换后立即生效，刷新后保持           │
│                                     │
│  [  中文  ] [   EN   ]              │
└─────────────────────────────────────┘
```

- 卡片标题：界面语言
- 卡片说明文字：切换后立即生效，刷新后保持（`muted` 色）
- 控件：SegmentedControl，选项 "中文" 和 "EN"

**迁移步骤**：
1. 在控制面板中实现语言切换模块，复用 `useLang()` hook
2. 从 `app-shell.tsx` header 中移除 SegmentedControl
3. 验证 `localStorage` 持久化行为不变

### 模块二：主题

**右侧内容**（卡片布局）：

```
┌─────────────────────────────────────┐
│  配色方案                            │
│  切换界面配色方案                     │
│                                     │
│  [  浅色  ] [  深色  ]              │
└─────────────────────────────────────┘
```

- 卡片标题：配色方案
- 卡片说明文字：切换界面配色方案（`muted` 色）
- 控件：SegmentedControl，选项 "浅色" 和 "深色"

**实现方式 — ThemeProvider（与 LanguageProvider 对称）**：

新增 `lib/theme/theme-context.tsx`，采用与现有 `LanguageProvider` 完全对称的 Context + localStorage 模式：

```typescript
// lib/theme/theme-context.tsx
type Theme = "light" | "dark";

type ThemeContextValue = {
  theme: Theme;
  setTheme: (t: Theme) => void;
};

export const ThemeContext = createContext<ThemeContextValue>(/* ... */);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme") as Theme | null;
    if (saved) setThemeState(saved);
    setMounted(true);
  }, []);

  const setTheme = (t: Theme) => {
    setThemeState(t);
    localStorage.setItem("theme", t);
    // 切换 <html> 元素的 class
    document.documentElement.classList.toggle("dark", t === "dark");
  };

  // hydration guard: 未挂载前不渲染，避免服务端/客户端 class 不匹配
  if (!mounted) return null;

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
```

**设计决策说明**：
- **不使用 Zustand**：主题状态需要与 DOM (`document.documentElement.classList`) 和 `localStorage` 同步，Context + Provider 模式可在 Provider 内部集中管理这些副作用，与 `LanguageProvider` 保持架构一致性
- CSS 变量已在 `globals.css` 中按 `:root`（浅色）和 `.dark`（深色）分别定义，只需切换 `<html>` 的 `dark` class 即可
- 持久化到 `localStorage("theme")`
- 在 `app-provider.tsx` 中注册：`ThemeProvider > LanguageProvider > QueryProvider`

### 模块三：模型配置（backend-v2 阶段实施）

> **范围说明**：本模块涉及新建后端 Settings API 和 YAML 持久化写入，不在 improve-5 阶段实施。improve-5 中「模型」菜单项以占位形式展示（与 MCP/Skills 一致）。以下为 backend-v2 阶段前端实现的完整设计参考。

**右侧内容**：
- 标题：模型配置
- LLM 模型选择：
  - 标签：LLM 模型
  - 控件：下拉选择框（Select）
  - 选项来源：从后端 `GET /api/v1/settings/models` 获取可用模型列表
  - 每个选项显示 provider 名称和模型名
- Embedding 模型选择：
  - 标签：Embedding 模型
  - 控件：下拉选择框
  - 选项来源：同上 API 响应中的 `embedding.available`
- 提示文字：切换后对新会话生效

**确认保存交互**：

模型配置涉及持久化写入后端 YAML 文件，采用「确认后保存」模式：

1. 页面加载时通过 `useQuery` 获取当前配置（服务端状态）
2. 用户修改下拉框时，仅更新组件内的 `useState`（本地表单状态），不立即提交
3. 当本地状态与服务端状态存在差异时，底部显示 **"应用更改"** 按钮（`disabled` 时灰色，`enabled` 时主色调）
4. 点击 "应用更改" 后：
   - 按钮显示 loading spinner，禁用交互
   - 通过 `useMutation` 调用 `PUT /api/v1/settings/models`
   - **成功**：按钮消失，右侧内容区顶部显示绿色内联提示 "✓ 配置已保存"，2 秒后淡出
   - **失败**：本地状态回滚为服务端值，显示红色错误提示 "保存失败：{error.message}"，3 秒后淡出
5. `onSuccess` 回调中调用 `queryClient.invalidateQueries(["settings", "models"])` 刷新缓存

```typescript
// 伪代码示意
const { data: serverConfig } = useQuery({
  queryKey: ["settings", "models"],
  queryFn: () => fetchModelSettings(),
});

const [localLlm, setLocalLlm] = useState(serverConfig?.llm.current_provider);
const [localEmbed, setLocalEmbed] = useState(serverConfig?.embedding.current_provider);

const hasChanges = localLlm !== serverConfig?.llm.current_provider
  || localEmbed !== serverConfig?.embedding.current_provider;

const mutation = useMutation({
  mutationFn: (payload) => updateModelSettings(payload),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["settings", "models"] });
    showFeedback("success", "配置已保存");
  },
  onError: (err) => {
    // 回滚本地状态
    setLocalLlm(serverConfig?.llm.current_provider);
    setLocalEmbed(serverConfig?.embedding.current_provider);
    showFeedback("error", `保存失败：${err.message}`);
  },
});
```

**后端 API 设计**：

需要在 `newbee_notebook/api/routers/settings.py` 中新增路由（当前后端无 settings 路由）：

```
GET  /api/v1/settings/models
  响应: {
    llm: {
      current_provider: "qwen",
      available: [
        { provider: "qwen", model: "qwen3.5-plus" },
        { provider: "zhipu", model: "glm-4.7-flash" },
        { provider: "openai", model: "gpt-4o-mini" }
      ]
    },
    embedding: {
      current_provider: "qwen3-embedding",
      available: [
        { provider: "qwen3-embedding", model: "Qwen3-Embedding-0.6B", mode: "local" },
        { provider: "zhipu", model: "embedding-3", mode: "api" }
      ]
    }
  }

PUT  /api/v1/settings/models
  请求体: {
    llm_provider?: string,
    embedding_provider?: string
  }
  行为: 持久化写入对应 YAML 配置文件（llm.yaml / embeddings.yaml）的 default 字段，
        同时更新运行时配置
  响应: 200 + 更新后的完整配置（与 GET 响应结构一致）
```

**降级策略**：若后端 API 未就绪（请求返回 404/500），前端以只读模式展示，下拉框禁用并显示"后端 API 未就绪"提示。

### 模块四：RAG 设置（backend-v2 阶段实施）

> **范围说明**：本模块涉及新建后端 Settings API 和 YAML 持久化写入，不在 improve-5 阶段实施。improve-5 中「RAG」菜单项以占位形式展示（与 MCP/Skills 一致）。以下为 backend-v2 阶段前端实现的完整设计参考。

**右侧内容**：
- 标题：RAG 检索设置
- 检索分数阈值：
  - 标签：最低相关度分数
  - 控件：Slider + 数值显示
  - 范围：0.0 - 1.0，步长 0.05
  - 当前默认值：0.25（来自 `rag.yaml` 中 `rag.min_relevance` 字段）
  - 说明文字：低于此分数的检索结果将被过滤
- 检索结果数量（Top-K）：
  - 标签：最大检索条数
  - 控件：数字输入框
  - 范围：1 - 20
  - 当前默认值：5（来自 `rag.yaml` 中 `rag.top_k.default` 字段）

**确认保存交互**：

与模型配置模块完全一致的「确认后保存」模式：
- `useQuery` 获取当前 RAG 配置
- `useState` 管理本地表单状态
- 存在差异时显示 "应用更改" 按钮
- `useMutation` 调用 `PUT /api/v1/settings/rag` 持久化
- 成功/失败反馈同模型配置模块

**后端 API 设计**：

```
GET  /api/v1/settings/rag
  响应: {
    score_threshold: 0.25,
    top_k: 5
  }
  字段映射: rag.yaml 中 rag.min_relevance → API score_threshold
           rag.yaml 中 rag.top_k.default → API top_k

PUT  /api/v1/settings/rag
  请求体: {
    score_threshold?: number,
    top_k?: number
  }
  行为: 持久化写入 rag.yaml 对应字段，同时更新运行时配置
  响应: 200 + 更新后的完整配置（与 GET 响应结构一致）
```

**降级策略**：同模型配置，API 未就绪时只读展示默认值。

### 模块五、六：MCP / Skills（占位）

不可通过左侧导航选中，无需渲染右侧内容。仅在左侧导航中以灰色文字 + "即将推出" 小标签展示。

### 模块七：关于

**右侧内容**（卡片布局）：

```
┌─────────────────────────────────────┐
│  应用信息                            │
│                                     │
│  名称          Newbee Notebook      │
│  版本          1.0.0                │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  连接状态                            │
│                                     │
│  后端           🟢 已连接            │
└─────────────────────────────────────┘
```

- **卡片 1**：应用信息
  - 名称行：标签 "名称" + 值 "Newbee Notebook"
  - 版本行：标签 "版本" + 值从 `GET /api/v1/info` 获取（`staleTime: Infinity`）
- **卡片 2**：连接状态
  - 后端行：标签 "后端" + 状态指示（绿色圆点 "已连接" 或红色圆点 "未连接"）
  - 通过 `GET /api/v1/health` 判断（`staleTime: 30_000`，每 30 秒刷新）

## 组件架构

```
layout.tsx
  +-- AppProvider
        +-- ThemeProvider  (新增)
              +-- LanguageProvider
                    +-- QueryProvider
                          +-- ControlPanelIcon  (固定定位，左下角)
                                +-- ControlPanel  (Popover，条件渲染)
                                      +-- LeftNav  (菜单项列表)
                                      +-- RightContent  (动态内容)
                                            +-- LanguageSettings
                                            +-- ThemeSettings
                                            +-- ModelPlaceholder   (待实现，backend-v2)
                                            +-- RagPlaceholder     (待实现，backend-v2)
                                            +-- McpPlaceholder     (待实现)
                                            +-- SkillsPlaceholder  (待实现)
                                            +-- AboutPanel
```

## 状态管理

**面板 UI 状态**：`panelOpen` 和 `activeTab` 作为 `ControlPanelIcon` 组件内部的 `useState` 管理，不需要全局共享（无其他组件需要读取或控制面板开关状态）。

```typescript
// ControlPanelIcon 组件内部
const [panelOpen, setPanelOpen] = useState(false);
const [activeTab, setActiveTab] = useState<
  "language" | "theme" | "model" | "rag" | "mcp" | "skills" | "about"
>("language");
```

**主题状态**：由 `ThemeProvider`（Context API）管理，对称于 `LanguageProvider`。

**语言状态**：继续使用现有的 `LanguageContext` / `useLang()`，不迁移（保持 improve-4 的设计决策）。

**模型配置和 RAG 参数**（backend-v2 阶段）：通过 TanStack Query 从后端获取/更新（`useQuery` + `useMutation`），配合组件内 `useState` 作为本地表单状态，不存储在前端 store 中。

## 样式方案

新增 `frontend/src/styles/control-panel.css`，遵循 improve-4 建立的 CSS 模块化规范：

- 所有类名以 `.control-panel-` 为前缀，避免与现有样式冲突
- 在 `globals.css` 中新增 `@import "../styles/control-panel.css";`
- 使用现有 CSS 变量（`--card`、`--border`、`--accent` 等）保持视觉一致性

关键样式要素：
- Icon 按钮：`position: fixed; bottom: 20px; left: 20px; z-index: 9999;`
- Popover 容器：`position: fixed; bottom: 70px; left: 20px; width: 450px; max-height: 70vh; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.12);` 向上弹出
- 左侧导航：`width: 110px;`，背景略深，flex-column 布局
- 左侧菜单项：`[图标] 文字` 水平排列，`height: 40px; padding: 0 12px; gap: 8px;`
- 选中态：`background: hsl(var(--accent)); border-radius: 6px;`
- 禁用态：`color: hsl(var(--muted-foreground) / 0.5); cursor: default;`
- 分隔线：`border-right: 1px solid hsl(var(--border) / 0.3);`（左右分隔）
- 右侧卡片：`background: hsl(var(--card)); border-radius: 8px; padding: 16px;`，卡片间距 `gap: 12px`
- 卡片内设置行：`display: flex; justify-content: space-between; align-items: center;`
- 过渡动画：`opacity` + `transform: translateY(8px)` 的进出动画
- 保存反馈（backend-v2）：`.control-panel-feedback` 绿色/红色内联文字，`transition: opacity 0.3s` 淡出

## i18n 文本新增

在 `strings.ts` 中新增 `controlPanel` 分区：

```typescript
controlPanel: {
  // ── improve-5 实施 ──
  language: { zh: "语言", en: "Language" },
  theme: { zh: "主题", en: "Theme" },
  model: { zh: "模型", en: "Model" },
  rag: { zh: "RAG", en: "RAG" },
  mcp: { zh: "MCP", en: "MCP" },
  skills: { zh: "Skills", en: "Skills" },
  about: { zh: "关于", en: "About" },
  themeLight: { zh: "浅色", en: "Light" },
  themeDark: { zh: "深色", en: "Dark" },
  interfaceLanguage: { zh: "界面语言", en: "Interface Language" },
  colorScheme: { zh: "配色方案", en: "Color Scheme" },
  appInfo: { zh: "应用信息", en: "App Info" },
  appName: { zh: "名称", en: "Name" },
  connectionStatus: { zh: "连接状态", en: "Connection Status" },
  backend: { zh: "后端", en: "Backend" },
  comingSoon: { zh: "即将推出", en: "Coming soon" },
  connected: { zh: "已连接", en: "Connected" },
  disconnected: { zh: "未连接", en: "Disconnected" },
  version: { zh: "版本", en: "Version" },
  backendStatus: { zh: "后端状态", en: "Backend status" },
  langSwitchHint: { zh: "切换后立即生效，刷新后保持", en: "Effective immediately, persists after refresh" },

  // ── backend-v2 阶段新增（模型/RAG 功能上线时启用）──
  llmModel: { zh: "LLM 模型", en: "LLM Model" },
  embeddingModel: { zh: "Embedding 模型", en: "Embedding Model" },
  modelSwitchHint: { zh: "切换后对新会话生效", en: "Takes effect on new sessions" },
  scoreThreshold: { zh: "最低相关度分数", en: "Min relevance score" },
  topK: { zh: "最大检索条数", en: "Max retrieval count" },
  scoreThresholdHint: { zh: "低于此分数的检索结果将被过滤", en: "Results below this score will be filtered" },
  apiNotReady: { zh: "后端 API 未就绪", en: "Backend API not ready" },
  applyChanges: { zh: "应用更改", en: "Apply Changes" },
  configSaved: { zh: "配置已保存", en: "Configuration saved" },
  saveFailed: { zh: "保存失败", en: "Save failed" },
}
```

## 与现有代码的关系

### 需要移除的代码

- `app-shell.tsx`：header 右侧的 `SegmentedControl`（语言切换）及其相关状态

### 需要保留不变的接口

- `LanguageContext` / `useLang()`：面板中的语言模块通过相同的 hook 操作
- `uiStrings` 结构：所有现有 i18n 调用不受影响
- `localStorage("lang")`：持久化 key 不变

### 新增的全局副作用

- 根布局新增一个固定定位元素（Icon + Popover）
- 主题切换会修改 `document.documentElement` 的 class（添加/移除 `dark`）
- `AppProvider` 中新增 `ThemeProvider` 包裹层

### 新增文件清单（improve-5 阶段）

| 文件 | 说明 |
|------|------|
| `frontend/src/lib/theme/theme-context.tsx` | ThemeProvider + useTheme hook |
| `frontend/src/components/layout/control-panel.tsx` | 全局控制面板主组件（Split Popover） |
| `frontend/src/components/layout/control-panel-icon.tsx` | 左下角 Icon 组件 |
| `frontend/src/styles/control-panel.css` | 控制面板样式 |

### 新增文件清单（backend-v2 阶段）

| 文件 | 说明 |
|------|------|
| `frontend/src/lib/api/settings.ts` | 设置相关 API 调用（fetchModelSettings, updateModelSettings, fetchRagSettings, updateRagSettings） |
| `newbee_notebook/api/routers/settings.py` | 后端 Settings API 路由（4 个端点） |
