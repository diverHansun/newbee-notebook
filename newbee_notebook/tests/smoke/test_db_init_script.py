import os
import re
import uuid
from pathlib import Path

import pytest
from newbee_notebook.infrastructure.persistence.database import get_runtime_schema_statements
from newbee_notebook.infrastructure.persistence.models import Base


@pytest.fixture
def anyio_backend():
    return "asyncio"


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
    assert "CONSTRAINT ck_diagrams_format" in sql
    assert "format IN ('reactflow_json', 'mermaid', 'echarts_option')" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_diagrams_notebook_id" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_diagrams_document_ids" in sql


def test_batch9_migration_sql_updates_diagram_format_check_for_echarts():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "migrations"
        / "batch9_diagrams_echarts.sql"
    )

    assert migration_path.exists()

    sql = migration_path.read_text(encoding="utf-8")

    assert "pg_constraint" in sql
    assert "ck_diagrams_format" in sql
    assert "diagrams_format_check" in sql
    assert "echarts_option" in sql
    assert "format IN ('reactflow_json', 'mermaid', 'echarts_option')" in sql
    assert "LIKE '%format%'" not in sql


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


def test_init_postgres_declares_batch6_video_table():
    sql_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "init-postgres.sql"
    )

    sql = sql_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS video_summaries (" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_video_summaries_notebook_id" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_video_summaries_document_ids" in sql


def test_runtime_schema_statements_backfill_batch3_tables():
    statements = "\n".join(get_runtime_schema_statements())

    assert "CREATE TABLE IF NOT EXISTS marks (" in statements
    assert "CREATE INDEX IF NOT EXISTS idx_marks_document_id" in statements
    assert "CREATE TABLE IF NOT EXISTS notes (" in statements
    assert "CREATE INDEX IF NOT EXISTS idx_notes_notebook_id" in statements
    assert "CREATE TABLE IF NOT EXISTS note_document_tags (" in statements
    assert "CREATE TABLE IF NOT EXISTS note_mark_refs (" in statements
    assert "CREATE TABLE IF NOT EXISTS diagrams (" in statements
    assert "CONSTRAINT ck_diagrams_format" in statements
    assert "format IN ('reactflow_json', 'mermaid', 'echarts_option')" in statements
    assert "CREATE INDEX IF NOT EXISTS idx_diagrams_notebook_id" in statements
    assert "CREATE INDEX IF NOT EXISTS idx_diagrams_document_ids" in statements


def test_runtime_schema_statements_update_existing_diagram_format_constraint():
    statements = "\n".join(get_runtime_schema_statements())

    assert "pg_constraint" in statements
    assert "ck_diagrams_format" in statements
    assert "diagrams_format_check" in statements
    assert "format IN ('reactflow_json', 'mermaid', 'echarts_option')" in statements
    assert "LIKE '%format%'" not in statements


@pytest.mark.anyio
async def test_batch9_migration_executes_against_ephemeral_postgres():
    asyncpg = pytest.importorskip("asyncpg")
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None

    if load_dotenv is not None:
        load_dotenv()

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    test_db = f"nb_echarts_migration_{uuid.uuid4().hex[:12]}"

    try:
        admin = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database="postgres",
            timeout=3,
        )
    except Exception as exc:  # pragma: no cover - environment dependent skip
        pytest.skip(f"PostgreSQL admin connection unavailable: {exc}")

    migration_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "migrations"
        / "batch9_diagrams_echarts.sql"
    )
    migration_sql = migration_path.read_text(encoding="utf-8")

    try:
        await admin.execute(f'CREATE DATABASE "{test_db}"')
    except Exception as exc:  # pragma: no cover - environment dependent skip
        await admin.close()
        pytest.skip(f"PostgreSQL test database creation unavailable: {exc}")

    conn = None
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=test_db,
            timeout=3,
        )
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        await conn.execute(
            """
            CREATE TABLE notebooks (
                id UUID PRIMARY KEY,
                title TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE diagrams (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                diagram_type TEXT NOT NULL,
                format TEXT NOT NULL CHECK (format IN ('reactflow_json', 'mermaid')),
                content_path TEXT NOT NULL,
                document_ids UUID[] NOT NULL DEFAULT '{}',
                node_positions JSONB,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        notebook_id = uuid.uuid4()
        await conn.execute("INSERT INTO notebooks(id, title) VALUES($1, 'test')", notebook_id)
        await conn.execute(
            """
            INSERT INTO diagrams(notebook_id, title, diagram_type, format, content_path)
            VALUES($1, 'Map', 'mindmap', 'reactflow_json', 'a.json')
            """,
            notebook_id,
        )
        await conn.execute(
            """
            INSERT INTO diagrams(notebook_id, title, diagram_type, format, content_path)
            VALUES($1, 'Flow', 'flowchart', 'mermaid', 'b.mmd')
            """,
            notebook_id,
        )

        await conn.execute(migration_sql)
        await conn.execute(migration_sql)

        await conn.execute(
            """
            INSERT INTO diagrams(notebook_id, title, diagram_type, format, content_path)
            VALUES($1, 'Chart', 'echarts', 'echarts_option', 'c.json')
            """,
            notebook_id,
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                """
                INSERT INTO diagrams(notebook_id, title, diagram_type, format, content_path)
                VALUES($1, 'Bad', 'bad', 'unknown', 'bad.txt')
                """,
                notebook_id,
            )

        await conn.execute("DROP TABLE diagrams")
        await conn.execute(
            """
            CREATE TABLE diagrams (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                diagram_type TEXT NOT NULL,
                format TEXT NOT NULL CHECK (format IN ('reactflow_json', 'mermaid', 'echarts_option')),
                content_path TEXT NOT NULL,
                document_ids UUID[] NOT NULL DEFAULT '{}',
                node_positions JSONB,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        await conn.execute(migration_sql)
        constraint_names = {
            row["conname"]
            for row in await conn.fetch(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'public.diagrams'::regclass
                  AND contype = 'c'
                """
            )
        }
        assert "ck_diagrams_format" in constraint_names
        assert "diagrams_format_check" not in constraint_names
    finally:
        if conn is not None:
            await conn.close()
        await admin.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1 AND pid <> pg_backend_pid()
            """,
            test_db,
        )
        await admin.execute(f'DROP DATABASE IF EXISTS "{test_db}"')
        await admin.close()


def test_init_postgres_declares_echarts_diagram_format():
    sql_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "init-postgres.sql"
    )

    sql = sql_path.read_text(encoding="utf-8")

    assert "CONSTRAINT ck_diagrams_format" in sql
    assert "format IN ('reactflow_json', 'mermaid', 'echarts_option')" in sql


def test_init_postgres_declares_default_qwen_pgvector_table():
    sql_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "init-postgres.sql"
    )

    sql = re.sub(r"/\*.*?\*/", "", sql_path.read_text(encoding="utf-8"), flags=re.S)

    assert "CREATE TABLE IF NOT EXISTS data_documents_qwen3_embedding (" in sql
    assert "embedding vector(1024)" in sql
    assert "documents_qwen3_embedding_idx_1" in sql
    assert "documents_qwen3_embedding_source_document_id_idx" in sql


def test_init_postgres_matches_live_message_column_order_for_image_ids():
    sql_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "init-postgres.sql"
    )

    sql = sql_path.read_text(encoding="utf-8")
    messages_block = sql.split("CREATE TABLE IF NOT EXISTS messages (", 1)[1].split(");", 1)[0]

    assert messages_block.index("created_at TIMESTAMP NOT NULL DEFAULT NOW()") < messages_block.index(
        "image_ids JSONB NOT NULL DEFAULT '[]'::jsonb"
    )


def test_runtime_schema_statements_backfill_pgvector_source_document_indexes():
    statements = "\n".join(get_runtime_schema_statements())

    assert "data_documents_qwen3_embedding" in statements
    assert "documents_qwen3_embedding_source_document_id_idx" in statements


def test_batch3_models_are_present_in_sqlalchemy_metadata():
    table_names = Base.metadata.tables.keys()

    assert "marks" in table_names
    assert "notes" in table_names
    assert "note_document_tags" in table_names
    assert "note_mark_refs" in table_names
    assert "diagrams" in table_names
    assert "video_summaries" in table_names


def test_batch8_migration_sql_exists_with_chat_images_table():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "migrations"
        / "batch8_chat_images.sql"
    )

    assert migration_path.exists()

    sql = migration_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS chat_images (" in sql
    assert "ALTER TABLE IF EXISTS messages" in sql
    assert "ADD COLUMN IF NOT EXISTS image_ids JSONB" in sql
    assert "idx_chat_images_session_id" in sql


def test_runtime_schema_statements_backfill_chat_image_tables():
    statements = "\n".join(get_runtime_schema_statements())

    assert "CREATE TABLE IF NOT EXISTS chat_images (" in statements
    assert "ADD COLUMN IF NOT EXISTS image_ids JSONB" in statements
    assert "CREATE INDEX IF NOT EXISTS idx_chat_images_session_id" in statements


def test_init_postgres_declares_chat_images_and_message_image_ids():
    sql_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "db"
        / "init-postgres.sql"
    )

    sql = sql_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS chat_images (" in sql
    assert "image_ids JSONB NOT NULL DEFAULT '[]'::jsonb" in sql
    assert "chat_images" in sql


def test_chat_image_models_are_present_in_sqlalchemy_metadata():
    table_names = Base.metadata.tables.keys()

    assert "chat_images" in table_names
    assert "image_ids" in Base.metadata.tables["messages"].columns
