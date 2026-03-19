"""Tool factories for the /note runtime skill."""

from __future__ import annotations

from typing import Any

from newbee_notebook.application.services.mark_service import MarkService
from newbee_notebook.application.services.note_service import NoteNotFoundError, NoteService
from newbee_notebook.domain.entities.mark import Mark
from newbee_notebook.domain.entities.note import Note
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition


def _note_label(note: Note) -> str:
    return note.title or "Untitled note"


def _mark_preview(mark: Mark) -> str:
    return f"\"{mark.anchor_text}\" - document {mark.document_id}"


def _safe_error_result(message: str, error: str) -> ToolCallResult:
    return ToolCallResult(content=message, error=error)


def _format_notes(notes: list[Note]) -> str:
    if not notes:
        return "No notes found in the current notebook."

    lines = [f"Found {len(notes)} note(s):"]
    for index, note in enumerate(notes, start=1):
        document_text = ", ".join(note.document_ids) if note.document_ids else "No linked documents"
        updated_text = note.updated_at.strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"{index}. [{_note_label(note)}] - linked documents: {document_text} - updated at {updated_text}"
        )
    return "\n".join(lines)


def _format_marks(marks: list[Mark]) -> str:
    if not marks:
        return "No marks found in the current scope."

    lines = [f"Found {len(marks)} mark(s):"]
    for index, mark in enumerate(marks, start=1):
        lines.append(f'{index}. "{mark.anchor_text}" - from document {mark.document_id}')
    return "\n".join(lines)


def build_list_notes_tool(*, note_service: NoteService, notebook_id: str) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            notes = await note_service.list_by_notebook(
                notebook_id,
                document_id=args.get("document_id"),
            )
        except Exception as exc:
            return _safe_error_result(f"Failed to list notes: {exc}", "list_notes_failed")
        return ToolCallResult(content=_format_notes(notes))

    return ToolDefinition(
        name="list_notes",
        description="List notes in the current notebook. Supports optional document filtering.",
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
        execute=_execute,
    )


def build_read_note_tool(*, note_service: NoteService, mark_service: MarkService) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        note_id = str(args.get("note_id") or "")
        try:
            note = await note_service.get_or_raise(note_id)
        except NoteNotFoundError as exc:
            return _safe_error_result(str(exc), "note_not_found")

        marks: list[Mark] = []
        for mark_id in note.mark_ids:
            mark = await mark_service.get(mark_id)
            if mark is not None:
                marks.append(mark)

        lines = [
            f"Title: {_note_label(note)}",
            f"Note ID: {note.note_id}",
            f"Markdown content:\n{note.content}",
            f"Linked documents: {', '.join(note.document_ids) if note.document_ids else 'None'}",
        ]
        if marks:
            lines.append("Referenced marks:")
            lines.extend(f"- {_mark_preview(mark)}" for mark in marks)
        else:
            lines.append("Referenced marks: None")
        return ToolCallResult(content="\n".join(lines))

    return ToolDefinition(
        name="read_note",
        description="Read a note, including markdown content and referenced marks.",
        parameters={
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "description": "Note ID"},
            },
            "required": ["note_id"],
        },
        execute=_execute,
    )


def build_create_note_tool(*, note_service: NoteService, notebook_id: str) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            note = await note_service.create(
                notebook_id=notebook_id,
                title=str(args.get("title") or ""),
                content=str(args.get("content") or ""),
                document_ids=list(args.get("document_ids") or []),
            )
        except Exception as exc:
            return _safe_error_result(f"Failed to create note: {exc}", "create_note_failed")

        return ToolCallResult(content=f"Note created: [{_note_label(note)}], ID: {note.note_id}")

    return ToolDefinition(
        name="create_note",
        description="Create a new note with optional content and linked documents.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title"},
                "content": {"type": "string", "description": "Optional initial markdown content."},
                "document_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional linked document IDs.",
                },
            },
            "required": ["title"],
        },
        execute=_execute,
    )


def build_update_note_tool(*, note_service: NoteService) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            note = await note_service.update(
                note_id=str(args.get("note_id") or ""),
                title=args.get("title"),
                content=args.get("content"),
            )
        except NoteNotFoundError as exc:
            return _safe_error_result(str(exc), "note_not_found")
        except Exception as exc:
            return _safe_error_result(f"Failed to update note: {exc}", "update_note_failed")

        return ToolCallResult(content=f"Note updated: [{_note_label(note)}]")

    return ToolDefinition(
        name="update_note",
        description="Update a note title or markdown content. Requires user confirmation.",
        parameters={
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "description": "Note ID"},
                "title": {"type": "string", "description": "Optional new title."},
                "content": {"type": "string", "description": "Optional new markdown content."},
            },
            "required": ["note_id"],
        },
        execute=_execute,
    )


def build_delete_note_tool(*, note_service: NoteService) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        note_id = str(args.get("note_id") or "")
        try:
            note = await note_service.get_or_raise(note_id)
            await note_service.delete(note_id)
        except NoteNotFoundError as exc:
            return _safe_error_result(str(exc), "note_not_found")
        except Exception as exc:
            return _safe_error_result(f"Failed to delete note: {exc}", "delete_note_failed")

        return ToolCallResult(content=f"Note deleted: [{_note_label(note)}]")

    return ToolDefinition(
        name="delete_note",
        description="Delete a note. Linked document tags and mark refs are removed as well. Requires confirmation.",
        parameters={
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "description": "Note ID"},
            },
            "required": ["note_id"],
        },
        execute=_execute,
    )


def build_list_marks_tool(*, mark_service: MarkService, notebook_id: str) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            marks = await mark_service.list_by_notebook(
                notebook_id,
                document_id=args.get("document_id"),
            )
        except Exception as exc:
            return _safe_error_result(f"Failed to list marks: {exc}", "list_marks_failed")
        return ToolCallResult(content=_format_marks(marks))

    return ToolDefinition(
        name="list_marks",
        description="List marks in the current notebook. Supports optional document filtering.",
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
        execute=_execute,
    )


def build_associate_note_document_tool(*, note_service: NoteService) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        note_id = str(args.get("note_id") or "")
        document_id = str(args.get("document_id") or "")
        try:
            note = await note_service.get_or_raise(note_id)
            await note_service.add_document_tag(note_id, document_id)
        except NoteNotFoundError as exc:
            return _safe_error_result(str(exc), "note_not_found")
        except Exception as exc:
            return _safe_error_result(
                f"Failed to link the document to the note: {exc}",
                "associate_note_document_failed",
            )

        return ToolCallResult(content=f"Linked note [{_note_label(note)}] to document [{document_id}]")

    return ToolDefinition(
        name="associate_note_document",
        description="Link a note to a document.",
        parameters={
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "description": "Note ID"},
                "document_id": {"type": "string", "description": "Document ID to link"},
            },
            "required": ["note_id", "document_id"],
        },
        execute=_execute,
    )


def build_disassociate_note_document_tool(*, note_service: NoteService) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        note_id = str(args.get("note_id") or "")
        document_id = str(args.get("document_id") or "")
        try:
            note = await note_service.get_or_raise(note_id)
            await note_service.remove_document_tag(note_id, document_id)
        except NoteNotFoundError as exc:
            return _safe_error_result(str(exc), "note_not_found")
        except Exception as exc:
            return _safe_error_result(
                f"Failed to unlink the document from the note: {exc}",
                "disassociate_note_document_failed",
            )

        return ToolCallResult(
            content=f"Removed document [{document_id}] from note [{_note_label(note)}]"
        )

    return ToolDefinition(
        name="disassociate_note_document",
        description="Remove the link between a note and a document. Requires confirmation.",
        parameters={
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "description": "Note ID"},
                "document_id": {"type": "string", "description": "Document ID to unlink"},
            },
            "required": ["note_id", "document_id"],
        },
        execute=_execute,
    )
