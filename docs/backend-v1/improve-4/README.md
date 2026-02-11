# Improve-4：后端交互健壮性与状态可观测性改进

## 1. 阶段背景

在 improve-3 阶段完成 MinerU V4 接入后，已通过集成测试验证主链路可用，但仍暴露出 3 类体验与工程一致性问题：

1. 文档未处理完成时，RAG 模式请求会出现 500（缺少结构化错误响应）。
2. 文档处理中状态未实时反映（`uploaded -> completed` 直接跳变）。
3. 脚本目录与命令入口不够统一，影响后续前后端协作与运维稳定性。

本阶段目标是在不改变核心业务流程的前提下，完成错误语义统一、状态机落地、脚本分层规范化。

## 2. 已确认决策

1. 后端不“禁用模式”，但必须在文档未就绪时返回结构化响应，避免 500。
2. 文档处理采用显式状态机更新（`uploaded -> pending -> processing -> completed/failed`）。
3. 脚本分层规范：
   - 后端相关命令放在 `newbee_notebook/scripts`
   - 前端相关命令放在 `frontend/scripts`（后续阶段）
   - 全局/用户直接运行命令放在 `scripts`

## 3. 设计约束

1. 错误处理规范需对齐 `docs/ai-core-v1/08-error-handling.md`（`E4001` / HTTP `409`）。
2. API 错误响应格式需对齐 `docs/ai-core-v1/04-api-design.md` 的统一结构。
3. 与现有 Library-first 流程兼容，不破坏 improve-1 到 improve-3 的已上线行为。

## 4. 文档索引

| 文档 | 说明 |
|------|------|
| [01-problem-analysis.md](./01-problem-analysis.md) | 问题复盘、根因分析、影响评估 |
| [02-solution-design.md](./02-solution-design.md) | 目标方案设计（错误响应、状态机、脚本分层） |
| [03-implementation-plan.md](./03-implementation-plan.md) | 实施计划、任务拆分、验收标准、风险与回滚 |
| [04-regression-check.md](./04-regression-check.md) | 对照 improve-1~3 的回归检验与验证结论 |

## 5. 阶段产出

1. 后端错误响应从“异常冒泡”升级为“可消费的结构化业务错误”。
2. 前端可通过标准状态字段正确展示“排队中/处理中/已完成/失败”。
3. 脚本使用入口清晰，减少重复脚本和调用歧义。

## 6. 状态

- 文档状态：实现完成，待后端联调验证
- 创建日期：2026-02-09
- 阶段版本：v1.0
