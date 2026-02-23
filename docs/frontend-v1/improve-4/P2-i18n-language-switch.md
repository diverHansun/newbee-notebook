# P2: 国际化与语言切换

## 问题描述

前端存在两类国际化问题：

1. **硬编码中文字符串**：约 10 个文件中的 UI 文本直接写在 JSX 中，无法切换语言
2. **切换机制缺失**：`lib/i18n/strings.ts` 已有双语结构（`{ zh, en }`），但只有辅助函数 `zh()`，没有语言状态管理和切换 UI

## 当前状态

`strings.ts` 已覆盖 `thinking` 和 `sourceSelector` 两个分区，其他所有文本均为硬编码。

硬编码文件清单（来自 improve-3 阶段扫描）：

| 文件 | 主要硬编码文本 |
|------|--------------|
| `chat-input.tsx` | 输入框占位符、按钮 aria-label、RAG 不可用提示、文档计数 |
| `message-item.tsx` | 生成中...、已取消、错误 |
| `chat-panel.tsx` | 新建会话、删除会话、会话计数、空列表提示、确认对话框文本 |
| `sources-card.tsx` | 引用来源、展开更多 |
| `source-card.tsx` | 各文档处理状态标签 |
| `source-list.tsx` | 添加、刷新、从 Library 添加、移除确认文本等 |
| `app-shell.tsx` | 返回列表 |
| `document-reader.tsx` | 文档信息加载失败、重试、返回聊天等多条状态文本 |
| `selection-menu.tsx` | 解释、总结 |
| `explain-card.tsx` | 卡片标题（解释/总结）、加载状态、关闭按钮 aria-label |
| `studio-panel.tsx` | Studio（即将推出） |
| `notebooks/page.tsx` | 页面标题、空状态文字、新建按钮 |
| `library/page.tsx` | 页面标题、空状态文字 |

## 设计方案

### 1. 语言状态管理

新增 `frontend/src/lib/i18n/language-context.tsx`，提供：

- `LanguageContext`：全局语言状态（`"zh" | "en"`）
- `LanguageProvider`：注入到 `AppProvider`，初始值总为 `"zh"`（服务端安全），在 `useEffect` 中从 `localStorage("lang")` 同步，刷新后保持状态
- 语言切换时写入 `localStorage`

**关键：SSR Hydration 安全处理**

Next.js App Router 的 SSR 阶段无法访问 `localStorage`，若 Provider 直接读取 `localStorage` 作为初始值，客户端首帧与服务端产出不一致会触发 hydration mismatch 报错。正确实现：

```tsx
// language-context.tsx
'use client';

const [lang, setLang] = useState<Lang>("zh");  // 服务端/首帧总为 "zh"

useEffect(() => {
  // 客户端首次挂载后同步 localStorage
  const saved = localStorage.getItem("lang") as Lang | null;
  if (saved === "en" || saved === "zh") setLang(saved);
}, []);

// 切换时写入
const switchLang = (next: Lang) => {
  setLang(next);
  localStorage.setItem("lang", next);
  document.documentElement.lang = next === "zh" ? "zh-CN" : "en"; // ← 动态更新 html lang
};
```

> `layout.tsx` 中的 `<html lang="zh-CN">` 为服务端静态值，不做修改；`document.documentElement.lang` 在客户端切换时由 `switchLang` 更新，两者各司其职。

新增 `frontend/src/lib/hooks/useLang.ts`，提供：

```
useLang() → { lang: "zh" | "en"; setLang; t; ti }
```

- `t(str: LocalizedString): string`：替代现有的 `zh()` 函数，根据当前语言自动返回对应文本
- `ti(str: LocalizedString, vars: Record<string, string>): string`：带插值的翻译函数，处理 `{n}` 等占位符，例：`ti(uiStrings.chat.sessionCount, { n: String(count) })`，避免链式 `.replace()` 在多处插值时出错

两个文件均需声明 `'use client'`（依赖 React context 和 localStorage，不可在 Server Components 中使用）。

### 2. strings.ts 扩展

在现有文件中补充以下分区（文本内容如下，供实施时参考）：

```
chat:
  newSession        新建会话 / New session
  deleteSession     删除会话 / Delete session
  sessionCount      {n} / 20 个会话 / {n} / 20 sessions
  emptyMessages     还没有消息，先发第一条。/ No messages yet. Send the first one.
  confirmDelete     确定要删除「{name}」吗？/ Delete "{name}"?
  inputPlaceholderChat    输入消息... / Type a message...
  inputPlaceholderAsk     输入问题（基于文档检索）... / Ask a question (document search)...
  stopGenerate      停止生成 / Stop generating
  sendMessage       发送消息 / Send message
  ragUnavailable    RAG 不可用 / RAG unavailable
  docCount          {selected}/{total} 文档 / {selected}/{total} docs
  removeDoc         移除 {title} / Remove {title}

messageStatus:
  streaming         生成中... / Generating...
  cancelled         已取消 / Cancelled
  error             错误 / Error

sources:
  title             引用来源 / References
  toolResults       工具调用结果 / Tool results
  expandMore        展开更多（共 {n} 条）/ Show more ({n} total)

sourceCard:
  waiting           等待处理 / Waiting
  processing        处理中... / Processing...
  converted         已转换，待索引 / Converted, pending index
  completed         已完成 / Completed
  failed            处理失败 / Failed
  converting        转换文档中... / Converting...

sourceList:
  add               + 添加 / + Add
  refresh           刷新 / Refresh
  addFromLibrary    从 Library 添加 / Add from Library
  cancel            取消 / Cancel
  emptyDocuments    当前 Notebook 还没有文档 / No documents in this notebook

reader:
  loadFailed        文档信息加载失败 / Failed to load document
  retry             重试 / Retry
  backToChat        ← 返回聊天 / Back to chat
  processing        文档正在处理中... / Document is processing...

layout:
  backToList        返回列表 / Back to list

selectionMenu:
  explain           解释 / Explain
  conclude          总结 / Conclude

studio:
  comingSoon        Studio（即将推出）/ Studio (coming soon)
```

### 3. 语言切换 UI

在 `app-shell.tsx` 的顶部导航栏右侧添加语言切换按钮：

- 使用 `SegmentedControl` 组件，选项为 `["中文", "EN"]`
- 宽度约 80px，高度与顶部栏其他按钮一致
- 点击后立即切换，页面文本即时更新（无需刷新）

### 4. 迁移规范

**迁移原则**：

- 迁移时只将硬编码字符串改为 `t(uiStrings.xxx.xxx)`，禁止同时修改组件逻辑
- 带有动态插值的字符串（如 `${n} / 20 个会话`）使用模板函数：`t(uiStrings.chat.sessionCount).replace("{n}", String(n))`
- 每次提交只包含一个文件的迁移，便于 review

**实施顺序（建议）**：

1. `sources-card.tsx` + `message-item.tsx`（改动少，验证方便）
2. `chat-panel.tsx`（改动多，单独提交）
3. `chat-input.tsx`
4. `source-card.tsx` + `source-list.tsx`
5. `explain-card.tsx`（**仅迁移文本字符串**，结构性 sources 展示改动留到批次 D / P3 阶段，避免冲突）+ `selection-menu.tsx`
6. `document-reader.tsx` + `app-shell.tsx` + `studio-panel.tsx`
7. `notebooks/page.tsx` + `library/page.tsx`

## 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/lib/i18n/strings.ts` | 扩展，新增 11 个分区（含 explain-card、studio、notebooks、library） |
| `frontend/src/lib/i18n/language-context.tsx` | 新增（`'use client'`） |
| `frontend/src/lib/hooks/useLang.ts` | 新增（`'use client'`，含 `t()` + `ti()` 插值函数） |
| `frontend/src/components/providers/app-provider.tsx` | 注入 `LanguageProvider` |
| `frontend/src/components/layout/app-shell.tsx` | 新增语言切换 UI |
| `frontend/src/components/chat/sources-card.tsx` | 文本替换 |
| `frontend/src/components/chat/message-item.tsx` | 文本替换 |
| `frontend/src/components/chat/chat-panel.tsx` | 文本替换 |
| `frontend/src/components/chat/chat-input.tsx` | 文本替换 |
| `frontend/src/components/chat/explain-card.tsx` | **仅文本迁移**（结构改动留 P3/批次 D） |
| `frontend/src/components/sources/source-card.tsx` | 文本替换 |
| `frontend/src/components/sources/source-list.tsx` | 文本替换 |
| `frontend/src/components/reader/document-reader.tsx` | 文本替换 |
| `frontend/src/components/reader/selection-menu.tsx` | 文本替换 |
| `frontend/src/components/studio/studio-panel.tsx` | 文本替换 |
| `frontend/src/app/notebooks/page.tsx` | 文本替换 |
| `frontend/src/app/library/page.tsx` | 文本替换 |

## 验证标准

- 切换语言后，所有已迁移文本即时变更，无需刷新
- 刷新后语言选择保持（`localStorage` 持久化）
- 未迁移的文件不受影响（不破坏现有功能）
- `pnpm typecheck` 无 TypeScript 报错
- 中英文切换时布局无错位（验证各语言文本长度差异的适应性）
