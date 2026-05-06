from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.shell import PathAccessError, PathPolicy, ShellEnvironment

pytestmark = pytest.mark.unit


def test_path_policy_resolves_relative_paths_inside_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes" / "brief.md"
    target.parent.mkdir()
    target.write_text("hello", encoding="utf-8")
    policy = PathPolicy(ShellEnvironment(cwd=workspace, workspace_roots=(workspace,)))

    resolved = policy.resolve_read_path("notes/brief.md")

    assert resolved == target.resolve()


def test_path_policy_rejects_paths_outside_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside.txt"
    workspace.mkdir()
    outside.write_text("secret", encoding="utf-8")
    policy = PathPolicy(ShellEnvironment(cwd=workspace, workspace_roots=(workspace,)))

    with pytest.raises(PathAccessError) as exc_info:
        policy.resolve_read_path(str(outside))

    assert exc_info.value.code == "outside_workspace"


def test_path_policy_rejects_sensitive_file_names(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    secret = workspace / ".env"
    secret.write_text("API_KEY=secret", encoding="utf-8")
    policy = PathPolicy(ShellEnvironment(cwd=workspace, workspace_roots=(workspace,)))

    with pytest.raises(PathAccessError) as exc_info:
        policy.resolve_read_path(".env")

    assert exc_info.value.code == "sensitive_file"


def test_path_policy_allows_write_to_new_file_when_parent_is_inside_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    policy = PathPolicy(ShellEnvironment(cwd=workspace, workspace_roots=(workspace,)))

    resolved = policy.resolve_write_path("generated/out.md")

    assert resolved == (workspace / "generated" / "out.md").resolve()
