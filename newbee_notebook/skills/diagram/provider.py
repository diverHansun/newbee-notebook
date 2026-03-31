"""Provider for the /diagram runtime skill."""

from __future__ import annotations

from newbee_notebook.application.services.diagram_service import DiagramService
from newbee_notebook.core.skills import SkillContext, SkillManifest
from newbee_notebook.core.skills.contracts import ConfirmationMeta
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
            system_prompt_addition=(
                "---\n"
                "Active skill: /diagram\n"
                "Supported diagram types: mindmap, flowchart, sequence.\n"
                "A /diagram request must call at least one real diagram operation tool before final response.\n"
                "Do not output raw <tool_call>...</tool_call> markup in assistant text.\n"
                "You must infer the target diagram type from user intent.\n"
                "When type is explicit, call create_diagram directly with diagram_type.\n"
                "When type is ambiguous, call confirm_diagram_type first and wait for user approval.\n"
                "After confirmation is approved, call create_diagram immediately.\n"
                "For mindmap, create_diagram content must be strict JSON with exactly two top-level arrays: "
                "nodes and edges.\n"
                "For flowchart and sequence, create_diagram content must be raw Mermaid syntax only.\n"
                "When notebook documents are available, use notebook evidence to build real node labels and structure.\n"
                "If notebook documents are unavailable, still generate a useful diagram from user intent only.\n"
                "Do not use placeholders.\n"
                "If no better title is available, provide a concise descriptive title.\n"
                "Always use one of the supported types only.\n"
                "Do not tell the user to open the notebook or echo raw diagram IDs unless the user explicitly asks. "
                "The Studio UI already shows diagram IDs.\n"
                "---"
            ),
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
