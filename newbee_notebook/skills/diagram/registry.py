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
        output_format="reactflow_json",
        file_extension=".json",
        description="Flow chart",
        agent_system_prompt=(
            "Generate a flow chart in strict JSON format with only two top-level arrays: "
            "'nodes' and 'edges'.\n"
            "- Each node must include: id, label\n"
            "- Each edge must include: source, target\n"
            "- Keep graph flow direction clear from start to end.\n"
            "- Do not output markdown fences or extra commentary.\n"
            "- Do not include node position fields. Positioning is handled by frontend layout."
        ),
        intent_hints=("flow chart", "flowchart", "流程图", "流程"),
        validator=validate_reactflow_schema,
    ),
    "sequence": DiagramTypeDescriptor(
        name="sequence",
        output_format="reactflow_json",
        file_extension=".json",
        description="Sequence diagram",
        agent_system_prompt=(
            "Generate a sequence-style graph in strict JSON format with only two top-level arrays: "
            "'nodes' and 'edges'.\n"
            "- Each node must include: id, label\n"
            "- Each edge must include: source, target\n"
            "- Use node labels to represent actors/components and ordered interaction steps.\n"
            "- Do not output markdown fences or extra commentary.\n"
            "- Do not include node position fields. Positioning is handled by frontend layout."
        ),
        intent_hints=("sequence diagram", "sequence", "时序图", "时序"),
        validator=validate_reactflow_schema,
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
