"""Tool factories for the /diagram runtime skill."""

from __future__ import annotations

from typing import Any

from newbee_notebook.application.services.diagram_service import (
    DiagramFormatMismatchError,
    DiagramNotFoundError,
    DiagramService,
    DiagramTypeNotFoundError,
    DiagramValidationError,
)
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition
from newbee_notebook.domain.entities.diagram import Diagram


def _safe_error_result(message: str, error: str) -> ToolCallResult:
    return ToolCallResult(content=message, error=error)


def _format_diagram_item(index: int, diagram: Diagram) -> str:
    document_text = ", ".join(diagram.document_ids) if diagram.document_ids else "none"
    updated_text = diagram.updated_at.strftime("%Y-%m-%d %H:%M")
    return (
        f"{index}. [{diagram.title}] - diagram ID: {diagram.diagram_id} - type: {diagram.diagram_type} "
        f"- documents: {document_text} - updated at {updated_text}"
    )


def _build_list_diagrams_tool(service: DiagramService, notebook_id: str) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            diagrams = await service.list_diagrams(
                notebook_id=notebook_id,
                document_id=args.get("document_id"),
            )
        except Exception as exc:
            return _safe_error_result(f"Failed to list diagrams: {exc}", "list_diagrams_failed")

        if not diagrams:
            return ToolCallResult(content="No diagrams found in the current notebook.")

        lines = [f"Found {len(diagrams)} diagram(s):"]
        lines.extend(_format_diagram_item(index, diagram) for index, diagram in enumerate(diagrams, start=1))
        return ToolCallResult(content="\n".join(lines))

    return ToolDefinition(
        name="list_diagrams",
        description="List diagrams in the current notebook. Supports optional document filtering.",
        parameters={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Optional document filter.",
                }
            },
            "required": [],
        },
        execute=execute,
    )


def _build_read_diagram_tool(service: DiagramService, notebook_id: str) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        diagram_id = str(args.get("diagram_id") or "")
        try:
            diagram = await service.get_diagram(diagram_id, notebook_id=notebook_id)
            content = await service.get_diagram_content(diagram_id, notebook_id=notebook_id)
        except DiagramNotFoundError as exc:
            return _safe_error_result(str(exc), "diagram_not_found")

        return ToolCallResult(
            content=content,
            metadata={
                "diagram_id": diagram.diagram_id,
                "diagram_type": diagram.diagram_type,
                "format": diagram.format,
            },
        )

    return ToolDefinition(
        name="read_diagram",
        description="Read diagram content and metadata by ID.",
        parameters={
            "type": "object",
            "properties": {
                "diagram_id": {"type": "string", "description": "Diagram ID"},
            },
            "required": ["diagram_id"],
        },
        execute=execute,
    )


def _build_confirm_diagram_type_tool() -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        diagram_type = str(args.get("diagram_type") or "")
        title = str(args.get("title") or "")
        reason = str(args.get("reason") or "")
        return ToolCallResult(
            content=(
                f"Diagram type confirmed: {diagram_type}. "
                "Proceed to create_diagram with this type."
            ),
            metadata={
                "diagram_type": diagram_type,
                "title": title,
                "reason": reason,
            },
        )

    return ToolDefinition(
        name="confirm_diagram_type",
        description=(
            "Ask user confirmation for inferred diagram type before creating a diagram. "
            "Use this tool when prompt intent is ambiguous."
        ),
        parameters={
            "type": "object",
            "properties": {
                "diagram_type": {
                    "type": "string",
                    "description": "Proposed diagram type.",
                },
                "title": {
                    "type": "string",
                    "description": "Optional title to confirm.",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation for the proposal.",
                },
            },
            "required": ["diagram_type", "reason"],
        },
        execute=execute,
    )


def _build_create_diagram_tool(service: DiagramService, notebook_id: str) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            diagram = await service.create_diagram(
                notebook_id=notebook_id,
                title=str(args.get("title") or ""),
                diagram_type=str(args.get("diagram_type") or ""),
                content=str(args.get("content") or ""),
                document_ids=list(args.get("document_ids") or []),
            )
        except DiagramTypeNotFoundError as exc:
            return _safe_error_result(str(exc), "diagram_type_not_found")
        except DiagramValidationError as exc:
            return _safe_error_result(f"Diagram validation failed: {exc}", "diagram_validation_failed")
        except ValueError as exc:
            return _safe_error_result(str(exc), "diagram_document_scope_invalid")
        except Exception as exc:
            return _safe_error_result(f"Failed to create diagram: {exc}", "create_diagram_failed")

        return ToolCallResult(
            content=f"Diagram created: [{diagram.title}]",
            metadata={
                "diagram_id": diagram.diagram_id,
                "diagram_type": diagram.diagram_type,
            },
        )

    return ToolDefinition(
        name="create_diagram",
        description=(
            "Create a diagram with explicit diagram type and full content payload. "
            "Use strict JSON for mindmap and raw Mermaid syntax for flowchart or sequence."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Diagram title"},
                "diagram_type": {"type": "string", "description": "Registered diagram type"},
                "content": {
                    "type": "string",
                    "description": (
                        "Full diagram content. For mindmap use strict JSON with top-level nodes and edges. "
                        "For flowchart or sequence use raw Mermaid syntax."
                    ),
                },
                "document_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional linked document IDs.",
                },
            },
            "required": ["title", "diagram_type", "content"],
        },
        execute=execute,
    )


def _build_update_diagram_tool(service: DiagramService, notebook_id: str) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            diagram = await service.update_diagram_content(
                diagram_id=str(args.get("diagram_id") or ""),
                content=str(args.get("content") or ""),
                title=(str(args["title"]) if "title" in args and args.get("title") is not None else None),
                notebook_id=notebook_id,
            )
        except DiagramNotFoundError as exc:
            return _safe_error_result(str(exc), "diagram_not_found")
        except DiagramValidationError as exc:
            return _safe_error_result(f"Diagram validation failed: {exc}", "diagram_validation_failed")
        except Exception as exc:
            return _safe_error_result(f"Failed to update diagram: {exc}", "update_diagram_failed")

        return ToolCallResult(content=f"Diagram updated: [{diagram.title}]")

    return ToolDefinition(
        name="update_diagram",
        description="Update diagram content and optional title. Requires confirmation.",
        parameters={
            "type": "object",
            "properties": {
                "diagram_id": {"type": "string", "description": "Diagram ID"},
                "title": {"type": "string", "description": "Optional new title"},
                "content": {"type": "string", "description": "Full updated content"},
            },
            "required": ["diagram_id", "content"],
        },
        execute=execute,
    )


def _build_delete_diagram_tool(service: DiagramService, notebook_id: str) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        diagram_id = str(args.get("diagram_id") or "")
        try:
            diagram = await service.get_diagram(diagram_id, notebook_id=notebook_id)
            await service.delete_diagram(diagram_id, notebook_id=notebook_id)
        except DiagramNotFoundError as exc:
            return _safe_error_result(str(exc), "diagram_not_found")
        except Exception as exc:
            return _safe_error_result(f"Failed to delete diagram: {exc}", "delete_diagram_failed")

        return ToolCallResult(content=f"Diagram deleted: [{diagram.title}]")

    return ToolDefinition(
        name="delete_diagram",
        description="Delete one diagram by ID. Requires confirmation.",
        parameters={
            "type": "object",
            "properties": {
                "diagram_id": {"type": "string", "description": "Diagram ID"},
            },
            "required": ["diagram_id"],
        },
        execute=execute,
    )


def _build_update_diagram_positions_tool(service: DiagramService, notebook_id: str) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            positions_arg = args.get("positions") or {}
            if not isinstance(positions_arg, dict):
                return _safe_error_result("positions must be an object", "diagram_positions_invalid")
            positions: dict[str, dict[str, float]] = {}
            for node_id, value in positions_arg.items():
                if not isinstance(value, dict):
                    return _safe_error_result(
                        f"Position for node {node_id} must be an object",
                        "diagram_positions_invalid",
                    )
                x = float(value.get("x", 0.0))
                y = float(value.get("y", 0.0))
                positions[str(node_id)] = {"x": x, "y": y}
            diagram = await service.update_node_positions(
                diagram_id=str(args.get("diagram_id") or ""),
                positions=positions,
                notebook_id=notebook_id,
            )
        except DiagramNotFoundError as exc:
            return _safe_error_result(str(exc), "diagram_not_found")
        except DiagramFormatMismatchError as exc:
            return _safe_error_result(str(exc), "diagram_format_mismatch")
        except ValueError as exc:
            return _safe_error_result(str(exc), "diagram_positions_invalid")
        except Exception as exc:
            return _safe_error_result(
                f"Failed to update diagram positions: {exc}",
                "update_diagram_positions_failed",
            )

        return ToolCallResult(
            content=f"Diagram positions updated: [{diagram.title}]",
            metadata={"diagram_id": diagram.diagram_id},
        )

    return ToolDefinition(
        name="update_diagram_positions",
        description="Update node positions for reactflow diagrams.",
        parameters={
            "type": "object",
            "properties": {
                "diagram_id": {"type": "string", "description": "Diagram ID"},
                "positions": {
                    "type": "object",
                    "description": "Map of node_id -> {x, y}.",
                },
            },
            "required": ["diagram_id", "positions"],
        },
        execute=execute,
    )


__all__ = [
    "_build_list_diagrams_tool",
    "_build_read_diagram_tool",
    "_build_confirm_diagram_type_tool",
    "_build_create_diagram_tool",
    "_build_update_diagram_tool",
    "_build_delete_diagram_tool",
    "_build_update_diagram_positions_tool",
]
