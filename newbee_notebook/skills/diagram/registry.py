"""Diagram type registry and validators."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, ValidationError

from newbee_notebook.application.services.diagram_service import (
    DiagramTypeNotFoundError,
    DiagramValidationError,
)


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
    """Validate agent-generated content against the reactflow schema."""

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise DiagramValidationError(f"Invalid JSON content: {exc}") from exc

    try:
        ReactFlowDiagramSchema.model_validate(parsed)
    except ValidationError as exc:
        raise DiagramValidationError(f"Diagram schema validation failed: {exc}") from exc

    for node in parsed.get("nodes", []):
        if "position" in node:
            raise DiagramValidationError(
                f"Node '{node.get('id', '<unknown>')}' includes unsupported field 'position'."
            )


def validate_mermaid_syntax(content: str) -> None:
    """Validate a minimal Mermaid syntax header for supported diagram types."""

    normalized = str(content or "").strip()
    if not normalized:
        raise DiagramValidationError("Mermaid syntax cannot be empty.")

    first_line = next((line.strip() for line in normalized.splitlines() if line.strip()), "")
    if not first_line.startswith(("flowchart ", "graph ", "sequenceDiagram")):
        raise DiagramValidationError(
            "Mermaid syntax must start with 'flowchart', 'graph', or 'sequenceDiagram'."
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


DIAGRAM_TYPE_REGISTRY: dict[str, DiagramTypeDescriptor] = {
    "mindmap": DiagramTypeDescriptor(
        name="mindmap",
        output_format="reactflow_json",
        file_extension=".json",
        description="Mind map",
        agent_system_prompt=(
            "Generate a mind map in strict JSON format with only two top-level arrays: "
            "'nodes' and 'edges'.\n"
            "- Each node must include: id, label\n"
            "- Each edge must include: source, target\n"
            "- Do not output any markdown fences or extra commentary.\n"
            "- Do not include node position fields. Positioning is handled by frontend layout."
        ),
        intent_hints=("mind map", "mindmap", "mind-map", "思维导图", "脑图"),
        validator=validate_reactflow_schema,
    ),
    "flowchart": DiagramTypeDescriptor(
        name="flowchart",
        output_format="mermaid",
        file_extension=".mmd",
        description="Flow chart",
        agent_system_prompt=(
            "Generate a Mermaid flowchart.\n"
            "- Output raw Mermaid syntax only. Do not wrap it in markdown fences.\n"
            "- Start with 'flowchart TD' unless another direction is clearly better.\n"
            "- Keep the flow readable from start to end.\n"
            "- Use concise node labels grounded in notebook evidence."
        ),
        intent_hints=("flow chart", "flowchart", "流程图", "流程"),
        validator=validate_mermaid_syntax,
    ),
    "sequence": DiagramTypeDescriptor(
        name="sequence",
        output_format="mermaid",
        file_extension=".mmd",
        description="Sequence diagram",
        agent_system_prompt=(
            "Generate a Mermaid sequence diagram.\n"
            "- Output raw Mermaid syntax only. Do not wrap it in markdown fences.\n"
            "- Start with 'sequenceDiagram'.\n"
            "- Use participants and messages grounded in notebook evidence.\n"
            "- Keep the interaction order concise and readable."
        ),
        intent_hints=("sequence diagram", "sequence", "时序图", "时序"),
        validator=validate_mermaid_syntax,
    ),
}


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
    for diagram_type, descriptor in DIAGRAM_TYPE_REGISTRY.items():
        for hint in descriptor.intent_hints:
            if hint.lower() in normalized:
                return diagram_type
    return None
