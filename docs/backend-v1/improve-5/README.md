# Improve-5：文档处理可靠性与长任务可观测性优化

## 1. 阶段背景

在 improve-4 联调与大文件测试中，核心链路已可用，但仍有三个待优化点：

1. MinerU 超时后当前熔断策略过于激进（单次失败即进入 300s cooldown）。
2. 文档状态机虽已覆盖 `pending/processing/completed/failed`，但 `processing` 内部缺少 ES/Embedding 阶段可观测性。
3. PDF 降级链路仍以 PyPDF 为主，扫描版 PDF 在 MinerU 不可用时成功率不足。

本阶段目标是在不破坏 improve-1 ~ improve-4 主流程的前提下，完成超时与熔断优化、处理中子阶段状态机落地、PDF 降级链路切换为 MarkItDown。

## 2. 本阶段已确认决策

1. 熔断策略改为“连续失败 5 次再熔断”，不再采用单次失败立即 cooldown。
2. 超时机制保持简化，不引入过多可配置项。
3. 处理中要增强 ES/Embedding 阶段状态可观测性。
4. PDF 兜底从 PyPDF 调整为 MarkItDown（启用 PDF 支持依赖）。
5. 用户指南明确：扫描版 PDF 优先建议使用 GPU 版本地 MinerU（OCR）；云端不可用时图片扫描件效果会下降。
6. `chat/ask/explain/conclude` 四模式的 RAG/ES 均需受 Notebook 作用域约束。
7. Chat ES tool 需要支持 notebook 作用域过滤，避免全局检索噪声与额外耗时。
8. 缺失 `document_id` 的 source 告警要做聚合降噪，避免重复 warning。
9. Postman 需补充 Library 级删除文档用例，明确“取消关联 != 删除文档”。

## 3. 设计约束

1. 与 `docs/ai-core-v1/08-error-handling.md` 的错误码语义保持一致。
2. 与 `docs/backend-v1/improve-1` ~ `improve-4` 的 Library-first 数据流兼容。
3. 文档处理运行主体在 `celery-worker` 容器，运行时依赖必须首先保证容器内可用。
4. 本地 `.venv` 依赖仅用于本地开发/脚本/测试，不能替代容器运行时依赖。

## 4. 文档索引

| 文档 | 说明 |
|------|------|
| [01-problem-analysis.md](./01-problem-analysis.md) | 现状复盘、根因与影响评估 |
| [02-solution-design.md](./02-solution-design.md) | 优化方案设计（熔断、状态机、降级链路、依赖策略） |
| [03-implementation-plan.md](./03-implementation-plan.md) | 开发任务拆分、实施顺序、验收标准 |
| [04-test-and-regression-plan.md](./04-test-and-regression-plan.md) | 测试矩阵、回归检查项、发布门禁 |
| [05-implementation-report.md](./05-implementation-report.md) | 代码实施结果与改动清单 |
| [06-regression-check.md](./06-regression-check.md) | 对照 improve-1 ~ improve-4 的回归检验结论 |
| [07-notebook-scope-hardening.md](./07-notebook-scope-hardening.md) | 四模式 notebook 作用域收敛与日志/用例补充 |

## 5. 当前状态

- 文档状态：核心实现完成，待用户执行后端全链路回归测试
- 创建日期：2026-02-09
- 更新日期：2026-02-09
- 阶段版本：v1.2
