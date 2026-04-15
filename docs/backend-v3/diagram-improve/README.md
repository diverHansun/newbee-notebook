# Diagram 模块优化 — 文档导航

## 背景

Studio 版块的 `/diagram` 技能支持三种图表类型(mindmap / flowchart / sequence),由 LLM 生成内容后,经后端 validator 校验、前端编译器渲染。目前 LLM 输出经常无法通过校验或无法被编译器接受,导致 `create_diagram` 失败。

## 本目录的职责

本目录存放 `/diagram` 模块失败问题的系统性诊断与优化方案。文档之间相互引用、各司其职,按以下顺序阅读:

| 序号 | 文档 | 职责 |
|------|------|------|
| 01 | [01-problem-analysis.md](./01-problem-analysis.md) | 完整的数据流梳理、三类失败模式的归因、死代码论证 |
| 02 | [02-syntax-spec.md](./02-syntax-spec.md) | 两种输出格式的完整语法规范,是 system_prompt 与 validator 的单一真相源 |
| 03 | [03-prompt-refactor.md](./03-prompt-refactor.md) | Prompt 重组方案(方案 γ:registry 驱动 + 全量注入)的实施设计 |
| 04 | [04-validator-hardening.md](./04-validator-hardening.md) | 后端 validator 加固方案,覆盖 Mermaid 深度检查与 mindmap schema 严格化 |
| 05 | [05-affected-files.md](./05-affected-files.md) | 受影响文件清单、改动要点、测试补充清单 |

## 一句话总结

把 `registry.py` 里已经写好但从未被使用的 `agent_system_prompt` 真正接入到 system_prompt,并以此为基础,把 Mermaid / mindmap JSON 的可验证语法规则沉淀到 registry,通过 provider 全量注入给 LLM,同时让后端 validator 对齐这些规则,让"后端通过"=="前端可渲染"。

## 核心决策

- **Prompt 策略**:方案 γ(Registry 驱动 + 全量注入),详见 03。
- **类型选择**:由 LLM 基于 system_prompt 中的类型特征自行判断,不做代码层面规则约束(保留 `confirm_diagram_type` 的歧义兜底)。
- **mindmap JSON schema 的定位**:这是 **项目自定义的简化 schema**,不是 React Flow 官方 Node schema。文档中统一用 "mindmap JSON schema" 指代,不再使用 "React Flow 语法" 这类容易误导 LLM 的措辞。
- **向后兼容**:不变更已有 API 与 tool 契约,不做数据库迁移,仅增强 prompt 与 validator。
