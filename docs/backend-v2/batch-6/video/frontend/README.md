# Video 模块 -- 前端设计文档

## 模块定位

Video 前端模块是 Studio 面板中与 Notes、Diagrams 同级的视图板块，为用户提供视频内容总结的触发、进度展示、结果浏览和管理能力。它是后端 Video 模块的 UI 消费层，本身不包含业务逻辑。

## 与后端文档的关系

本目录下的文档描述前端的组件结构、状态管理、数据流和交互设计。业务逻辑、数据模型的语义定义、API 端点的完整规格请参考同级的 [后端设计文档](../backend/README.md)。前端文档中引用的后端概念（如 VideoSummary、platform、summarize pipeline）均以后端文档为准。

## 核心场景

1. 用户在 Studio Video 面板顶部输入 Bilibili URL 或 BV 号，点击按钮触发总结，面板内通过 step indicator 展示实时进度，完成后自动刷新列表
2. 用户在 Video 列表中浏览历史摘要，点击条目进入详情视图查看完整 Markdown 总结
3. 用户在详情视图中将摘要关联到当前 notebook 或取消关联
4. 用户通过主聊天面板的 `/video` 斜杠命令触发 agent 工具调用，agent 完成后 Video 面板通过缓存失效自动刷新数据

## 文档清单

| 序号 | 文档 | 说明 |
|------|------|------|
| 01 | [goals-duty.md](01-goals-duty.md) | 设计目标与职责边界 |
| 02 | [architecture.md](02-architecture.md) | 前端架构设计（组件结构、状态管理、设计模式） |
| 03 | [data-model.md](03-data-model.md) | 前端数据模型（TypeScript 类型、Query Keys、Store State） |
| 04 | [dfd-interface.md](04-dfd-interface.md) | 数据流与接口（API Client、SSE 消费、组件间通信） |
| 05 | [use-case.md](05-use-case.md) | 关键用例（总结流程、列表/详情导航、Notebook 关联、B站登录） |
| 06 | [test.md](06-test.md) | 前端验证策略 |

## 技术栈约束

前端文档中的所有设计均基于项目现有技术栈：

- Next.js 15 + React 19 + TypeScript
- Zustand 5（状态管理）
- TanStack React Query 5（服务端状态与缓存）
- Tailwind CSS 3（样式）

不引入新的框架或状态管理方案。
