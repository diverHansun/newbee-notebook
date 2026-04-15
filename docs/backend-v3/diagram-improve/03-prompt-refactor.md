# 03 Prompt 重组方案(方案 γ)

## 1. 设计目标

- 消除 `registry.agent_system_prompt` 死代码
- 让 LLM 在**生成前**就看到全部三种类型的完整语法规则,提升一次性成功率
- 让 registry 成为"类型知识"的单一真相源,未来加新类型只改 registry,不改 provider
- Token 开销可控(估算整段 addition 在 1.5k tokens 以内)
- 与 [02-syntax-spec.md](./02-syntax-spec.md) 对齐:prompt 不应出现该文档未记录的规则,也不应遗漏该文档的强约束

## 2. 架构

### 2.1 Registry 扩展

`DiagramTypeDescriptor` 新增以下字段(保留现有字段):

```python
@dataclass(frozen=True)
class DiagramTypeDescriptor:
    name: str
    output_format: str
    file_extension: str
    description: str              # 一行中文描述,出现在 prompt 头部的"类型一览表"里
    agent_system_prompt: str      # 已存在,重写内容为本类型的完整语法规则 + 少量反例
    intent_hints: tuple[str, ...] # 保留,用于可能的辅助判断
    validator: Callable[[str], None]

    # 新增
    selection_guidance: str       # 1-2 句,告诉 LLM 什么场景下应选用此类型
    positive_example: str         # 一个最小可渲染的正例 content
```

> 正例由 registry 持有,既用于 prompt few-shot,也用于 validator 的自检测试。

### 2.2 Provider 汇总策略

`DiagramSkillProvider.build_manifest` 不再硬编码 `system_prompt_addition`,改为**在运行时从 `DIAGRAM_TYPE_REGISTRY` 汇总**。汇总函数可放在 `skills/diagram/registry.py`:

```python
def build_diagram_system_prompt() -> str:
    sections: list[str] = [HEADER_PREAMBLE]          # 全局角色与禁忌
    sections.append(_render_type_overview())          # 三类型一览 + selection_guidance
    for descriptor in DIAGRAM_TYPE_REGISTRY.values():
        sections.append(_render_type_section(descriptor))
    sections.append(OPERATIONAL_RULES)                # tool 调用约束与确认流程
    return "\n\n".join(sections)
```

`provider.py` 内只保留一行:

```python
system_prompt_addition=build_diagram_system_prompt(),
```

### 2.3 内容切面

| 切面 | 内容来源 | 约束 |
|------|----------|------|
| HEADER_PREAMBLE | provider 模块常量 | 角色、通用禁忌(不要 markdown fence、不要占位符、不要 `<tool_call>` 文本) |
| 类型一览表 | registry 各项 `description` + `selection_guidance` | Markdown 表格,帮 LLM 选型 |
| 每类型详细节 | `agent_system_prompt` | 严格语法规则 + 1 个 positive_example + 2-3 个反例 |
| OPERATIONAL_RULES | provider 模块常量 | 工具调用顺序:歧义时先 `confirm_diagram_type`,确认后 `create_diagram`;不要回显 diagram_id |

## 3. 完整 Prompt 模板(示意)

以下是注入到 system_prompt 的完整结构(节选,正文规则来自 02 文档):

```
---
Active skill: /diagram

你正在协助用户在笔记本中创建或维护图表。你必须在最终回复前至少调用一次真实的图表操作工具
(如 create_diagram),不要在回复里输出 <tool_call>...</tool_call> 这类裸标记。

通用禁忌:
- 工具参数 content 字段里不得包含 markdown 代码块围栏(```)
- 不得使用占位符("TODO"、"待补充"、"...")
- 不得在 content 前后附加自然语言说明
- diagram_id 已由 Studio UI 展示,不要在回复里复述,也不要要求用户去打开笔记

支持的图表类型一览:

| type       | 格式              | 何时选用                                                       |
|------------|-------------------|----------------------------------------------------------------|
| mindmap    | mindmap JSON      | 需要展示层级关系、分类树、知识图的"放射状"结构                 |
| flowchart  | Mermaid flowchart | 需要展示步骤、决策、分支、并行流程的"方向性"结构               |
| sequence   | Mermaid sequence  | 需要展示多方参与的时间顺序交互、消息往返                       |

若用户意图明确,直接调用 create_diagram。若意图歧义(例如"给这部分内容画个图"),
先调用 confirm_diagram_type 提议类型并说明理由,等待确认后再 create_diagram。

=== mindmap 详细规则 ===
<< descriptor.agent_system_prompt: 包含 02 文档 §1 的全部规则 + 一个合法样例 + 两个非法样例与原因 >>

=== flowchart 详细规则 ===
<< descriptor.agent_system_prompt: 包含 02 文档 §2 的全部规则 + 一个合法样例 + 两个非法样例与原因 >>

=== sequence 详细规则 ===
<< descriptor.agent_system_prompt: 包含 02 文档 §3 的全部规则 + 一个合法样例 + 两个非法样例与原因 >>

Notebook 证据使用:
- 当有 notebook documents 时,用真实文档构造 node/label,不要编造
- 若无 notebook documents,仍可基于用户意图生成有用的图表
- 无更好标题时,提供一个简洁的描述性 title
---
```

## 4. Token 预算估算

| 切面            | 估算 tokens |
|-----------------|-------------|
| HEADER_PREAMBLE | 120         |
| 类型一览表      | 160         |
| mindmap 详细    | 300         |
| flowchart 详细  | 380         |
| sequence 详细   | 320         |
| OPERATIONAL     | 80          |
| **合计**        | **~1360**   |

对比现状的 ~250 tokens,增长约 1100 tokens。对 Opus / Sonnet 级别模型,此开销可接受且换来显著的生成准确率提升。

## 5. 保留与退让

- `confirm_diagram_type` tool 保留不动,作为歧义兜底
- `infer_diagram_type_from_prompt` 函数保留不动(目前未接入任何流程,本次不引入代码层选型约束)
- `required_tool_call_before_response` / `force_first_tool_call` 保留不动

## 6. 与其它文档的衔接

- 具体语法规则:见 [02-syntax-spec.md](./02-syntax-spec.md)
- 每条规则在后端 validator 中的对应实现:见 [04-validator-hardening.md](./04-validator-hardening.md)
- provider / registry / tools 的改动点、行数、风险:见 [05-affected-files.md](./05-affected-files.md)
