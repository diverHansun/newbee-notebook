from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from newbee_notebook.application.services.note_service import NoteNotFoundError
from newbee_notebook.core.skills import SkillContext
from newbee_notebook.domain.entities.mark import Mark
from newbee_notebook.domain.entities.note import Note
from newbee_notebook.skills.note.provider import NoteSkillProvider
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


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def note_service():
    return AsyncMock()


@pytest.fixture
def mark_service():
    return AsyncMock()


@pytest.mark.anyio
async def test_build_list_notes_tool_formats_notebook_notes(note_service):
    note_service.list_by_notebook.return_value = [
        Note(
            note_id="note-1",
            notebook_id="nb-1",
            title="Chapter 3",
            content="summary",
            document_ids=["doc-1", "doc-2"],
        )
    ]
    tool = build_list_notes_tool(note_service=note_service, notebook_id="nb-1")

    result = await tool.execute({})

    assert result.error is None
    assert "Found 1 note(s)" in result.content
    assert "Chapter 3" in result.content
    assert "note-1" in result.content
    note_service.list_by_notebook.assert_awaited_once_with("nb-1", document_id=None)


@pytest.mark.anyio
async def test_build_read_note_tool_includes_note_content_and_mark_refs(note_service, mark_service):
    note_service.get_or_raise.return_value = Note(
        note_id="note-1",
        notebook_id="nb-1",
        title="Chapter 3",
        content="See [[mark:mark-1]]",
        document_ids=["doc-1"],
        mark_ids=["mark-1"],
    )
    mark_service.get.return_value = Mark(
        mark_id="mark-1",
        document_id="doc-1",
        anchor_text="Transformer block",
        char_offset=42,
    )
    tool = build_read_note_tool(note_service=note_service, mark_service=mark_service)

    result = await tool.execute({"note_id": "note-1"})

    assert result.error is None
    assert "Chapter 3" in result.content
    assert "See [[mark:mark-1]]" in result.content
    assert "Transformer block" in result.content


@pytest.mark.anyio
async def test_build_create_note_tool_creates_notebook_scoped_note(note_service):
    note_service.create.return_value = Note(
        note_id="note-1",
        notebook_id="nb-1",
        title="New Note",
        content="hello",
        document_ids=["doc-1"],
    )
    tool = build_create_note_tool(note_service=note_service, notebook_id="nb-1")

    result = await tool.execute({"title": "New Note", "content": "hello", "document_ids": ["doc-1"]})

    assert result.error is None
    assert "Note created" in result.content
    assert "note-1" in result.content
    note_service.create.assert_awaited_once_with(
        notebook_id="nb-1",
        title="New Note",
        content="hello",
        document_ids=["doc-1"],
    )


@pytest.mark.anyio
async def test_build_update_note_tool_returns_error_for_missing_note(note_service):
    note_service.update.side_effect = NoteNotFoundError("missing")
    tool = build_update_note_tool(note_service=note_service)

    result = await tool.execute({"note_id": "missing", "title": "Updated"})

    assert result.error == "note_not_found"
    assert "missing" in result.content


@pytest.mark.anyio
async def test_build_associate_and_disassociate_tools_delegate_to_service(note_service):
    note_service.get_or_raise.return_value = Note(
        note_id="note-1",
        notebook_id="nb-1",
        title="Existing",
        content="",
    )
    associate_tool = build_associate_note_document_tool(note_service=note_service)
    disassociate_tool = build_disassociate_note_document_tool(note_service=note_service)

    associate_result = await associate_tool.execute({"note_id": "note-1", "document_id": "doc-1"})
    disassociate_result = await disassociate_tool.execute({"note_id": "note-1", "document_id": "doc-1"})

    assert associate_result.error is None
    assert "Linked note" in associate_result.content
    assert disassociate_result.error is None
    assert "Removed document" in disassociate_result.content
    note_service.add_document_tag.assert_awaited_once_with("note-1", "doc-1")
    note_service.remove_document_tag.assert_awaited_once_with("note-1", "doc-1")


@pytest.mark.anyio
async def test_build_list_marks_tool_uses_notebook_scope(mark_service):
    mark_service.list_by_notebook.return_value = [
        Mark(mark_id="mark-1", document_id="doc-1", anchor_text="Important line", char_offset=12)
    ]
    tool = build_list_marks_tool(mark_service=mark_service, notebook_id="nb-1")

    result = await tool.execute({"document_id": "doc-1"})

    assert result.error is None
    assert "Found 1 mark(s)" in result.content
    assert "Important line" in result.content
    mark_service.list_by_notebook.assert_awaited_once_with("nb-1", document_id="doc-1")


def test_note_skill_provider_builds_manifest_with_expected_tools(note_service, mark_service):
    provider = NoteSkillProvider(note_service=note_service, mark_service=mark_service)

    manifest = provider.build_manifest(
        SkillContext(
            notebook_id="nb-1",
            activated_command="/note",
            selected_document_ids=["doc-1"],
        )
    )

    assert manifest.name == "note"
    assert manifest.slash_command == "/note"
    assert manifest.confirmation_required == frozenset(
        {"update_note", "delete_note", "disassociate_note_document"}
    )
    assert manifest.force_first_tool_call is True
    assert [tool.name for tool in manifest.tools] == [
        "list_notes",
        "read_note",
        "create_note",
        "update_note",
        "delete_note",
        "list_marks",
        "associate_note_document",
        "disassociate_note_document",
    ]
    assert "use the available note and mark tools" in manifest.system_prompt_addition.lower()
    assert "do not ask the user to confirm in plain text" in manifest.system_prompt_addition.lower()
    assert "runtime confirmation flow" in manifest.system_prompt_addition.lower()
