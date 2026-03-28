from pathlib import Path

from newbee_notebook.infrastructure.persistence.database import get_runtime_schema_statements
from newbee_notebook.infrastructure.persistence.models import Base


def test_init_postgres_declares_runtime_tables():
    sql_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "init-postgres.sql"
    )

    sql = sql_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS sessions (" in sql
    assert "CREATE TABLE IF NOT EXISTS notebook_document_refs (" in sql
    assert 'REFERENCES sessions(id)' in sql


def test_init_postgres_allows_agent_mode_in_messages():
    sql_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "init-postgres.sql"
    )

    sql = sql_path.read_text(encoding="utf-8")

    assert "mode VARCHAR(20) NOT NULL CHECK (mode IN ('agent','ask','conclude','explain'))" in sql


def test_runtime_schema_statements_backfill_messages_mode_constraint_for_agent():
    statements = get_runtime_schema_statements()

    assert any("UPDATE messages SET mode = 'agent' WHERE mode = 'chat'" in statement for statement in statements)
    assert any("DROP CONSTRAINT IF EXISTS messages_mode_check" in statement for statement in statements)
    assert any(
        "messages_mode_check" in statement and "'agent','ask','conclude','explain'" in statement
        for statement in statements
    )


def test_init_postgres_does_not_create_legacy_chat_tables():
    sql_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "init-postgres.sql"
    )

    sql = sql_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS chat_sessions (" not in sql
    assert "CREATE TABLE IF NOT EXISTS chat_messages (" not in sql
    assert "Legacy tables: chat_sessions, chat_messages" not in sql


def test_batch3_migration_sql_exists_with_notes_and_marks_tables():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "migrations"
        / "batch3_notes_marks.sql"
    )

    assert migration_path.exists()

    sql = migration_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS marks (" in sql
    assert "char_offset INTEGER NOT NULL CHECK (char_offset >= 0)" in sql
    assert "CREATE TABLE IF NOT EXISTS notes (" in sql
    assert "title TEXT NOT NULL DEFAULT ''" in sql
    assert "content TEXT NOT NULL DEFAULT ''" in sql
    assert "CREATE TABLE IF NOT EXISTS note_document_tags (" in sql
    assert "UNIQUE(note_id, document_id)" in sql
    assert "CREATE TABLE IF NOT EXISTS note_mark_refs (" in sql
    assert "UNIQUE(note_id, mark_id)" in sql


def test_batch4_migration_sql_exists_with_diagrams_table():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "migrations"
        / "batch4_diagrams.sql"
    )

    assert migration_path.exists()

    sql = migration_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS diagrams (" in sql
    assert "format TEXT NOT NULL CHECK (format IN ('reactflow_json', 'mermaid'))" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_diagrams_notebook_id" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_diagrams_document_ids" in sql


def test_batch6_migration_sql_exists_with_video_summaries_table():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "migrations"
        / "batch6_videos.sql"
    )

    assert migration_path.exists()

    sql = migration_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS video_summaries (" in sql
    assert "platform TEXT NOT NULL" in sql
    assert "video_id TEXT NOT NULL" in sql
    assert "document_ids UUID[] NOT NULL DEFAULT '{}'" in sql
    assert "UNIQUE(platform, video_id)" in sql


def test_runtime_schema_statements_backfill_batch6_video_tables():
    statements = "\n".join(get_runtime_schema_statements())

    assert "CREATE TABLE IF NOT EXISTS video_summaries (" in statements
    assert "CREATE INDEX IF NOT EXISTS idx_video_summaries_notebook_id" in statements
    assert "CREATE INDEX IF NOT EXISTS idx_video_summaries_document_ids" in statements


def test_init_postgres_declares_batch3_tables():
    sql_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "init-postgres.sql"
    )

    sql = sql_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS marks (" in sql
    assert "REFERENCES documents(id) ON DELETE CASCADE" in sql
    assert "CREATE TABLE IF NOT EXISTS notes (" in sql
    assert "REFERENCES notebooks(id) ON DELETE CASCADE" in sql
    assert "CREATE TABLE IF NOT EXISTS note_document_tags (" in sql
    assert "CREATE TABLE IF NOT EXISTS note_mark_refs (" in sql
    assert "CREATE TABLE IF NOT EXISTS diagrams (" in sql


def test_init_postgres_notice_mentions_video_summaries():
    sql_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "init-postgres.sql"
    )

    sql = sql_path.read_text(encoding="utf-8")

    assert "video_summaries" in sql
    assert "Core tables:" in sql


def test_runtime_schema_statements_backfill_batch3_tables():
    statements = "\n".join(get_runtime_schema_statements())

    assert "CREATE TABLE IF NOT EXISTS marks (" in statements
    assert "CREATE INDEX IF NOT EXISTS idx_marks_document_id" in statements
    assert "CREATE TABLE IF NOT EXISTS notes (" in statements
    assert "CREATE INDEX IF NOT EXISTS idx_notes_notebook_id" in statements
    assert "CREATE TABLE IF NOT EXISTS note_document_tags (" in statements
    assert "CREATE TABLE IF NOT EXISTS note_mark_refs (" in statements
    assert "CREATE TABLE IF NOT EXISTS diagrams (" in statements
    assert "CREATE INDEX IF NOT EXISTS idx_diagrams_notebook_id" in statements
    assert "CREATE INDEX IF NOT EXISTS idx_diagrams_document_ids" in statements


def test_batch3_models_are_present_in_sqlalchemy_metadata():
    table_names = Base.metadata.tables.keys()

    assert "marks" in table_names
    assert "notes" in table_names
    assert "note_document_tags" in table_names
    assert "note_mark_refs" in table_names
    assert "diagrams" in table_names
    assert "video_summaries" in table_names
