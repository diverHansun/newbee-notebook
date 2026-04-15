"""Diagram type registry, prompt builder, and validators."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError

from newbee_notebook.application.services.diagram_service import (
    DiagramTypeNotFoundError,
    DiagramValidationError,
)


class ReactFlowNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrictStr
    label: StrictStr


class ReactFlowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: StrictStr
    target: StrictStr


class ReactFlowDiagramSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[ReactFlowNode]
    edges: list[ReactFlowEdge]


_FLOWCHART_DIRECTION_WHITELIST = {"TD", "TB", "BT", "LR", "RL"}
_MERMAID_SPECIAL_CHARS = frozenset({"(", ")", ":", ";", "\"", "'", "`", "|", "\\", "<", ">", "&", "#"})
_MINDMAP_TOP_LEVEL_KEYS = frozenset({"nodes", "edges"})
_MINDMAP_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

_FLOWCHART_HEADER_PATTERN = re.compile(r"^(flowchart|graph)\s+([A-Za-z]+)\s*$")
_FLOWCHART_NODE_WITH_SHAPE_PATTERN = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(\[\[[^\]]+\]\]|\[\([^)]+\)\]|\(\[[^\]]+\]\)|\(\([^)]+\)\)|\[[^\]]+\]|\([^)]+\)|\{[^}]+\})"
)
_FLOWCHART_EDGE_PATTERN = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\b\s*(?:-->|---|-.->|==>|--x|--o|-x|-o)\s*(?:\|[^|]*\|\s*)?"
    r"\b([A-Za-z_][A-Za-z0-9_]*)\b"
)
_FLOWCHART_EDGE_LABEL_PATTERN = re.compile(r"\|([^|]+)\|")

_SEQUENCE_HEADER_PATTERN = re.compile(r"^sequenceDiagram\s*$")
_SEQUENCE_PARTICIPANT_PATTERN = re.compile(
    r"^\s*(?:participant|actor)\s+"
    r"(?P<id>[A-Za-z_][A-Za-z0-9_]*|\"[^\"]+\"|\([^)]+\))"
    r"(?:\s+as\s+.+)?$"
)
_SEQUENCE_MESSAGE_PATTERN = re.compile(
    r"^\s*(?P<source>[A-Za-z_][A-Za-z0-9_]*|\"[^\"]+\"|\([^)]+\))\s*"
    r"(?P<arrow>->>|-->>|-->|->|--x|-x|-\))\s*"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_]*|\"[^\"]+\"|\([^)]+\))\s*:\s*"
    r"(?P<message>.+)$"
)


def _build_validation_message(
    category: str,
    detail: str,
    location: str,
    suggestion: str,
) -> str:
    return f"{category}: {detail} | 违规位置: {location} | 建议: {suggestion}"


def _raise_validation_error(
    category: str,
    detail: str,
    location: str,
    suggestion: str,
) -> None:
    raise DiagramValidationError(_build_validation_message(category, detail, location, suggestion))


def _stringify_location(path: tuple[object, ...]) -> str:
    if not path:
        return "content"

    result = "content"
    for token in path:
        if isinstance(token, int):
            result += f"[{token}]"
        else:
            result += f".{token}"
    return result


def _raise_schema_error_from_pydantic(exc: ValidationError) -> None:
    first_error = exc.errors()[0]
    location = _stringify_location(tuple(first_error.get("loc", ())))
    error_type = str(first_error.get("type", ""))

    if error_type == "extra_forbidden":
        field = first_error.get("loc", ("unknown",))[-1]
        _raise_validation_error(
            "schema",
            f"字段 '{field}' 不允许出现",
            location,
            "仅保留 schema 允许的字段",
        )

    if error_type == "missing":
        field = first_error.get("loc", ("unknown",))[-1]
        _raise_validation_error(
            "schema",
            f"缺少必填字段 '{field}'",
            location,
            "补齐必填字段并确保字段名正确",
        )

    _raise_validation_error(
        "schema",
        first_error.get("msg", "Schema validation failed"),
        location,
        "按 mindmap JSON schema 修复结构与字段类型",
    )


def validate_reactflow_schema(content: str) -> None:
    """Validate agent-generated content against the custom mindmap JSON schema."""

    normalized = str(content or "").strip()
    if not normalized:
        _raise_validation_error(
            "structure",
            "content 不能为空",
            "content",
            "直接输出一个非空 JSON 对象",
        )

    if "```" in normalized:
        _raise_validation_error(
            "structure",
            "检测到 markdown 代码块围栏",
            "content",
            "去掉 ``` 围栏，仅输出 JSON",
        )

    if not normalized.startswith("{") or not normalized.endswith("}"):
        _raise_validation_error(
            "structure",
            "顶层必须是 JSON 对象",
            "content",
            "确保内容以 '{' 开头并以 '}' 结尾",
        )

    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        _raise_validation_error(
            "structure",
            f"JSON 解析失败: {exc.msg}",
            f"第 {exc.lineno} 行",
            "移除注释/尾随逗号并输出合法 JSON",
        )

    if not isinstance(parsed, dict):
        _raise_validation_error(
            "structure",
            "顶层必须是对象",
            "content",
            "将顶层改为 {\"nodes\": [...], \"edges\": [...]}",
        )

    keys = set(parsed.keys())
    missing_keys = sorted(_MINDMAP_TOP_LEVEL_KEYS - keys)
    if missing_keys:
        _raise_validation_error(
            "structure",
            f"缺少顶层键: {', '.join(missing_keys)}",
            "content",
            "补齐 nodes 与 edges 两个顶层数组",
        )

    unknown_keys = sorted(keys - _MINDMAP_TOP_LEVEL_KEYS)
    if unknown_keys:
        _raise_validation_error(
            "schema",
            f"存在未定义顶层键: {', '.join(unknown_keys)}",
            "content",
            "仅保留 nodes 与 edges",
        )

    try:
        schema = ReactFlowDiagramSchema.model_validate(parsed)
    except ValidationError as exc:
        _raise_schema_error_from_pydantic(exc)

    if not schema.nodes:
        _raise_validation_error(
            "schema",
            "nodes 数组不能为空",
            "content.nodes",
            "至少提供一个节点",
        )

    node_ids: set[str] = set()
    for index, node in enumerate(schema.nodes):
        node_id = node.id.strip()
        label = node.label.strip()
        location = f"nodes[{index}]"

        if not node_id:
            _raise_validation_error(
                "schema",
                "node.id 不能为空",
                f"{location}.id",
                "提供非空字符串 id",
            )
        if not label:
            _raise_validation_error(
                "schema",
                "node.label 不能为空",
                f"{location}.label",
                "提供非空字符串 label",
            )
        if " " in node_id:
            _raise_validation_error(
                "schema",
                "node.id 不能包含空格",
                f"{location}.id",
                "使用英文/数字/下划线组成的 id",
            )
        if _MINDMAP_ID_PATTERN.fullmatch(node_id) is None:
            _raise_validation_error(
                "schema",
                f"node.id '{node_id}' 含非法字符",
                f"{location}.id",
                "仅使用英文/数字/下划线",
            )
        if node_id in node_ids:
            _raise_validation_error(
                "schema",
                f"node.id '{node_id}' 重复",
                f"{location}.id",
                "确保每个节点 id 唯一",
            )
        node_ids.add(node_id)

    for index, edge in enumerate(schema.edges):
        source = edge.source.strip()
        target = edge.target.strip()
        location = f"edges[{index}]"

        if source == target:
            _raise_validation_error(
                "schema",
                "edge.source 与 edge.target 不能相同",
                location,
                "移除自环或改为不同节点",
            )
        if source not in node_ids:
            _raise_validation_error(
                "reference",
                f"edge.source '{source}' 未在 nodes 中声明",
                f"{location}.source",
                "先在 nodes 中定义该 id",
            )
        if target not in node_ids:
            _raise_validation_error(
                "reference",
                f"edge.target '{target}' 未在 nodes 中声明",
                f"{location}.target",
                "先在 nodes 中定义该 id",
            )


def _first_non_empty_line(lines: list[str]) -> tuple[int, str]:
    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if stripped:
            return index, stripped
    return -1, ""


def _is_non_ascii_punctuation(char: str) -> bool:
    return ord(char) > 127 and unicodedata.category(char).startswith("P")


def _label_requires_quotes(label: str) -> bool:
    value = label.strip()
    if not value:
        return False

    if re.search(r"\bend\b", value, flags=re.IGNORECASE):
        return True
    if any(char in _MERMAID_SPECIAL_CHARS for char in value):
        return True
    if any(_is_non_ascii_punctuation(char) for char in value):
        return True
    return False


def _is_quoted(value: str) -> bool:
    stripped = value.strip()
    return len(stripped) >= 2 and stripped[0] == stripped[-1] == "\""


def _unwrap_shape_label(shape: str) -> str:
    shape = shape.strip()
    wrappers = [
        ("([[", "]]"),  # defensive for uncommon nested cases
        ("[[", "]]"),
        ("([", "])"),
        ("[(", ")]"),
        ("((", "))"),
        ("[", "]"),
        ("(", ")"),
        ("{", "}"),
    ]
    for start, end in wrappers:
        if shape.startswith(start) and shape.endswith(end):
            return shape[len(start) : len(shape) - len(end)]
    return shape


def _validate_bracket_balance(content: str) -> None:
    stack: list[tuple[str, int]] = []
    open_to_close = {"[": "]", "(": ")", "{": "}"}
    close_to_open = {"]": "[", ")": "(", "}": "{"}
    in_quote = False

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        escaped = False
        for char in raw_line:
            if char == "\\" and not escaped:
                escaped = True
                continue

            if char == "\"" and not escaped:
                in_quote = not in_quote
            elif not in_quote and char in open_to_close:
                stack.append((char, line_number))
            elif not in_quote and char in close_to_open:
                if not stack or stack[-1][0] != close_to_open[char]:
                    _raise_validation_error(
                        "syntax",
                        f"括号 '{char}' 未匹配",
                        f"第 {line_number} 行",
                        "检查括号配对并补齐缺失括号",
                    )
                stack.pop()

            escaped = False

    if in_quote:
        _raise_validation_error(
            "syntax",
            "检测到未闭合的双引号",
            "content",
            "补齐双引号或移除多余引号",
        )

    if stack:
        opener, line_number = stack[-1]
        _raise_validation_error(
            "syntax",
            f"括号 '{opener}' 未闭合",
            f"第 {line_number} 行",
            "检查括号配对并补齐缺失括号",
        )


def _validate_flowchart(lines: list[str], first_line_index: int, header: str) -> None:
    match = _FLOWCHART_HEADER_PATTERN.fullmatch(header)
    if match is None:
        _raise_validation_error(
            "syntax",
            "flowchart/graph 首行格式无效",
            f"第 {first_line_index + 1} 行",
            "使用 'flowchart <DIR>' 或 'graph <DIR>'",
        )

    direction = match.group(2)
    if direction not in _FLOWCHART_DIRECTION_WHITELIST:
        _raise_validation_error(
            "syntax",
            f"flowchart 方向关键字 '{direction}' 非法",
            f"第 {first_line_index + 1} 行",
            "改为 TD / TB / BT / LR / RL 之一",
        )

    full_content = "\n".join(lines)
    _validate_bracket_balance(full_content)

    for line_index, raw_line in enumerate(lines[first_line_index + 1 :], start=first_line_index + 2):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        if stripped.lower() == "end" or stripped.lower().startswith("subgraph "):
            continue

        for node_match in _FLOWCHART_NODE_WITH_SHAPE_PATTERN.finditer(raw_line):
            node_id = node_match.group(1)
            shape = node_match.group(2)
            label = _unwrap_shape_label(shape)
            location = f"第 {line_index} 行"

            if node_id.lower() == "end":
                _raise_validation_error(
                    "reserved",
                    "节点 id 'end' 是 Mermaid 保留字",
                    location,
                    "改为 'END' 或 'Finish'",
                )
            if node_id.startswith(("o", "x")):
                _raise_validation_error(
                    "reserved",
                    f"节点 id '{node_id}' 不能以 'o' 或 'x' 开头",
                    location,
                    "修改节点 id 首字母（如改为大写）",
                )
            if _label_requires_quotes(label) and not _is_quoted(label):
                _raise_validation_error(
                    "escape",
                    f"节点 label '{label}' 含特殊字符但未加双引号",
                    location,
                    "使用形如 A[\"...\"] / A(\"...\") / A{\"...\"} 的写法",
                )

        for edge_match in _FLOWCHART_EDGE_PATTERN.finditer(raw_line):
            source, target = edge_match.group(1), edge_match.group(2)
            location = f"第 {line_index} 行"

            for node_id in (source, target):
                if node_id.lower() == "end":
                    _raise_validation_error(
                        "reserved",
                        "节点 id 'end' 是 Mermaid 保留字",
                        location,
                        "改为 'END' 或 'Finish'",
                    )
                if node_id.startswith(("o", "x")):
                    _raise_validation_error(
                        "reserved",
                        f"节点 id '{node_id}' 不能以 'o' 或 'x' 开头",
                        location,
                        "修改节点 id 首字母（如改为大写）",
                    )

        for label_match in _FLOWCHART_EDGE_LABEL_PATTERN.finditer(raw_line):
            label = label_match.group(1).strip()
            if _label_requires_quotes(label) and not _is_quoted(label):
                _raise_validation_error(
                    "escape",
                    f"边标签 '{label}' 含特殊字符但未加双引号",
                    f"第 {line_index} 行",
                    "使用形如 A -->|\"...\"| B 的写法",
                )


def _is_bare_end_identifier(identifier: str) -> bool:
    token = identifier.strip()
    if token.startswith("\"") and token.endswith("\""):
        return False
    if token.startswith("(") and token.endswith(")"):
        return False
    return token.lower() == "end"


def _validate_sequence(lines: list[str], first_line_index: int, header: str) -> None:
    if _SEQUENCE_HEADER_PATTERN.fullmatch(header) is None:
        _raise_validation_error(
            "syntax",
            "sequenceDiagram 首行不能带附加内容",
            f"第 {first_line_index + 1} 行",
            "首行仅保留 'sequenceDiagram'",
        )

    for line_index, raw_line in enumerate(lines[first_line_index + 1 :], start=first_line_index + 2):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("%%"):
            continue

        participant_match = _SEQUENCE_PARTICIPANT_PATTERN.match(stripped)
        if participant_match is not None:
            participant_id = participant_match.group("id")
            if _is_bare_end_identifier(participant_id):
                _raise_validation_error(
                    "reserved",
                    "participant/actor id 不能使用裸 end",
                    f"第 {line_index} 行",
                    "改为 END 或使用 \"end\" 包裹",
                )
            continue

        message_match = _SEQUENCE_MESSAGE_PATTERN.match(stripped)
        if message_match is None:
            continue

        source = message_match.group("source")
        target = message_match.group("target")
        message = message_match.group("message")
        location = f"第 {line_index} 行"

        if _is_bare_end_identifier(source) or _is_bare_end_identifier(target):
            _raise_validation_error(
                "reserved",
                "消息参与者不能使用裸 end",
                location,
                "改为 END 或使用 \"end\" 包裹",
            )

        message_without_entities = re.sub(r"#\d+;", "", message)
        if ";" in message_without_entities:
            _raise_validation_error(
                "escape",
                "消息文本中的 ';' 需要转义为 '#59;'",
                location,
                "将 ';' 替换为 '#59;'",
            )
        if "#" in message_without_entities:
            _raise_validation_error(
                "escape",
                "消息文本中的 '#' 需要使用实体编码",
                location,
                "将 '#' 替换为 '#35;' 或其它 HTML 实体",
            )


def validate_mermaid_syntax(content: str) -> None:
    """Validate Mermaid syntax for flowchart/graph/sequenceDiagram inputs."""

    normalized = str(content or "")
    stripped = normalized.strip()
    if not stripped:
        _raise_validation_error(
            "structure",
            "Mermaid content 不能为空",
            "content",
            "输出非空 Mermaid 文本",
        )

    if "```" in stripped:
        _raise_validation_error(
            "structure",
            "检测到 markdown 代码块围栏",
            "content",
            "去掉 ``` 围栏，仅输出 Mermaid 语法",
        )

    lines = normalized.splitlines()
    first_line_index, header = _first_non_empty_line(lines)
    if first_line_index < 0:
        _raise_validation_error(
            "structure",
            "Mermaid content 不能为空",
            "content",
            "输出非空 Mermaid 文本",
        )

    if header.startswith(("flowchart ", "graph ")):
        _validate_flowchart(lines, first_line_index, header)
        return

    if header.startswith("sequenceDiagram"):
        _validate_sequence(lines, first_line_index, header)
        return

    _raise_validation_error(
        "syntax",
        "首行不是支持的 Mermaid 类型头",
        f"第 {first_line_index + 1} 行",
        "使用 'flowchart <DIR>' / 'graph <DIR>' / 'sequenceDiagram'",
    )


@dataclass(frozen=True)
class DiagramTypeDescriptor:
    name: str
    output_format: str
    file_extension: str
    description: str
    agent_system_prompt: str
    intent_hints: tuple[str, ...]
    validator: Callable[[str], None]
    selection_guidance: str
    positive_example: str


DIAGRAM_TYPE_REGISTRY: dict[str, DiagramTypeDescriptor] = {
    "mindmap": DiagramTypeDescriptor(
        name="mindmap",
        output_format="reactflow_json",
        file_extension=".json",
        description="Mind map",
        agent_system_prompt=(
            "Output format: mindmap JSON schema.\n"
            "- Top-level object must contain exactly two keys: nodes, edges.\n"
            "- nodes is a non-empty array. Each node must be {id, label} only.\n"
            "- edges is an array. Each edge must be {source, target} only.\n"
            "- id must be unique and contain only letters, digits, underscore.\n"
            "- Do not include markdown fences, comments, trailing commas, or extra prose.\n"
            "- Do not include React Flow fields such as position, data, type, style.\n"
            "Invalid examples:\n"
            "1) [{\"id\":\"a\",\"label\":\"A\"}]  # top-level must be object\n"
            "2) {\"nodes\":[{\"id\":\"a\",\"label\":\"A\",\"position\":{\"x\":0,\"y\":0}}],\"edges\":[]}  # "
            "position forbidden"
        ),
        intent_hints=("mind map", "mindmap", "mind-map", "思维导图", "脑图"),
        validator=validate_reactflow_schema,
        selection_guidance="Use mindmap when the user asks for hierarchical categories, topic trees, or radial structure.",
        positive_example=(
            "{\n"
            "  \"nodes\": [\n"
            "    {\"id\": \"root\", \"label\": \"机器学习\"},\n"
            "    {\"id\": \"sup\", \"label\": \"监督学习\"},\n"
            "    {\"id\": \"unsup\", \"label\": \"无监督学习\"}\n"
            "  ],\n"
            "  \"edges\": [\n"
            "    {\"source\": \"root\", \"target\": \"sup\"},\n"
            "    {\"source\": \"root\", \"target\": \"unsup\"}\n"
            "  ]\n"
            "}"
        ),
    ),
    "flowchart": DiagramTypeDescriptor(
        name="flowchart",
        output_format="mermaid",
        file_extension=".mmd",
        description="Flow chart",
        agent_system_prompt=(
            "Output format: Mermaid flowchart.\n"
            "- First non-empty line must be: flowchart <DIR> or graph <DIR>.\n"
            "- Allowed DIR: TD, TB, BT, LR, RL.\n"
            "- Node id cannot be bare 'end' and cannot start with lowercase o/x.\n"
            "- If a node label or edge label contains special punctuation, wrap label with double quotes.\n"
            "- Do not include markdown fences or explanatory prose.\n"
            "Invalid examples:\n"
            "1) flowchart TOP\\nA --> B  # invalid direction\n"
            "2) flowchart TD\\nA[执行(步骤1)] --> B  # label needs double quotes"
        ),
        intent_hints=("flow chart", "flowchart", "流程图", "流程"),
        validator=validate_mermaid_syntax,
        selection_guidance="Use flowchart when the user asks for process steps, decision branches, or directional workflow.",
        positive_example=(
            "flowchart TD\n"
            "    Start([开始]) --> Input[\"读取输入\"]\n"
            "    Input --> Check{\"输入有效?\"}\n"
            "    Check -->|是| Process[\"执行处理\"]\n"
            "    Check -->|否| Error[\"返回错误\"]\n"
            "    Process --> Finish([结束])\n"
            "    Error --> Finish"
        ),
    ),
    "sequence": DiagramTypeDescriptor(
        name="sequence",
        output_format="mermaid",
        file_extension=".mmd",
        description="Sequence diagram",
        agent_system_prompt=(
            "Output format: Mermaid sequenceDiagram.\n"
            "- First non-empty line must be exactly sequenceDiagram.\n"
            "- Participant IDs cannot be bare 'end'.\n"
            "- In message text, ';' must be escaped as #59; and '#' must be escaped as #35; unless part of an entity.\n"
            "- Do not include markdown fences or explanatory prose.\n"
            "Invalid examples:\n"
            "1) sequenceDiagram LR\\nA->>B: hi  # header must not contain extra tokens\n"
            "2) sequenceDiagram\\nA->>B: step1; step2  # semicolon must be escaped"
        ),
        intent_hints=("sequence diagram", "sequence", "时序图", "时序"),
        validator=validate_mermaid_syntax,
        selection_guidance=(
            "Use sequence when the user asks for interactions between actors/services over time and message exchanges."
        ),
        positive_example=(
            "sequenceDiagram\n"
            "    participant U as 用户\n"
            "    participant API as 接口\n"
            "    participant DB as 数据库\n"
            "    U->>API: 提交查询\n"
            "    API->>DB: SELECT * FROM t\n"
            "    DB-->>API: 结果集\n"
            "    API-->>U: JSON 响应"
        ),
    ),
}

_PROMPT_ORDER = ("mindmap", "flowchart", "sequence")

_HEADER_PREAMBLE = (
    "---\n"
    "Active skill: /diagram\n"
    "You create or maintain diagrams for notebook content.\n"
    "Before final response, call at least one real diagram operation tool (for example create_diagram).\n"
    "Do not output raw <tool_call>...</tool_call> markup in assistant text.\n"
    "Universal prohibitions:\n"
    "- content must not include markdown code fences (```).\n"
    "- content must not include placeholders (TODO / 待补充 / ...).\n"
    "- content must not include natural-language wrappers before or after diagram syntax.\n"
)

_OPERATIONAL_RULES = (
    "Operational rules:\n"
    "- If user intent is explicit, call create_diagram directly with the chosen diagram_type.\n"
    "- If user intent is ambiguous, call confirm_diagram_type first, then create_diagram after approval.\n"
    "- For mindmap use mindmap JSON schema; for flowchart/sequence use Mermaid syntax.\n"
    "- If notebook documents are available, ground node labels/messages in evidence.\n"
    "- If notebook documents are unavailable, still generate a useful diagram from user intent.\n"
    "- Do not ask user to open notebook pages and do not echo diagram_id unless explicitly requested.\n"
    "---"
)


def _render_type_overview() -> str:
    lines = [
        "Supported diagram types:",
        "",
        "| type | output | selection guidance |",
        "| --- | --- | --- |",
    ]
    output_names = {
        "mindmap": "mindmap JSON schema",
        "flowchart": "Mermaid flowchart",
        "sequence": "Mermaid sequenceDiagram",
    }

    for diagram_type in _PROMPT_ORDER:
        descriptor = DIAGRAM_TYPE_REGISTRY[diagram_type]
        lines.append(
            f"| {descriptor.name} | {output_names.get(diagram_type, descriptor.output_format)} | "
            f"{descriptor.selection_guidance} |"
        )
    return "\n".join(lines)


def _render_type_section(descriptor: DiagramTypeDescriptor) -> str:
    return (
        f"=== {descriptor.name} rules ===\n"
        f"{descriptor.agent_system_prompt}\n\n"
        f"Minimal valid example:\n{descriptor.positive_example}"
    )


def build_diagram_system_prompt() -> str:
    """Build full system prompt addition from the registry descriptors."""

    sections = [_HEADER_PREAMBLE, _render_type_overview()]
    for diagram_type in _PROMPT_ORDER:
        sections.append(_render_type_section(DIAGRAM_TYPE_REGISTRY[diagram_type]))
    sections.append(_OPERATIONAL_RULES)
    return "\n\n".join(sections)


def get_descriptor(diagram_type: str) -> DiagramTypeDescriptor:
    """Get one descriptor by name."""

    descriptor = DIAGRAM_TYPE_REGISTRY.get(diagram_type)
    if descriptor is None:
        available = ", ".join(sorted(DIAGRAM_TYPE_REGISTRY.keys()))
        raise DiagramTypeNotFoundError(
            f"Diagram type '{diagram_type}' is not registered. Available: {available}"
        )
    return descriptor


def infer_diagram_type_from_prompt(prompt: str) -> str | None:
    """Infer diagram type from prompt text using registry hints."""

    normalized = str(prompt or "").lower()
    for diagram_type in _PROMPT_ORDER:
        descriptor = DIAGRAM_TYPE_REGISTRY[diagram_type]
        for hint in descriptor.intent_hints:
            if hint.lower() in normalized:
                return diagram_type
    return None
