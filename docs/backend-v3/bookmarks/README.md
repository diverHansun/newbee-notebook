# Bookmarks 模块改进文档（backend-v3）

## 背景

在 Studio 的 Markdown Viewer 中，用户选中文本后点击书签按钮，出现 `POST /api/v1/documents/{document_id}/marks` 返回 `422 Unprocessable Entity` 的问题，导致书签创建失败，前端仅展示“书签创建失败”的通用提示。

本目录文档用于沉淀该问题的分析结论与优化方案，不涉及本次直接代码修改。

## 文档清单

| 文档 | 职责 |
|------|------|
| [problem-analysis.md](problem-analysis.md) | 问题说明：现象、复现、证据链、根因判定、影响范围 |
| [optimization-plan.md](optimization-plan.md) | 优化方案：方案选型、分阶段改造建议、测试与验收标准 |

## 阅读顺序

1. 先阅读 [problem-analysis.md](problem-analysis.md)，确认问题边界与根因。
2. 再阅读 [optimization-plan.md](optimization-plan.md)，评估实施路线与风险。

## 本轮结论摘要

1. 当前 422 的主因是 `anchor_text` 超过后端请求模型最大长度（500 字符）触发字段校验失败。
2. 前端在提交书签前没有对选中文本长度做约束或友好提示，导致可预期失败直接落到后端校验。
3. 建议采用“前端显式约束 + 后端统一错误语义 + 测试补齐”的组合优化方案。
