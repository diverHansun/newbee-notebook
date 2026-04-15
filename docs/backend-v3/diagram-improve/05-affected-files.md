# 05 受影响文件与实施清单

## 1. 总览

本次优化聚焦 Prompt 与 validator,**不改 API、不改数据库、不改前端渲染器**。涉及的文件分布:

| 模块 | 改动性质 | 文件数 |
|------|----------|--------|
| skills/diagram | 重写 registry、简化 provider | 2 |
| application/services/diagram_service.py | 不动 | 0 |
| tests/unit/skills/diagram | 扩充用例 | 2 |
| 前端 | 不动 | 0 |

## 2. 逐文件改动清单

### 2.1 newbee_notebook/skills/diagram/registry.py(主修改)

**改动类型**:重写

**改动要点**:

1. 为 `DiagramTypeDescriptor` 新增字段 `selection_guidance: str` 与 `positive_example: str`(保留原有字段)。
2. 为三种类型的 `agent_system_prompt` 重写内容,精确对齐 [02-syntax-spec.md](./02-syntax-spec.md) 的条款,附 1 个合法样例、2-3 个非法样例与原因。
3. 为三种类型填充 `selection_guidance`(2 句以内)与 `positive_example`(直接复用 02 文档中的合法样例字符串)。
4. `validate_reactflow_schema` 按 [04-validator-hardening.md](./04-validator-hardening.md) §3 重写:
   - 先做 markdown 围栏、整体结构、顶层键白名单检查
   - 改用 `pydantic.ConfigDict(extra="forbid")` 模式强制 node / edge 字段白名单
   - 增加 id 重复、id 含空格、edge 端点存在性、`source == target` 检查
   - 错误消息按 §5 模板生成
5. `validate_mermaid_syntax` 按 [04-validator-hardening.md](./04-validator-hardening.md) §4 重写:
   - 新增预检:markdown 围栏
   - 按首行分派 flowchart / sequenceDiagram
   - flowchart 深度检查:方向白名单、保留字 `end`、`o/x` 开头、括号配对、label 引号、边标签引号
   - sequenceDiagram 深度检查:参与者保留字、消息文本 `;` 与 `#` 转义
6. 新增汇总函数 `build_diagram_system_prompt() -> str`(见 [03-prompt-refactor.md](./03-prompt-refactor.md) §2.2),供 provider 调用。该函数包含:
   - `HEADER_PREAMBLE` 模块常量
   - 类型一览表(由 registry 动态拼装)
   - 每类型详细章节(由各 descriptor 的 `agent_system_prompt` 拼接)
   - `OPERATIONAL_RULES` 模块常量

**估算行数**:现有约 150 行,重写后约 450-550 行(大部分是 prompt 模板字符串)。

**风险**:

- `DiagramTypeDescriptor` 字段新增会影响现有测试 `test_registry.py` 的构造断言,需同步更新。
- `validate_reactflow_schema` 旧行为仅禁止 `position`,新行为禁止所有额外字段,若历史 diagram 内容含额外字段,`update_diagram` 时可能失败;需确认历史数据风险(见 §4 回归策略)。

### 2.2 newbee_notebook/skills/diagram/provider.py(简化)

**改动类型**:精简

**改动要点**:

1. 删除现硬编码的 `system_prompt_addition` 字符串(provider.py:50-71)。
2. 引入 `from newbee_notebook.skills.diagram.registry import build_diagram_system_prompt`。
3. 在 `build_manifest` 中使用 `system_prompt_addition=build_diagram_system_prompt()`。
4. 其余(tools 注册、confirmation_meta、force_first_tool_call 等)保持不变。

**估算行数**:净减少约 15-20 行。

**风险**:现有测试 `tests/unit/skills/diagram/test_tools.py:193-196` 对 `system_prompt_addition` 做了字符串断言(如 `"create_diagram" in manifest.system_prompt_addition`、`"Mermaid" in ...`),新的汇总文本应继续包含这些关键字,但需**逐条复核断言并视需要调整**。

### 2.3 newbee_notebook/skills/diagram/tools.py(轻微)

**改动类型**:不改行为,仅可能微调 `create_diagram` 工具的 `description` 文本,让它与新的 registry 保持措辞一致(例如统一使用 "mindmap JSON schema" 而非 "strict JSON")。

**估算行数**:±5 行。

### 2.4 newbee_notebook/skills/diagram/__init__.py

**改动类型**:按需补充导出。若将 `build_diagram_system_prompt` 放在 `registry.py` 并被 `provider.py` 直接 import,不需要修改。

### 2.5 newbee_notebook/application/services/diagram_service.py

**改动类型**:不改动。

理由:service 只负责调度、持久化,validator 逻辑完全在 registry 内。加固 validator 不会穿透到 service 层。

### 2.6 frontend/*

**改动类型**:不改动。

前端 `MermaidRenderer`、`parseReactFlowDiagram`、`applyDagreLayout`、`buildReactFlowElements` 均不动。后端 validator 与 prompt 加强后,进入前端的内容天然满足渲染器要求。

## 3. 测试补充

### 3.1 tests/unit/skills/diagram/test_registry.py

**改动类型**:扩充用例

**新增用例矩阵**:

| 用例组 | 检查点 | 对应规则来源 |
|--------|--------|--------------|
| `test_build_diagram_system_prompt_contains_each_type` | 汇总 prompt 包含三种类型的关键字 | 03 §3 |
| `test_descriptor_positive_examples_pass_their_validator` | 每个 `positive_example` 在对应 validator 下通过 | 04 §6 |
| `test_mindmap_rejects_markdown_fence` | 04 §3 #2 | |
| `test_mindmap_rejects_extra_top_level_key` | 04 §3 #5 | |
| `test_mindmap_rejects_position_field` | 04 §3 #8(保留旧用例) | |
| `test_mindmap_rejects_duplicate_ids` | 04 §3 #10 | |
| `test_mindmap_rejects_edge_to_unknown_node` | 04 §3 #14 | |
| `test_mindmap_rejects_self_loop` | 04 §3 #15 | |
| `test_flowchart_rejects_invalid_direction` | 04 §4 F1 | |
| `test_flowchart_rejects_reserved_end_id` | 04 §4 F2 | |
| `test_flowchart_rejects_id_starting_with_o_or_x` | 04 §4 F3 | |
| `test_flowchart_rejects_unquoted_label_with_parentheses` | 04 §4 F5 | |
| `test_mermaid_rejects_markdown_fence` | 04 §4 M2/M3 | |
| `test_sequence_rejects_extra_tokens_on_header` | 04 §4 S1 | |
| `test_sequence_rejects_reserved_end_participant` | 04 §4 S2 | |
| `test_sequence_rejects_unescaped_semicolon` | 04 §4 S4 | |

每用例:构造最小反例字符串 → 断言 `DiagramValidationError` 被抛出 → 断言错误消息含对应类别关键字(如 `"reserved"`、`"structure"` 等)。

### 3.2 tests/unit/skills/diagram/test_tools.py

**改动类型**:调整断言措辞

复核 provider manifest 的 `system_prompt_addition` 断言:

- 保留对"包含 create_diagram"、"包含 Mermaid"、"不含 `<tool_call>`"等断言的含义
- 文本若有措辞调整,对应断言同步更新
- 新增断言:"包含 `mindmap JSON schema` 而不包含 `React Flow syntax`"

## 4. 向后兼容与回归策略

### 4.1 新旧 mindmap 数据的兼容

当前生产中若有旧 mindmap diagram 的 JSON 包含除 `nodes/edges` 之外的字段(例如历史上曾允许),则:

- `read_diagram`(仅读取)不走 validator,不受影响
- `update_diagram`(含新 content)会走 validator,若 LLM 生成的新内容符合新规则,通过
- `update_diagram_positions` 改变的是 `diagram.node_positions`(不是 content),不受影响

**结论**:对历史数据无破坏,对"用户提交旧风格 content 做更新"场景无负面影响(LLM 已按新 prompt 生成新风格内容)。

### 4.2 灰度策略

不需要灰度。Prompt 与 validator 都是运行时代码,无数据模型变更,合并即生效。

### 4.3 回滚策略

单次提交回滚即可恢复旧行为。建议改动分两个 commit:

- commit 1:registry 重写(descriptor 扩展 + validator 加固 + prompt 汇总函数 + 测试扩充)
- commit 2:provider 精简(切换到 `build_diagram_system_prompt()`)

回滚时优先回滚 commit 2(最小回滚,恢复旧 prompt,但 validator 保持加固)。

## 5. 实施顺序建议

1. 先落地 [02-syntax-spec.md](./02-syntax-spec.md)(已完成,作为实现依据)
2. 重写 registry:扩展 descriptor → 重写 validator → 补齐测试
3. 精简 provider:切换到汇总 prompt → 更新 tools 测试断言
4. 端到端手动验证:针对 mindmap / flowchart / sequence 各运行 1-2 轮真实 `/diagram` 会话,观察首次成功率

## 6. 后续可独立立项的改进(非本次范围)

- 结构化 `DiagramValidationError` 返回给 LLM 的错误 metadata,供 LLM 基于"错误类别 + 建议修法"自动重试
- 引入 `mermaid-py` 或 `pymermaid` 等解析库做深度校验(需评估依赖体量)
- 为 `create_diagram` 增加一次失败后的自动重试,传入失败原因作为提示
- 对 `infer_diagram_type_from_prompt` 是否接入或移除做决策(目前是孤岛函数)
