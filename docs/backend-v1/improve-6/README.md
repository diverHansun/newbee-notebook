# Improve-6: 记忆架构重构、删除逻辑修正与 API 补全

## 1. 阶段背景

在 improve-5 完成文档处理可靠性优化和 notebook 作用域收敛后，test-2 全链路测试暴露了四个需要治理的架构级问题:

1. **Explain/Conclude 模式无记忆**: 当前使用 `RetrieverQueryEngine`(无状态)，用户无法在 Explain/Conclude 中进行追问式交互。
2. **历史消息跨模式泄漏**: `_load_session_history()` 不按 mode 过滤，Explain/Conclude 产生的消息被注入 Chat/Ask 的 `ChatMemoryBuffer`，污染上下文。
3. **删除端点语义不清晰**: `DELETE /documents/{id}` 和 `DELETE /library/documents/{id}` 调用同一个方法，无法区分"软删除(只清索引)"和"硬删除(含文件系统)"。
4. **Session Messages API 缺失**: 前端无法获取历史对话记录，`GET /sessions/{id}/messages` 端点未实现。

本阶段目标是在不破坏 improve-1 ~ improve-5 主流程的前提下，完成记忆架构重构、删除语义修正、文档存储清理机制和 API 补全。

## 2. 本阶段已确认决策

1. Explain/Conclude 模式从 `RetrieverQueryEngine` 迁移到 `CondensePlusContextChatEngine`，获得轻量多轮对话能力。
2. 引入双记忆系统: `_memory`(Chat/Ask 共享) + `_ec_memory`(Explain/Conclude 共享)，各自独立加载。
3. `_load_session_history()` 按 `mode` 字段分流加载，彻底解决跨模式消息泄漏。
4. 提供 `include_ec_context` 开关，可选地将 EC 活动摘要注入 Chat/Ask 的上下文。
5. 删除端点拆分: `DELETE /documents/{id}` 改为软删除(清索引保留文件)，`DELETE /library/documents/{id}?force=true` 为硬删除(含文件系统)。
6. 文档存储继续使用 bind mount，补充 `make clean-doc` 命令按 document_id 精确删除孤儿文件。
7. 补全 `GET /sessions/{session_id}/messages` 端点，支持 mode 过滤和分页。

## 3. 设计约束

1. 与 improve-1 ~ improve-5 的 Library-first 数据流、notebook 作用域、文档处理流程兼容。
2. `CondensePlusContextChatEngine` 使用 LlamaIndex 已有 API，不引入自定义 ChatEngine 子类。
3. EC 记忆的 token 预算严格控制(约 2000 tokens / 5 轮)，不影响 Chat/Ask 主记忆空间。
4. 删除逻辑变更必须保持 Postman Collection 中已有用例的兼容性(或同步更新)。
5. `make clean-doc` 命令必须按 document_id 精确匹配删除，禁止批量全删。

## 4. 文档索引

| 序号 | 文档 | 职责 |
|------|------|------|
| 01 | [01-problem-analysis.md](./01-problem-analysis.md) | 现状复盘: 四个问题的根因分析、代码证据、影响评估 |
| 02 | [02-memory-architecture.md](./02-memory-architecture.md) | 记忆架构重构: 双记忆系统、CondensePlusContextChatEngine 迁移、mode 分流加载 |
| 03 | [03-ec-context-switch.md](./03-ec-context-switch.md) | EC 上下文开关: include_ec_context 机制设计、摘要生成策略、API 接口 |
| 04 | [04-deletion-endpoint.md](./04-deletion-endpoint.md) | 删除端点修正: 三端点语义明确化、软删除/硬删除拆分、数据流 |
| 05 | [05-document-storage.md](./05-document-storage.md) | 文档存储清理: bind mount 策略、make clean-doc 精确删除、孤儿检测 |
| 06 | [06-session-messages-api.md](./06-session-messages-api.md) | API 补全: Messages 端点设计、响应模型、分页与过滤 |
| 07 | [07-implementation-plan.md](./07-implementation-plan.md) | 实施计划: 任务拆分、依赖关系、实施顺序、验收标准 |
| 08 | [08-test-plan.md](./08-test-plan.md) | 测试计划: 测试矩阵、回归检查项、验证方法 |

## 5. 当前状态

- 文档状态: 设计规划阶段
- 创建日期: 2026-02-11
- 阶段版本: v1.0
