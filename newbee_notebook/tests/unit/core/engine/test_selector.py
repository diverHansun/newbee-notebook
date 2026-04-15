"""Unit tests for the batch-2 engine public surface."""

import newbee_notebook.core.engine as engine
from newbee_notebook.core.session import SessionLockManager, SessionManager, SessionRunResult


def test_core_engine_exports_runtime_contracts_only():
    assert hasattr(engine, "AgentLoop")
    assert hasattr(engine, "AgentResult")
    assert hasattr(engine, "ModeConfigFactory")
    assert hasattr(engine, "LoopPolicy")
    assert hasattr(engine, "ToolPolicy")
    assert hasattr(engine, "SourcePolicy")
    assert hasattr(engine, "load_pgvector_index")
    assert hasattr(engine, "load_es_index")
    assert not hasattr(engine, "ModeSelector")
    assert not hasattr(engine, "parse_mode_from_input")
    assert not hasattr(engine, "get_mode_help")
    assert not hasattr(engine, "SessionManager")


def test_core_session_package_exports_request_scoped_runtime_manager():
    assert SessionManager is not None
    assert SessionLockManager is not None
    assert SessionRunResult is not None
