# Note-Bookmark 模块

Studio 笔记与书签系统的后端设计文档。

## 模块定位

为 Studio Panel 提供笔记（Note）和书签（Mark）的数据管理能力。Note 是全局知识实体，Mark 是文档级位置标记，两者通过引用关系关联。

## 文档索引

| 文档 | 内容 |
|------|------|
| [01-goals-duty.md](01-goals-duty.md) | 设计目标与职责边界 |
| [02-data-model.md](02-data-model.md) | 数据模型、表结构、级联规则 |
| [03-service-layer.md](03-service-layer.md) | MarkService、NoteService 接口设计 |
| [04-api-layer.md](04-api-layer.md) | REST API 端点与请求/响应契约 |
| [05-test.md](05-test.md) | 测试策略 |

## 与其他模块的关系

- **note-related-skills**：Agent Skill 层是本模块 Service 之上的薄适配层，复用相同的业务逻辑
- **前端 Studio Panel**：通过本模块的 REST API 实现笔记编辑、书签管理、交叉导航
- **前端 Markdown Viewer**：通过 Mark API 获取书签数据，在阅读器中渲染高亮标记
