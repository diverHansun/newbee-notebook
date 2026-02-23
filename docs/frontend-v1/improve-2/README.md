# frontend-v1 improve-2 优化文档索引

## 概述

本阶段（improve-2）针对 frontend-v1 模块在功能测试和代码审查中发现的问题进行系统性修复与优化。
问题涵盖 API 层一致性、阅读器交互体验、会话管理 UX，以及前后端联调稳定性。

## 问题清单

| 编号 | 问题 | 影响范围 | 状态 | 文档 |
|------|------|----------|------|------|
| P1 | `lib/api/chat.ts` 绕过统一 API 客户端，导致错误处理逻辑重复 | API 层一致性 | 已修复 | [01-api-layer-refactor.md](./01-api-layer-refactor.md) |
| P2 | 文字选中时蓝色菜单位置随选择方向偏移，反向选择时定位错误 | 阅读器交互 | 已修复 | [02-text-selection-interaction.md](./02-text-selection-interaction.md) |
| P3 | 操作按钮（解释/总结）在用户松开鼠标前即弹出，干扰选择过程 | 阅读器交互 | 已修复 | [02-text-selection-interaction.md](./02-text-selection-interaction.md) |
| P4 | 新建会话需要手动输入标题，缺乏自动命名机制，UX 流程冗余 | 会话管理 | 已修复 | [03-session-creation-ux.md](./03-session-creation-ux.md) |
| P5 | SSE 流被 Next.js rewrite 代理缓冲，导致前端无响应、30 秒后连接超时 | 前后端联调 | 已修复 | [04-sse-stream-cancellation-and-fallback.md](./04-sse-stream-cancellation-and-fallback.md) |
| P6 | Markdown 查看器快速滚动时卡顿，预加载策略保守，缺少 React 渲染优化 | 阅读器性能 | 已修复 | [05-markdown-scroll-performance.md](./05-markdown-scroll-performance.md) |
| P7 | 拖拽选文超出视口触发 autoscroll 时，IntersectionObserver 加载新块导致原生选区跳转 | 阅读器交互 | 已修复 | [06-text-selection-drag-scroll-jump.md](./06-text-selection-drag-scroll-jump.md) |
| P8 | 非流式 `/chat` 长请求在 `localhost:3000` 下仍经 `rewrite` 路径，约 30 秒返回 `500 Internal Server Error` | 前后端联调 | 已修复 | [07-provider-switch-regression-and-chat-route-proxy.md](./07-provider-switch-regression-and-chat-route-proxy.md) |
| P9 | 切换 `qwen` provider 后，`explain/conclude` 流式请求在后端 `chat_service` 的 60 秒 chunk timeout 处被截断 | 后端时延/超时策略 | 已修复 | [07-provider-switch-regression-and-chat-route-proxy.md](./07-provider-switch-regression-and-chat-route-proxy.md) |

> P2 与 P3 共用同一份文档，根本原因相同，联合修复。
> P6 与 P7 在实现上有关联：P6 的预加载距离扩大是 P7 冻结机制的配套优化，已同步实施。
> P8 与 P9 是切换 LLM provider 后在联调阶段新增暴露的问题，属于 improve-2 收尾阶段。

## 文档结构

```
docs/frontend-v1/improve-2/
  README.md                                    本文件，总索引
  01-api-layer-refactor.md                     P1: API 层统一化重构
  02-text-selection-interaction.md             P2+P3: 文字选中交互修复
  03-session-creation-ux.md                    P4: 新建会话 UX 优化
  04-sse-stream-cancellation-and-fallback.md   P5: SSE 取消与非流式降级
  05-markdown-scroll-performance.md            P6: Markdown 滚动性能
  06-text-selection-drag-scroll-jump.md        P7: 拖选超视口跳转修复
  07-provider-switch-regression-and-chat-route-proxy.md  P8+P9: Provider 切换后的联调回归问题
```

## 修改文件速览

| 文件 | 涉及问题 |
|------|----------|
| `frontend/src/lib/api/chat.ts` | P1（已完成） |
| `frontend/src/lib/api/client.ts` | P1（已完成） |
| `frontend/src/lib/hooks/useTextSelection.ts` | P2, P3（已完成），P7（已完成） |
| `frontend/src/components/reader/selection-menu.tsx` | P2, P3（已完成） |
| `frontend/src/components/chat/chat-panel.tsx` | P4（已完成） |
| `frontend/src/lib/hooks/useChatSession.ts` | P4（已完成），P5（已完成） |
| `frontend/src/app/api/v1/chat/notebooks/[notebookId]/chat/stream/route.ts` | P5（已完成，新增） |
| `frontend/src/components/reader/markdown-viewer.tsx` | P6, P7（已完成），P9（待调优） |
| `frontend/src/stores/reader-store.ts` | P7（已完成） |
| `newbee_notebook/application/services/chat_service.py` | P5（已完成，持久化顺序修正） |
| `frontend/src/app/api/v1/chat/notebooks/[notebookId]/chat/route.ts` | P8（已完成，新增并已命中） |
| `frontend/next.config.ts` | P8（已完成，rewrite 调整为 fallback） |
| `newbee_notebook/api/routers/chat.py` | P5（已完成，SSE heartbeat），P8/P9（联调排查） |
| `newbee_notebook/configs/llm.yaml` | P9（provider 切换实验配置） |

## 工程原则说明

本次修改遵循以下原则：

- **单一职责**：每个模块只做一件事，错误处理归属于统一客户端层
- **最小修改范围**：不引入新的抽象或重构不相关的代码
- **行为驱动**：用户交互逻辑以用户实际操作意图为准，而非事件触发顺序
- **不破坏现有接口**：所有修改保持对外 API 和组件 Props 不变
