# frontend-v1 improve-2 优化文档索引

## 概述

本阶段（improve-2）针对 frontend-v1 模块在功能测试和代码审查中发现的四个问题进行系统性修复与优化。
问题涵盖 API 层一致性、阅读器交互体验、以及会话管理 UX 三个维度。

## 问题清单

| 编号 | 问题 | 影响范围 | 文档 |
|------|------|----------|------|
| P1 | `lib/api/chat.ts` 绕过统一 API 客户端，导致错误处理逻辑重复 | API 层一致性 | [01-api-layer-refactor.md](./01-api-layer-refactor.md) |
| P2 | 文字选中时蓝色菜单位置随选择方向偏移，反向选择时定位错误 | 阅读器交互 | [02-text-selection-interaction.md](./02-text-selection-interaction.md) |
| P3 | 操作按钮（解释/总结）在用户松开鼠标前即弹出，干扰选择过程 | 阅读器交互 | [02-text-selection-interaction.md](./02-text-selection-interaction.md) |
| P4 | 新建会话需要手动输入标题，缺乏自动命名机制，UX 流程冗余 | 会话管理 | [03-session-creation-ux.md](./03-session-creation-ux.md) |

> P2 与 P3 共用同一份文档，因为它们在代码层面出自同一根本原因，需要联合修复。

## 文档结构

```
docs/frontend-v1/improve-2/
  README.md                        本文件，总索引
  01-api-layer-refactor.md         P1: API 层统一化重构
  02-text-selection-interaction.md P2+P3: 文字选中交互修复
  03-session-creation-ux.md        P4: 新建会话 UX 优化
```

## 修改文件速览

| 文件 | 涉及问题 |
|------|----------|
| `frontend/src/lib/api/chat.ts` | P1 |
| `frontend/src/lib/hooks/useTextSelection.ts` | P2, P3 |
| `frontend/src/components/chat/chat-panel.tsx` | P4 |
| `frontend/src/lib/hooks/useChatSession.ts` | P4 |

## 工程原则说明

本次修改遵循以下原则：

- **单一职责**：每个模块只做一件事，错误处理归属于统一客户端层
- **最小修改范围**：不引入新的抽象或重构不相关的代码
- **行为驱动**：用户交互逻辑以用户实际操作意图为准，而非事件触发顺序
- **不破坏现有接口**：所有修改保持对外 API 和组件 Props 不变
