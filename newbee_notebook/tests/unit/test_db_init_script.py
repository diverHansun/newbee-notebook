from pathlib import Path

from newbee_notebook.infrastructure.persistence.database import get_runtime_schema_statements


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
