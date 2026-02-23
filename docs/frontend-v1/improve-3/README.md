# Frontend V1 Improve-3 阶段

## 阶段目标

在 improve-1（核心性能与 UX 修复）和 improve-2（API 统一、流式稳定性、Provider 适配）的基础上，本阶段聚焦于 **交互体验打磨、流式输出可靠性、信息检索精细化** 三个维度，同时为 improve-4 的中英文国际化做好对齐准备。

## 问题清单

| 编号 | 问题 | 类型 | 复杂度 | 优先级 |
|------|------|------|--------|--------|
| P1 | Explain/Conclude 卡片竖直方向过小 | UI 尺寸 | 低 | P0 |
| P2 | AI 消息生成前空气泡，缺少加载指示器 | UX + 后端 | 中 | P1 |
| P3 | 按钮方块状、圆角不足、输入区布局生硬 | UI 组件 | 中 | P1 |
| P4 | Chat 流式输出中 Tool 调用文本泄漏到前端 | 后端架构 | 中高 | P2 |
| P5 | 文档全部参与 RAG/ES，无法指定搜索范围 | 前后端功能 | 高 | P3 |

## 实施顺序

```
P1 (卡片尺寸) ──> P3 (UI 组件) ──> P2 + P4 (指示器 + 两阶段流式) ──> P5 (Source Selector)
```

P2 与 P4 建议一起实施：P2 定义 `thinking` SSE 事件格式、前端 ThinkingIndicator 组件和 Store 扩展；P4 实现两阶段流式架构，通过 PHASE_MARKER 机制在正确时机触发 thinking 事件。两者共享 `SSEEvent.thinking()`、`thinkingStage` store 字段，分工明确，互为前提。

## 国际化对齐策略

当前前端 14 个文件中存在中英文混杂的硬编码字符串。本阶段所有新增的 UI 文本统一写入 `lib/i18n/strings.ts` 常量文件，结构为 `{ zh: string; en: string }`，为 improve-4 的语言切换功能做准备。已有组件中的文本暂不迁移，留待 improve-4 统一处理。

## 回归补充（2026-02-23）

在 improve-3 主线功能实现后，结合 improve-1 / improve-2 回归测试补充修复了两项前端边界问题：

1. **`Ask` 模式 SSE 超时未触发 fallback**
   - 根因：前端只在 `onError`（网络/解析异常）分支触发非流式 `/chat` 降级；后端 `chat_service.py` 的 chunk 超时通过 SSE `{"type":"error","error_code":"timeout"}` 正常返回，不会进入 `onError`。
   - 修复：`useChatSession.ts` 在 `onEvent(error)` 中识别 `error_code === "timeout"`，复用与 `onError` 相同的 fallback 逻辑，自动改走 `/chat`。

2. **手动取消流式后显示原始 `cancelled` 文案**
   - 根因：取消后仅写入 `status: "cancelled"`，UI 直接显示内部状态枚举字符串。
   - 修复：
     - `message-item.tsx` 对状态文案做本地化映射（`cancelled -> 已取消`）
     - `useChatSession.ts` 在取消时若 assistant 占位消息尚无内容，直接删除该消息，避免空气泡/状态残留

## 文档索引

| 文件 | 内容 |
|------|------|
| [P1-explain-card-resize.md](P1-explain-card-resize.md) | Explain/Conclude 卡片尺寸调整 |
| [P2-thinking-indicator.md](P2-thinking-indicator.md) | AI 思考指示器设计与 SSE 事件扩展 |
| [P3-ui-components-polish.md](P3-ui-components-polish.md) | 全局圆角升级与输入区重设计 |
| [P4-two-phase-streaming.md](P4-two-phase-streaming.md) | 两阶段流式输出方案 |
| [P5-source-selector.md](P5-source-selector.md) | 可选 Sources 功能（前后端） |

## 涉及的主要文件

### 前端

- `components/chat/explain-card.tsx` — P1
- `lib/api/types.ts` — P2（`SseEvent` 新增 `thinking` 分支）
- `components/chat/message-item.tsx` — P2, P3
- `components/chat/chat-input.tsx` — P3, P5
- `components/chat/chat-panel.tsx` — P5
- `lib/hooks/useChatSession.ts` — P2（thinking 业务处理）, P5
- `lib/hooks/useChatStream.ts` — P2（透传 thinking 事件给 useChatSession 回调）
- `lib/utils/sse-parser.ts` — 无需修改，事件类型由 `types.ts` 决定
- `stores/chat-store.ts` — P2, P5
- `app/globals.css` — P1, P2, P3
- `lib/i18n/strings.ts` — 新增，P2-P5 共用

### 后端

- `application/services/chat_service.py` — P2, P4, P5
- `core/engine/modes/chat_mode.py` — P4
- `api/routers/chat.py` — P2, P5
- `api/models/requests.py` — P5
