# Frontend V1 Improve-4 阶段

## 阶段目标

在 improve-3（交互体验打磨、流式输出可靠性、信息检索精细化）的基础上，本阶段聚焦于 **工程可维护性提升、国际化支持、引用信息精细化、性能调优** 四个维度。

各任务按依赖关系顺序排列：P1 CSS 模块化是后续所有改动的前置条件；P2 国际化在 P1 完成后展开；P3-P5 可并行推进。

## 问题清单

| 编号 | 问题 | 类型 | 复杂度 | 优先级 |
|------|------|------|--------|--------|
| P1 | `globals.css` 1244 行单文件，维护困难 | CSS 工程化 | 中 | P0 |
| P2 | 前端中英文混杂，缺少语言切换机制 | 国际化 | 中 | P1 |
| P3 | 引用来源无论是否相关均显示，Chat 模式尤为突出 | 前后端功能 | 中高 | P1 |
| P4 | explain/conclude 生成速度慢于 ask/chat | 后端性能 | 低 | P2 |
| P5 | 输入框过高 + 用户气泡颜色不合理 + 无自动滚动 | UI/UX | 中 | P1 |

## 实施顺序

```
P1 (CSS 模块化)
      ↓
P2 (国际化 — 机制先行)
      ↓
P4 (性能优化) ──── P5 (UI 打磨)   ← 两者可并行
      ↓
P3 (智能引用来源 — 后端+前端)
```

> **P3 与 P4 的依赖说明（重要更正）**：`chat_mode.py` 已有 `had_tool_calls = bool(getattr(self._runner, "had_tool_calls", False))`，P3 不依赖 P4，两者独立。P3 先于 P5 并非强制，视资源可并行。建议 P4 完成 `skip_condense` 配置化后顺带确认 `ElasticsearchSearchTool._last_raw_results` 的数据结构设计，为 P3 提供明确的接口契约。

## 推荐实施批次

| 批次 | 任务 | 验证重点 |
|------|------|---------|
| **批次 A** | P1 CSS 模块化 | 视觉一致性（目视）+ `pnpm build`（PostCSS/Tailwind 完整编译） |
| **批次 B** | P2 国际化基础设施（LanguageProvider + useLang + 顶栏切换 UI）+ 第一批文本迁移（message-item / sources-card / explain-card 文本） | 语言切换即时生效 + `localStorage` 持久化 + `pnpm typecheck` |
| **批次 C** | P4 性能优化（skip_condense 配置化）+ `ElasticsearchSearchTool._last_raw_results` 接口设计与单测 | TTFT 对比（before/after）+ `test_modes.py` 通过 |
| **批次 D** | P3 智能引用来源（后端 + 前端）| Chat 简单回复无 sources；工具调用显示 ToolResultsCard；Ask sources 有 score 过滤 |
| **批次 E** | P5 UI 打磨（输入框 + 气泡颜色 + 三个滚动 Effect）+ P2 剩余文本迁移 | 滚动行为 + 对比度 + 会话切换定位 |

## 测试与验收策略

### 前端静态检查

- `pnpm typecheck`：TypeScript 类型检查（每批次必做）
- `pnpm build`：批次 A（P1 CSS 拆分后）必做，确认 PostCSS `@import` 路径正确

### 后端单元测试

- `newbee_notebook/tests/unit/test_modes.py`：P4 skip_condense 配置读取
- `newbee_notebook/tests/unit/test_chat_router_sse.py`：P3 SSE `sources_type` 字段扩展
- 新增 `chat_service` 单测：sources 为空时不发事件；score 过滤阈值生效

### Playwright 端到端回归（脚本化 smoke）

- **P3**：Chat 简单回复（不调用工具）→ 消息下方无任何引用 UI；知识库检索 → 显示 `ToolResultsCard`
- **P5**：发送消息 → 自动滚到底部；streaming 中上滚 → 跟随停止；下滚回近底 → 恢复；切换会话 → 定位到底部
- **P2**：点击语言切换 → 所有已迁移文本即时变更；刷新页面 → 语言持久



## 设计约束

- **向后兼容**：P1 是纯重构，`globals.css` 输出的 CSS 类名和变量名不变
- **增量 i18n**：P2 新增语言切换机制，现有文本迁移按文件批量推进，不要求一次完成
- **最小协议扩展**：P3 对 SSE 事件新增 `sources_type` 字段，不修改已有字段
- **单一职责**：P4 仅修改 `skip_condense` 参数，不重构 engine 架构

## 文档索引

| 文件 | 内容 |
|------|------|
| [P1-css-modularization.md](P1-css-modularization.md) | globals.css 拆分方案与快照策略 |
| [P2-i18n-language-switch.md](P2-i18n-language-switch.md) | 语言切换机制设计与文本迁移规范 |
| [P3-smart-sources.md](P3-smart-sources.md) | 智能引用来源（后端过滤 + 前端分类展示） |
| [P4-explain-conclude-perf.md](P4-explain-conclude-perf.md) | explain/conclude 性能诊断与优化 |
| [P5-ui-polish.md](P5-ui-polish.md) | 输入框高度、用户气泡颜色、消息自动滚动 |

## 涉及的主要文件

### 前端

- `frontend/src/app/globals.css` — P1（拆分源文件）
- `frontend/src/styles/*.css` — P1（新增各分区文件）
- `frontend/src/lib/i18n/strings.ts` — P2（扩展文本常量）
- `frontend/src/lib/i18n/language-context.tsx` — P2（新增，语言状态管理）
- `frontend/src/lib/hooks/useLang.ts` — P2（新增，语言 hook）
- `frontend/src/components/layout/app-shell.tsx` — P2（语言切换 UI）
- `frontend/src/components/chat/sources-card.tsx` — P3（拆分为两种展示变体）
- `frontend/src/components/chat/message-item.tsx` — P3、P5（sources 分发、气泡颜色）
- `frontend/src/components/chat/chat-panel.tsx` — P5（自动滚动）
- `frontend/src/components/chat/chat-input.tsx` — P5（输入框高度）
- `frontend/src/lib/api/types.ts` — P3（`sources_type` 字段）

### 后端

- `newbee_notebook/configs/modes.yaml` — P4（新增 `skip_condense` 配置项）
- `newbee_notebook/core/common/config.py` — P4（新增 `get_explain_skip_condense()` / `get_conclude_skip_condense()`）
- `newbee_notebook/core/engine/modes/explain_mode.py` — P3、P4
- `newbee_notebook/core/engine/modes/conclude_mode.py` — P4
- `newbee_notebook/core/engine/modes/chat_mode.py` — P3（sources 逻辑调整）
- `newbee_notebook/application/services/chat_service.py` — P3（SSE sources 事件）

## 实施进度与回归补充（2026-02-23）

### 已完成（代码已落地）

- `P1` CSS 模块化：`globals.css` 已拆分至 `frontend/src/styles/*.css`，保留变量与 Tailwind 入口
- `P2` 国际化：语言上下文、`useLang`、顶栏语言切换、主要页面文本迁移已完成（含 `explain-card.tsx`、`studio-panel.tsx`）
- `P3` 智能引用来源：SSE `sources_type`、前端 `ToolResultsCard/DocumentReferencesCard` 分流、Chat 模式取消事后 pgvector 补查已完成
- `P4` explain/conclude 性能优化：`skip_condense` 已配置化并接入 modes
- `P5` UI 打磨：输入框限高、用户气泡颜色变量、消息自动滚动（含会话切换/历史加载）已完成

### 本轮额外修复（测试中发现）

- `chat-panel` 历史加载自动滚动时机过早：改为短时 `requestAnimationFrame` 跟随到底部，避免 markdown 布局延后导致停在中间
- `chat-input` / `SourceSelector` 循环更新：`onDocsChange` 内联回调导致 `Maximum update depth exceeded`，已改为稳定回调
- `ChatMode._stream()` phase-2 提示词编码损坏（乱码）：已替换为 ASCII 英文提示词，修复工具文本泄漏回归
- `Ask` 分数过滤兼容性：当 sources 全部无有效正分数（如 `0.0` / 缺失）时，不再被阈值过滤全部清空
- `Ask` 展示兜底：当 `document_id` 校验导致 `Ask` sources 全部被清空时，允许保留展示用 sources（Reference 入库仍仅写有效 `document_id`）

### 当前测试现状（重要）

- `Chat` 普通回复：已验证不再显示无关引用卡片
- `Chat` 天气工具场景：已验证不再泄漏 `<tool_call>`
- `Ask`：内容生成正常，但在当前数据环境中多次出现“回答正确但无 `sources` 事件”的情况（含流式与 `/chat` fallback）
  - 说明：该问题已确认不在前端 UI；更像是 `AskMode` 的 post-hoc sources 收集与 agent 实际检索链路存在偏差（`_last_sources` 上游为空）
- `ToolResultsCard`：当前 notebook 数据环境下未稳定复现非空 ES 工具结果（多次 `knowledge_base_search` 查询返回空结果），因此仅完成代码与协议验证，未完成有数据命中的 UI 截图级验证
