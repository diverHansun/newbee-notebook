# 01 问题分析

## 1. 范围与目标

`/diagram` 技能在 Studio 版块承担图表生成职责,支持三种类型:

| diagram_type | format           | 前端渲染器                        |
|--------------|------------------|-----------------------------------|
| mindmap      | reactflow_json   | React Flow + dagre 布局           |
| flowchart    | mermaid          | mermaid.js                        |
| sequence     | mermaid          | mermaid.js                        |

当前核心问题:**LLM 输出的 `content` 经常无法通过后端 validator,或虽能通过后端但无法被前端编译器解析,导致 `create_diagram` 失败或渲染为空**。本文档先完整梳理创建图表的数据流,再对三类失败模式进行归因。

## 2. 创建图表的数据流

```
用户输入 /diagram ...
        │
        ▼
ChatService 构建 session,加载 DiagramSkillProvider
        │
        ▼
DiagramSkillProvider.build_manifest(context)
   - 将 provider.py:50-71 的 system_prompt_addition 追加到系统提示
   - 注册 tools:list_diagrams / read_diagram / confirm_diagram_type
            / create_diagram / update_diagram / delete_diagram
            / update_diagram_positions
        │
        ▼
LLM 基于 prompt 选择 diagram_type,组装 content,调用 create_diagram
        │
        ▼
tools._build_create_diagram_tool.execute(args)
        │
        ▼
DiagramService.create_diagram(notebook_id, title, diagram_type, content, document_ids)
   │
   ├── registry.get_descriptor(diagram_type)
   ├── descriptor.validator(content)
   │     - mindmap  → validate_reactflow_schema(content)
   │     - flowchart→ validate_mermaid_syntax(content)
   │     - sequence → validate_mermaid_syntax(content)
   ├── 校验失败 → 抛 DiagramValidationError → 以 tool error 回给 LLM
   └── 校验通过 → 写入 storage(.json / .mmd)→ 写入仓储
        │
        ▼
tool result 回到 LLM,LLM 生成最终回复
        │
        ▼
前端 DiagramViewer 根据 diagram.format 分派:
   - reactflow_json → parseReactFlowDiagram → applyDagreLayout → React Flow 渲染
   - mermaid        → mermaid.initialize + mermaid.render → 注入 SVG
```

## 3. 失败模式分类

### 3.1 问题 A:LLM 输出结构就不对(优先级高)

表现:

- mindmap content 不是合法 JSON,或 JSON 顶层缺少 `nodes` / `edges` 数组。
- mindmap content 里的 node 带了非法字段(如 `position`),当前 validator 拒绝。
- Mermaid content 首行不是 `flowchart ` / `graph ` / `sequenceDiagram`,当前 validator 拒绝。
- Mermaid content 被 LLM 包裹进 ` ```mermaid ... ``` ` 代码块。
- Mermaid flowchart 使用了不存在的方向关键字(如 `flowchart TOP`)。

当前处理:validator 抛 `DiagramValidationError`,tool 返回 `diagram_validation_failed` error code。LLM 看到 error 后是否重试、如何重试,不稳定。

### 3.2 问题 B:后端校验通过,但前端渲染失败(优先级高)

表现:

- Mermaid label 含未转义的特殊字符(括号、冒号、中文引号、反斜杠),mermaid.js 解析抛错。
- Mermaid 使用了保留字 `end` 作为节点 id / label。
- 节点 id 以 `o` / `x` 开头,被解析器识别为 `--o` / `--x` 边终点。
- sequenceDiagram 消息里出现 `;` 未用 `#59;` 转义。

当前 `validate_mermaid_syntax` 仅校验首行关键字,上述问题无一被拦截。结果:`create_diagram` 返回成功,前端 `mermaid.render` Promise reject,`MermaidRenderer` 进入空 SVG 状态,用户看到空白。

目标:**让"后端通过"等价于"前端可渲染"**。通过加深 validator 与在 system_prompt 中显式警告这些坑位,两端配合消除 B 类失败。

### 3.3 问题 C:LLM 选错了 diagram_type(优先级中)

表现:用户意图明显是"画一个流程",LLM 却用 mindmap 结构生成。或反之。

当前机制:

- `DiagramSkillProvider.system_prompt_addition` 只说明"支持 mindmap / flowchart / sequence",**没有各类型的特征说明和适用场景**。
- `registry.infer_diagram_type_from_prompt` 基于关键字匹配(`"思维导图"`、`"流程图"` 等),但调用链里看不到它被 provider/tools 使用,属于辅助工具函数。
- `confirm_diagram_type` tool 作为歧义兜底存在,但 LLM 是否触发它,取决于它自己对"歧义"的判断。

用户约束:**类型选择应由 LLM 自行决定,不做代码规则约束**。因此 C 的解法只能是**让 system_prompt 更清晰地描述三种类型的特征与典型场景**,提高 LLM 的选型准确率,保留 `confirm_diagram_type` 作为兜底。

## 4. 根因分析

### 4.1 registry.agent_system_prompt 是死代码

`newbee_notebook/skills/diagram/registry.py` 的 `DiagramTypeDescriptor` 定义了 `agent_system_prompt: str` 字段,并为三种类型分别填了详细的语法规则(mindmap 的 JSON 要求、Mermaid 的方向/起始关键字等)。

然而全仓搜索 `agent_system_prompt` 的使用点:

- `skills/diagram/registry.py` — 定义
- `docs/backend-v2/batch-4/diagram/03-diagram-type-registry.md` — 文档引用
- **没有任何运行时代码读取该字段**

唯一接入 LLM 的路径是 `DiagramSkillProvider.build_manifest` 中硬编码的 `system_prompt_addition`(provider.py:50-71),该文本:

- 笼统表述"mindmap 用 JSON 带 nodes/edges,flowchart/sequence 用 Mermaid 语法"
- **没有任何关于 Mermaid 方向关键字、节点 shape、label quoting、保留字 end 的说明**
- **没有 few-shot 示例**
- **没有对"常见错误输出"的反例警示**

**LLM 从未看到 registry 里已经写好的那些规则**。这是问题 A 的核心根因。

### 4.2 术语歧义:diagram_type vs format

当前对外暴露了两个相近的概念:

- `diagram_type` — `mindmap` / `flowchart` / `sequence`
- `format` — `reactflow_json` / `mermaid`

在 system_prompt 里两个词交替出现,且"reactflow_json" 这个 format 名称容易让 LLM 误认为要输出 React Flow 官方 Node schema(含 `position`、`data`、`type` 字段)。实际上我们的 mindmap JSON schema 是**项目自定义的简化 schema**,仅需要 `{nodes: [{id, label}], edges: [{source, target}]}`,前端用 dagre 做布局、React Flow 做渲染。

文档中统一约定:对 LLM 呈现的所有文本,使用 **"mindmap JSON schema"** 这个名称,避免出现 "React Flow syntax" / "reactflow format" 等措辞。

### 4.3 Mermaid validator 过浅

`validate_mermaid_syntax` 的实现仅检查首行非空行是否以 `flowchart ` / `graph ` / `sequenceDiagram` 开头。对问题 B 的所有场景都束手无策:

- label 特殊字符未转义
- 使用保留字
- 代码块围栏未剥离
- 方向关键字拼写错误
- 空节点、空边定义

当后端放行这些内容时,前端 mermaid.js 才抛错,用户侧体验就是"生成成功但看不见"。

### 4.4 无自愈通道

`create_diagram` 失败时,tool 返回 error,依赖 LLM 自行看懂 `DiagramValidationError` 的原始消息并修正。没有结构化的"错误类别 + 建议修法"回传机制。若 system_prompt 与 validator 能在前置环节把错误率压到极低,这一环暂可不做改造;本次优化先聚焦前置。

## 5. 本次优化的边界

纳入范围:

- 消除 `agent_system_prompt` 死代码,由 provider 在 `build_manifest` 时拼装注入
- 全量重写 provider 的 `system_prompt_addition`,包含三类型的特征、选型指引、通用禁忌、few-shot 示例
- 加深 `validate_mermaid_syntax`,覆盖典型 B 类错误
- 对 mindmap JSON schema 增加若干严格性检查(空数组、id 唯一、edge 端点存在)

不纳入范围:

- 不改 API/tool 契约
- 不改数据库模型
- 不改前端渲染器逻辑
- 不引入外部 Mermaid 解析库(保持纯 Python 轻量校验)
- 不引入 LLM 自动重试循环(后续可独立立项)

## 6. 阅读下一篇

语法规范见 [02-syntax-spec.md](./02-syntax-spec.md)。
