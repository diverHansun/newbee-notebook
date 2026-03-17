# Note-Related-Skills 模块

Agent Skill 层的后端设计文档。为 agent 提供通过 `/note` slash 命令激活的笔记和书签操作能力。

## 模块定位

本模块是 note-bookmark 模块 Service 层之上的薄适配层。它将 NoteService 和 MarkService 的操作包装为 ToolDefinition，在 `/note` 命令激活时注入到 agent 的工具列表中。

核心语义区分：用户在 Studio UI 中直接操作笔记和书签是标准前端功能，不属于 skill。Skill 是专门为 agent 准备的技能，只有在用户显式激活后 agent 才能看到并使用这些工具。

## 文档索引

| 文档 | 内容 |
|------|------|
| [01-goals-duty.md](01-goals-duty.md) | 设计目标与职责边界 |
| [02-architecture.md](02-architecture.md) | SkillManifest、SkillRegistry、NoteSkillProvider 架构 |
| [03-tool-definitions.md](03-tool-definitions.md) | Agent 工具定义（参数、描述、返回值） |
| [04-activation-and-confirmation.md](04-activation-and-confirmation.md) | /note 激活流程与破坏性操作确认机制 |
| [05-test.md](05-test.md) | 测试策略 |

## 与其他模块的关系

- **note-bookmark**：本模块复用其 Service 层，不重新实现业务逻辑
- **core/tools**：本模块产出的 ToolDefinition 与内建工具（knowledge_base、time）遵循相同契约
- **core/engine**：AgentLoop 通过 ToolRegistry.get_tools(external_tools=) 接收 skill 注入的工具
- **ChatService**：检测 /note 前缀，触发 skill 激活流程
- **batch-4 skill 系统**：本模块的 SkillManifest/SkillRegistry 抽象是 batch-4 动态 skill 加载的种子框架
