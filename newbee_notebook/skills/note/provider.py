"""Provider for the /note runtime skill."""

from __future__ import annotations

from newbee_notebook.application.services.mark_service import MarkService
from newbee_notebook.application.services.note_service import NoteService
from newbee_notebook.core.skills import SkillContext, SkillManifest
from newbee_notebook.skills.note.tools import (
    build_associate_note_document_tool,
    build_create_note_tool,
    build_delete_note_tool,
    build_disassociate_note_document_tool,
    build_list_marks_tool,
    build_list_notes_tool,
    build_read_note_tool,
    build_update_note_tool,
)


class NoteSkillProvider:
    def __init__(self, *, note_service: NoteService, mark_service: MarkService) -> None:
        self._note_service = note_service
        self._mark_service = mark_service

    @property
    def skill_name(self) -> str:
        return "note"

    @property
    def slash_commands(self) -> list[str]:
        return ["/note"]

    def build_manifest(self, context: SkillContext) -> SkillManifest:
        return SkillManifest(
            name="note",
            slash_command=context.activated_command,
            description="Note and mark management skill",
            system_prompt_addition=(
                "---\n"
                "Active skill: /note\n"
                "You can use the available tools to manage notes and inspect marks. "
                "Before editing or deleting data, explain the intended action to the user.\n"
                "---"
            ),
            tools=[
                build_list_notes_tool(note_service=self._note_service, notebook_id=context.notebook_id),
                build_read_note_tool(note_service=self._note_service, mark_service=self._mark_service),
                build_create_note_tool(note_service=self._note_service, notebook_id=context.notebook_id),
                build_update_note_tool(note_service=self._note_service),
                build_delete_note_tool(note_service=self._note_service),
                build_list_marks_tool(mark_service=self._mark_service, notebook_id=context.notebook_id),
                build_associate_note_document_tool(note_service=self._note_service),
                build_disassociate_note_document_tool(note_service=self._note_service),
            ],
            confirmation_required=frozenset(
                {"update_note", "delete_note", "disassociate_note_document"}
            ),
        )
