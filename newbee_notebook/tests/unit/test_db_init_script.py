from pathlib import Path


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
