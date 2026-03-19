"""Provider for the /diagram runtime skill."""

from __future__ import annotations

from newbee_notebook.application.services.diagram_service import DiagramService
from newbee_notebook.core.skills import SkillContext, SkillManifest
from newbee_notebook.skills.diagram.tools import (
    _build_confirm_diagram_type_tool,
    _build_create_diagram_tool,
    _build_delete_diagram_tool,
    _build_list_diagrams_tool,
    _build_read_diagram_tool,
    _build_update_diagram_positions_tool,
    _build_update_diagram_tool,
)

DIAGRAM_SLASH_COMMAND = "/diagram"


class DiagramSkillProvider:
    """Runtime skill provider for diagram creation and management."""

    def __init__(self, *, diagram_service: DiagramService) -> None:
        self._diagram_service = diagram_service

    @property
    def skill_name(self) -> str:
        return "diagram"

    @property
    def slash_commands(self) -> list[str]:
        return [DIAGRAM_SLASH_COMMAND]

    def build_manifest(self, context: SkillContext) -> SkillManifest:
        return SkillManifest(
            name="diagram",
            slash_command=DIAGRAM_SLASH_COMMAND,
            description="Diagram generation and management skill",
            system_prompt_addition=(
                "---\n"
                "Active skill: /diagram\n"
                "You must infer the target diagram type from user intent.\n"
                "When type is explicit, call create_diagram directly with diagram_type.\n"
                "When type is ambiguous, call confirm_diagram_type first and wait for user approval.\n"
                "Always use registered diagram types only.\n"
                "---"
            ),
            tools=[
                _build_list_diagrams_tool(
                    service=self._diagram_service,
                    notebook_id=context.notebook_id,
                ),
                _build_read_diagram_tool(service=self._diagram_service),
                _build_confirm_diagram_type_tool(),
                _build_create_diagram_tool(
                    service=self._diagram_service,
                    notebook_id=context.notebook_id,
                ),
                _build_update_diagram_tool(service=self._diagram_service),
                _build_update_diagram_positions_tool(service=self._diagram_service),
                _build_delete_diagram_tool(service=self._diagram_service),
            ],
            confirmation_required=frozenset(
                {
                    "confirm_diagram_type",
                    "update_diagram",
                    "delete_diagram",
                }
            ),
            force_first_tool_call=True,
        )
