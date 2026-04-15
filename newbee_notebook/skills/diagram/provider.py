"""Provider for the /diagram runtime skill."""

from __future__ import annotations

from newbee_notebook.application.services.diagram_service import DiagramService
from newbee_notebook.core.skills import SkillContext, SkillManifest
from newbee_notebook.core.skills.contracts import ConfirmationMeta
from newbee_notebook.skills.diagram.registry import build_diagram_system_prompt
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

DIAGRAM_OPERATION_TOOLS = frozenset(
    {
        "create_diagram",
        "update_diagram",
        "delete_diagram",
        "list_diagrams",
        "read_diagram",
    }
)


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
            system_prompt_addition=build_diagram_system_prompt(),
            tools=[
                _build_list_diagrams_tool(
                    service=self._diagram_service,
                    notebook_id=context.notebook_id,
                ),
                _build_read_diagram_tool(
                    service=self._diagram_service,
                    notebook_id=context.notebook_id,
                ),
                _build_confirm_diagram_type_tool(),
                _build_create_diagram_tool(
                    service=self._diagram_service,
                    notebook_id=context.notebook_id,
                ),
                _build_update_diagram_tool(
                    service=self._diagram_service,
                    notebook_id=context.notebook_id,
                ),
                _build_update_diagram_positions_tool(
                    service=self._diagram_service,
                    notebook_id=context.notebook_id,
                ),
                _build_delete_diagram_tool(
                    service=self._diagram_service,
                    notebook_id=context.notebook_id,
                ),
            ],
            confirmation_required=frozenset(
                {
                    "confirm_diagram_type",
                    "update_diagram",
                    "delete_diagram",
                }
            ),
            confirmation_meta={
                "confirm_diagram_type": ConfirmationMeta(
                    action_type="confirm", target_type="diagram"
                ),
                "update_diagram": ConfirmationMeta(
                    action_type="update", target_type="diagram"
                ),
                "delete_diagram": ConfirmationMeta(
                    action_type="delete", target_type="diagram"
                ),
            },
            force_first_tool_call=True,
            required_tool_call_before_response=DIAGRAM_OPERATION_TOOLS,
        )
