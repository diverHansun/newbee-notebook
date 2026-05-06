"""Runtime environment visible to shell-backed tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


def _resolve_path(value: Path | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _resolve_roots(values: tuple[Path | str, ...] | list[Path | str]) -> tuple[Path, ...]:
    roots: list[Path] = []
    seen: set[str] = set()
    for value in values:
        path = _resolve_path(value)
        key = str(path).casefold()
        if key not in seen:
            roots.append(path)
            seen.add(key)
    return tuple(roots)


@dataclass(frozen=True)
class ShellEnvironment:
    """Describes the filesystem view for one family of tool calls."""

    cwd: Path | str
    workspace_roots: tuple[Path | str, ...] = ()
    additional_roots: tuple[Path | str, ...] = ()
    skill_roots: tuple[Path | str, ...] = ()
    run_dir: Path | str | None = None
    sandbox_session_key: str | None = None
    allow_workspace_write: bool = True
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    max_output_bytes: int = 120_000

    def __post_init__(self) -> None:
        cwd = _resolve_path(self.cwd)
        workspace_roots = self.workspace_roots or (cwd,)
        object.__setattr__(self, "cwd", cwd)
        object.__setattr__(self, "workspace_roots", _resolve_roots(tuple(workspace_roots)))
        object.__setattr__(self, "additional_roots", _resolve_roots(tuple(self.additional_roots)))
        object.__setattr__(self, "skill_roots", _resolve_roots(tuple(self.skill_roots)))
        object.__setattr__(
            self,
            "run_dir",
            _resolve_path(self.run_dir) if self.run_dir is not None else None,
        )
        key = str(self.sandbox_session_key or "").strip()
        object.__setattr__(self, "sandbox_session_key", key or None)
        object.__setattr__(self, "env", dict(self.env))

    @property
    def read_roots(self) -> tuple[Path, ...]:
        roots = [*self.workspace_roots, *self.additional_roots, *self.skill_roots]
        if self.run_dir is not None:
            roots.append(self.run_dir)
        return tuple(roots)

    @property
    def write_roots(self) -> tuple[Path, ...]:
        roots = [*self.workspace_roots] if self.allow_workspace_write else []
        if self.run_dir is not None:
            roots.append(self.run_dir)
        return tuple(roots)


def build_default_shell_environment(cwd: Path | str | None = None) -> ShellEnvironment:
    """Build the default host-side environment until sandbox-backed execution exists."""

    base = _resolve_path(cwd or Path.cwd())
    return ShellEnvironment(cwd=base, workspace_roots=(base,))
