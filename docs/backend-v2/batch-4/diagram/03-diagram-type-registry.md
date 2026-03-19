# DiagramTypeRegistry

## 职责

DiagramTypeRegistry 是图表类型的注册中心，负责集中管理每种图表类型的：

- 输出格式（reactflow_json 或 mermaid）
- 文件扩展名
- 格式校验器
- Agent 生成指令模板（注入 system prompt）
- 类型识别提示词（用于 Agent 在 `/diagram` 单命令下判断目标图表类型）

新增图表类型只需在注册表中添加一条 `DiagramTypeDescriptor`，DiagramService 和 DiagramSkillProvider 无需修改。

对齐说明：

- 注册表代码路径按当前仓库分层放在 `newbee_notebook/skills/diagram/registry.py`
- `DiagramValidationError` / `DiagramTypeNotFoundError` 在实现时应与 `DiagramService` 所在模块保持同一来源，避免再造一套平行异常定义
- slash 命令策略统一为单入口 `/diagram`，不再按类型拆分 `/mindmap`、`/flowchart`、`/sequence`

## DiagramTypeDescriptor

```python
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class DiagramTypeDescriptor:
    name: str
    # 图表类型标识，与数据库 diagram_type 字段值一致
    # 示例："mindmap"

    output_format: str
    # "reactflow_json" 或 "mermaid"

    file_extension: str
    # MinIO 文件扩展名
    # 示例：".json"、".mmd"

    description: str
    # 向用户展示的图表类型名称，用于 Studio UI 和 i18n
    # 示例："思维导图"

    agent_system_prompt: str
    # 激活该图表类型时注入 AgentLoop system prompt 的补充指令
    # 包含输出格式要求、结构约束、示例

    intent_hints: tuple[str, ...]
    # 用户意图关键词提示（用于 /diagram 下的类型识别）
    # 示例：("mind map", "mindmap", "思维导图", "脑图")

    validator: Callable[[str], None]
    # 格式校验函数，接收原始文本，校验失败时抛出 DiagramValidationError
```

## 格式校验器

### reactflow_json 校验器

使用 Pydantic 模型进行结构校验：

```python
from pydantic import BaseModel
from newbee_notebook.application.services.diagram_service import DiagramValidationError
import json


class ReactFlowNode(BaseModel):
    id: str
    label: str


class ReactFlowEdge(BaseModel):
    source: str
    target: str


class ReactFlowDiagramSchema(BaseModel):
    nodes: list[ReactFlowNode]
    edges: list[ReactFlowEdge]


def validate_reactflow_schema(content: str) -> None:
    """
    校验 reactflow_json 格式内容。

    规则：
    - 必须是合法 JSON
    - 顶层必须有 nodes 和 edges 数组
    - 每个 node 必须有 id 和 label 字段
    - 每个 edge 必须有 source 和 target 字段
    - node 不应包含 position 字段（坐标由前端计算）

    校验失败时抛出 DiagramValidationError，错误信息需足够具体，
    以便 Agent 根据错误信息修正后重试。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise DiagramValidationError(f"JSON 解析失败：{e}") from e

    try:
        ReactFlowDiagramSchema.model_validate(data)
    except Exception as e:
        raise DiagramValidationError(f"图表结构校验失败：{e}") from e

    # 检查 node 是否携带 position 字段（不应由 Agent 输出）
    for node in data.get("nodes", []):
        if "position" in node:
            raise DiagramValidationError(
                f"节点 '{node.get('id')}' 包含 position 字段，"
                "请移除所有 position 字段，坐标由前端自动计算。"
            )
```

### mermaid 校验器（预留，未来 batch 实现）

```python
def validate_mermaid_syntax(content: str) -> None:
    """
    校验 Mermaid 语法文本。

    实现建议：使用 @a24z/mermaid-parser（Node.js 端）或
    通过 subprocess 调用 mermaid CLI 进行语法检查。
    batch-4 注册 mermaid 类型时补充实现。
    """
    raise NotImplementedError("mermaid 校验器将在注册 mermaid 类型时实现")
```

## 异常类型

```python
class DiagramValidationError(Exception):
    """图表内容格式校验失败，错误信息应具体描述校验失败原因，供 Agent 参考修正"""
    pass


class DiagramTypeNotFoundError(Exception):
    """请求的图表类型未在注册表中注册"""
    pass
```

## DIAGRAM_TYPE_REGISTRY

```python
# newbee_notebook/skills/diagram/registry.py

DIAGRAM_TYPE_REGISTRY: dict[str, DiagramTypeDescriptor] = {
    "mindmap": DiagramTypeDescriptor(
        name="mindmap",
        output_format="reactflow_json",
        file_extension=".json",
        description="思维导图",
        agent_system_prompt=(
            "你需要根据用户要求和文档内容生成一张思维导图。\n"
            "输出格式为严格的 JSON，顶层包含两个字段：\n"
            "- nodes：数组，每个元素包含 id（字符串）和 label（字符串）\n"
            "- edges：数组，每个元素包含 source（节点 id）和 target（节点 id）\n"
            "约束：\n"
            "1. 不要在节点中包含 position 字段\n"
            "2. 不要在 JSON 之外输出任何内容\n"
            "3. 根节点 id 建议使用 'root'\n"
            "4. label 内容使用与用户输入一致的语言\n"
            "示例输出：\n"
            '{"nodes": [{"id": "root", "label": "主题"}, {"id": "n1", "label": "子主题"}], '
            '"edges": [{"source": "root", "target": "n1"}]}'
        ),
        intent_hints=("mind map", "mindmap", "思维导图", "脑图"),
        validator=validate_reactflow_schema,
    ),

    # 预留扩展位（未来 batch 注册时取消注释并补充实现）
    # "flowchart": DiagramTypeDescriptor(
    #     name="flowchart",
    #     output_format="mermaid",
    #     file_extension=".mmd",
    #     description="流程图",
    #     agent_system_prompt="...",
    #     intent_hints=("flowchart", "流程图"),
    #     validator=validate_mermaid_syntax,
    # ),
    #
    # "sequence": DiagramTypeDescriptor(
    #     name="sequence",
    #     output_format="mermaid",
    #     file_extension=".mmd",
    #     description="时序图",
    #     agent_system_prompt="...",
    #     intent_hints=("sequence diagram", "时序图"),
    #     validator=validate_mermaid_syntax,
    # ),
}
```

## 查询接口

```python
def get_descriptor(diagram_type: str) -> DiagramTypeDescriptor:
    """
    获取图表类型描述符，类型不存在时抛出 DiagramTypeNotFoundError。
    """
    descriptor = DIAGRAM_TYPE_REGISTRY.get(diagram_type)
    if descriptor is None:
        supported = list(DIAGRAM_TYPE_REGISTRY.keys())
        raise DiagramTypeNotFoundError(
            f"图表类型 '{diagram_type}' 未注册，当前支持的类型：{supported}"
        )
    return descriptor


def infer_diagram_type_from_prompt(prompt: str) -> str | None:
    """
    根据用户提示词粗粒度识别图表类型。
    识别失败返回 None，由上层触发确认流。
    """
    normalized = str(prompt or "").lower()
    for diagram_type, descriptor in DIAGRAM_TYPE_REGISTRY.items():
        for hint in descriptor.intent_hints:
            if hint.lower() in normalized:
                return diagram_type
    return None
```

## 与单命令 `/diagram` 的关系

- DiagramTypeRegistry 不负责 slash 命令路由，路由由 `DiagramSkillProvider.slash_commands = ["/diagram"]` 统一处理。
- Registry 只负责“类型能力定义”和“类型识别辅助”。
- 当用户未明确类型时，Agent 应通过确认卡片（`confirm_diagram_type` 工具）与用户确认后再调用 `create_diagram`。
