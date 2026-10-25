"""Naive database wall times must carry the server offset on the wire."""

import time
from datetime import datetime, timedelta, timezone

import pytest

from newbee_notebook.api.models.responses import NotebookResponse
from newbee_notebook.api.models.note_models import NoteResponse


@pytest.mark.parametrize("server_tz,offset", [("UTC", 0), ("Asia/Taipei", 8)])
def test_database_timestamps_preserve_instant_across_browser_timezones(monkeypatch, server_tz, offset):
    if not hasattr(time, "tzset"):
        pytest.skip("tzset is needed to simulate server time zones")
    with monkeypatch.context() as env:
        env.setenv("TZ", server_tz)
        time.tzset()
        try:
            value = datetime(2026, 10, 25, 7, 12)
            notebook = NotebookResponse(
                notebook_id="nb", title="Test", description=None,
                session_count=0, document_count=0, created_at=value, updated_at=value,
            )
            note = NoteResponse(
                note_id="note", notebook_id="nb", title="Test", content="Test",
                document_ids=[], mark_ids=[], created_at=value, updated_at=value,
            )
            for response in (notebook, note):
                for name in ("created_at", "updated_at"):
                    parsed = datetime.fromisoformat(response.model_dump(mode="json")[name])
                    assert parsed.utcoffset() == timedelta(hours=offset)
                    assert parsed.timestamp() == value.timestamp()
        finally:
            # Restore environment before resetting the process-global timezone.
            env.undo()
            time.tzset()


def test_explicit_timestamp_offset_is_preserved():
    value = datetime(2026, 10, 25, 15, 12, tzinfo=timezone(timedelta(hours=8)))
    notebook = NotebookResponse(
        notebook_id="nb", title="Test", description=None,
        session_count=0, document_count=0, created_at=value, updated_at=value,
    )
    assert notebook.model_dump(mode="json")["created_at"] == value.isoformat()
