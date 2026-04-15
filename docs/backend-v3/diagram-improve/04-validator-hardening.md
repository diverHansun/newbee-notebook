# 04 后端 validator 加固

## 1. 目标

让**"后端 validator 通过"等价于"前端编译器可以渲染"**。即:

- 覆盖 [02-syntax-spec.md](./02-syntax-spec.md) 中的每一条强约束
- 保持纯 Python 实现,不引入外部 Mermaid 解析库
- 错误消息结构化、对 LLM 友好,可作为修正依据

## 2. 通用错误返回规范

validator 抛出的 `DiagramValidationError`,统一包含:

```
<类别>: <具体描述> | 违规位置: <行号或节点 id 或节点字段名> | 建议: <修正方向>
```

类别枚举(仅内部日志使用,不暴露给 LLM):

- `structure`:顶层结构错误(非 JSON、缺键、类型错)
- `schema`:字段类型 / 未知字段
- `syntax`:语法关键字错误
- `reserved`:使用了保留字
- `escape`:特殊字符未转义
- `reference`:引用了不存在的 id

## 3. mindmap validator(强化)

函数:`validate_reactflow_schema(content: str) -> None`(保留现名,避免改动调用方)

新增或增强的检查:

| 序号 | 检查项 | 触发错误类别 |
|------|--------|--------------|
| 1 | content 去掉首尾空白后不以 `{` 开头或不以 `}` 结尾 | structure |
| 2 | 若 content 被 markdown 围栏(```)包裹 | structure |
| 3 | `json.loads` 失败(含注释、尾随逗号等) | structure |
| 4 | 顶层不是 dict | structure |
| 5 | 顶层除 `nodes` / `edges` 外存在其它键 | schema |
| 6 | `nodes` 不是 list 或长度为 0 | schema |
| 7 | `edges` 不是 list | schema |
| 8 | 任一 node 含 `nodes/edges` 以外的字段(尤其 `position`) | schema |
| 9 | 任一 node 缺 `id` 或 `label`,或其值非字符串 | schema |
| 10 | node id 重复 | schema |
| 11 | node id 包含空格 | schema |
| 12 | 任一 edge 字段不是 `source` / `target` 之一 | schema |
| 13 | 任一 edge 缺 `source` 或 `target` | schema |
| 14 | edge `source` 或 `target` 不在 node id 集合中 | reference |
| 15 | edge `source == target` | schema |

实现提示:

- 尽量收集所有违规再一次性抛出,便于 LLM 修正;若实现复杂度过高,至少首次违规时报出精确位置
- 用 `pydantic` 严格模式(`model_config = ConfigDict(extra="forbid")`)替代现有 `BaseModel`,自动覆盖 #5、#8、#12

## 4. Mermaid validator(深度化)

函数:`validate_mermaid_syntax(content: str) -> None`(保留现名)

旧实现仅检查首行关键字。新实现分为三步:

### 4.1 预检(对所有 Mermaid 类型)

| 序号 | 检查项 | 类别 |
|------|--------|------|
| M1 | content 去首尾空白后为空 | structure |
| M2 | content 首行含 ` ``` ` 或 ` ```mermaid ` | structure |
| M3 | 全文含 ` ``` `(任意位置的代码块围栏) | structure |

### 4.2 首行判别与分派

解析首行(忽略前导空白与空行),按前缀分派:

- `flowchart ` 或 `graph ` → 进入 4.3 flowchart 深度检查
- `sequenceDiagram`(首行恰好这一个 token,允许尾随空白)→ 进入 4.4 sequenceDiagram 深度检查
- 其它 → `syntax`,首行不是支持的 Mermaid 类型头

### 4.3 flowchart 深度检查

| 序号 | 检查项 | 类别 |
|------|--------|------|
| F1 | 首行方向关键字不在白名单 `{TD, TB, BT, LR, RL}` | syntax |
| F2 | 存在任一节点 id 等于 `end` / `End` / `END` | reserved |
| F3 | 存在任一节点 id 以 `o` 或 `x` 开头(小写) | reserved |
| F4 | 存在未闭合的方括号 / 圆括号 / 花括号对(按 `[`、`(`、`{` 计数) | syntax |
| F5 | 发现形如 `A[...]` 的 label 内含需转义字符且未被双引号包裹 | escape |
| F6 | 发现边标签 `-->|...|` 内含需转义字符且未被双引号包裹 | escape |

说明:F2-F6 基于行级正则扫描即可实现,不需要完整的 Mermaid AST。label 提取正则示例:`r'\[([^\[\]]*)\]'`、`r'\(([^()]*)\)'`、`r'\{([^{}]*)\}'`、`r'\|([^|]*)\|'`。

需转义字符集:`(`, `)`, `:`, `;`, `"`, `'`, `` ` ``, `|`, `\`, `<`, `>`, `&`, `#`,以及所有 Unicode 中文标点(通过 `unicodedata` 判断或维护静态集合)。

### 4.4 sequenceDiagram 深度检查

| 序号 | 检查项 | 类别 |
|------|--------|------|
| S1 | 首行非 `sequenceDiagram`(允许尾随空白,不允许附加内容) | syntax |
| S2 | 存在 `participant <id>` 或 `actor <id>` 行,其中 `<id>` 是裸 `end` | reserved |
| S3 | 存在消息行,箭头前后的参与者名是裸 `end` | reserved |
| S4 | 消息文本(冒号后内容)含 `;` 且未写成 `#59;` | escape |
| S5 | 消息文本含 `#` 且未作为 HTML 实体前缀(如 `#59;`、`#35;`)的情况下单独出现 | escape |

### 4.5 非目标检查(本次不做)

- 不做完整 Mermaid AST 解析
- 不检测 flowchart 的循环依赖、连通性
- 不检测 sequenceDiagram 的 activate/deactivate 配对

这些属于"能正确渲染但可能语义瑕疵"的场景,超出本次目标(本次目标是消除"后端过但前端炸")。

## 5. 错误消息样例

```
structure: JSON 解析失败 | 违规位置: 第 1 行 | 建议: 去掉 markdown 围栏,直接输出 JSON
schema: node 字段不允许出现 'position' | 违规位置: nodes[2].id='sup' | 建议: 移除 position 字段,布局由前端处理
syntax: flowchart 方向关键字 'TOP' 非法 | 违规位置: 第 1 行 | 建议: 改为 TD / TB / BT / LR / RL 之一
reserved: 节点 id 'end' 是 Mermaid 保留字 | 违规位置: 第 3 行 | 建议: 改为 'END' 或 'Finish'
escape: label 含未转义的括号 | 违规位置: 第 4 行 'A[执行(步骤1)]' | 建议: 用双引号包裹 label,如 A["执行(步骤1)"]
```

## 6. 自检测试

在 `tests/unit/skills/diagram/test_registry.py` 中补充(新增测试见 [05-affected-files.md](./05-affected-files.md)):

- 对 registry 每个 `positive_example` 调用对应 validator,必须通过
- 对本文档第 3 节、第 4 节每条违规提供最小反例,validator 必须抛出,且错误消息含对应类别与位置线索

## 7. 与 prompt 的一致性

validator 的每条规则,在 [02-syntax-spec.md](./02-syntax-spec.md) 中都有对应条目;并经由 `agent_system_prompt` 抵达 LLM(见 [03-prompt-refactor.md](./03-prompt-refactor.md))。**三处(文档、prompt、validator)必须同步修改**。
