from pathlib import Path

from newbee_notebook.core.context.session_memory import StoredMessage
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.value_objects import mode_type as mode_type_module
from newbee_notebook.infrastructure.persistence.models import MessageModel, SessionModel


def test_context_compaction_declares_message_type_contracts():
    assert hasattr(mode_type_module, "MessageType")
    assert "message_type" in Message.__dataclass_fields__
    assert "message_type" in StoredMessage.__dataclass_fields__
    assert "message_type" in MessageModel.__table__.columns


def test_context_compaction_declares_session_boundary_contract():
    field = Session.__dataclass_fields__.get("compaction_boundary_id")

    assert field is not None
    assert field.default is None
    assert "compaction_boundary_id" in SessionModel.__table__.columns


def test_batch5_context_compaction_migration_exists():
    migration_path = (
        Path(__file__).resolve().parents[5]
        / "newbee_notebook"
        / "scripts"
        / "db"
        / "migrations"
        / "batch5_context_compaction.sql"
    )

    assert migration_path.exists()
