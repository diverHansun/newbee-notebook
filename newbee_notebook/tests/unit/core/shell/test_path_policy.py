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


def test_path_policy_maps_container_workspace_and_work_paths(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work_dir = tmp_path / "work"
    workspace.mkdir()
    work_dir.mkdir()
    policy = PathPolicy(
        ShellEnvironment(
            cwd=workspace,
            workspace_roots=(workspace,),
            run_dir=work_dir,
            allow_workspace_write=False,
        )
    )

    assert policy.resolve_read_path("/workspace/brief.md") == (workspace / "brief.md").resolve()
    assert policy.resolve_read_path("/work/out.md") == (work_dir / "out.md").resolve()

    with pytest.raises(PathAccessError) as exc_info:
        policy.resolve_write_path("/workspace/brief.md")
    assert exc_info.value.code == "outside_workspace"
    assert policy.resolve_write_path("/work/out.md") == (work_dir / "out.md").resolve()


def test_path_policy_requires_work_alias_for_notebook_work_writes(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work_dir = workspace / ".tmp" / "sandbox-work" / "notebooks" / "nb1" / "work"
    workspace.mkdir()
    work_dir.mkdir(parents=True)
    policy = PathPolicy(
        ShellEnvironment(
            cwd=workspace,
            workspace_roots=(workspace,),
            run_dir=work_dir,
            allow_workspace_write=False,
        )
    )

    with pytest.raises(PathAccessError) as workspace_alias:
        policy.resolve_write_path(
            "/workspace/.tmp/sandbox-work/notebooks/nb1/work/out.md"
        )
    with pytest.raises(PathAccessError) as relative_alias:
        policy.resolve_write_path(".tmp/sandbox-work/notebooks/nb1/work/out.md")
    with pytest.raises(PathAccessError) as absolute_alias:
        policy.resolve_write_path(work_dir / "out.md")

    assert workspace_alias.value.code == "outside_workspace"
    assert relative_alias.value.code == "outside_workspace"
    assert absolute_alias.value.code == "outside_workspace"
    assert policy.resolve_write_path("/work/out.md") == (work_dir / "out.md").resolve()
