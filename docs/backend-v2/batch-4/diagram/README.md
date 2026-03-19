# batch-4 / diagram 模块概述

## 模块定位

diagram 模块负责 Newbee Notebook 中图表功能的全部后端逻辑，包含数据持久化、格式校验、Agent 技能集成，以及对外暴露的 REST API。

本模块是 batch-4 的核心交付物，与 batch-3 建立的 Skill 基础设施（SkillRegistry、ConfirmationGateway、AgentLoop 确认机制）协同工作，不重复实现已有基础设施。

## 设计原则

- 图表类型通过 DiagramTypeRegistry 注册，新增类型无需修改 DiagramService 主体逻辑
- 统一使用 `/diagram` 单入口命令，类型由 Agent 判断，必要时通过确认卡片确认
- 图表内容（JSON 或 Mermaid 语法）存储在 MinIO，元数据存储在 PostgreSQL
- 用户对节点的位置调整与 AI 生成的图表内容分离存储，互不覆盖
- Agent 对图表的创建、更新、删除操作均须通过 Skill 工具调用，不暴露直接写接口
- 需要确认的操作（类型不明确时的 create 前确认、update、delete）复用 batch-3 确认机制

## 文档索引

| 文件 | 内容 |
|------|------|
| [01-goals-duty.md](./01-goals-duty.md) | 设计目标、模块职责与边界 |
| [02-data-model.md](./02-data-model.md) | 数据库表结构、MinIO 存储路径、领域实体 |
| [03-diagram-type-registry.md](./03-diagram-type-registry.md) | DiagramTypeDescriptor、校验器、DIAGRAM_TYPE_REGISTRY |
| [04-service-layer.md](./04-service-layer.md) | DiagramService 接口、DiagramRepository 抽象 |
| [05-skill-provider.md](./05-skill-provider.md) | DiagramSkillProvider、Agent 工具定义、与 batch-3 基础设施的集成点 |
| [06-api-layer.md](./06-api-layer.md) | REST API 规范、请求响应结构、错误码 |
| [07-test.md](./07-test.md) | 测试策略与用例说明 |

## 与其他模块的关系

- **batch-3 note-related-skills**：提供 SkillRegistry、SkillProvider、SkillManifest、ConfirmationGateway 等基础设施，本模块直接复用，不重新实现
- **batch-3 note-bookmark**：本模块的数据模型设计参考 note/mark 实体的命名和级联规则风格
- **batch-4 frontend**：前端 DiagramViewer 消费本模块的 REST API，前端文档见 `docs/backend-v2/batch-4/frontend/`
