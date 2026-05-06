"""Path resolution and access checks shared by filesystem tools."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from newbee_notebook.core.shell.environment import ShellEnvironment


SENSITIVE_NAMES = {
    ".env",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}
SENSITIVE_GLOBS = {
    ".env.*",
    "*.key",
    "*.p12",
    "*.pem",
    "*.pfx",
}
SENSITIVE_SUBSTRINGS = {
    "credential",
    "secret",
    "token",
}


class PathAccessError(Exception):
    """Raised when a path cannot be accessed under the active shell policy."""

    def __init__(self, code: str, message: str, path: Path | None = None):
        super().__init__(message)
        self.code = code
        self.path = path


class PathPolicy:
    def __init__(self, environment: ShellEnvironment):
        self.environment = environment

    def resolve_read_path(self, path: Path | str) -> Path:
        resolved = self._resolve_user_path(path)
        self._ensure_inside_any_root(resolved, self.environment.read_roots)
        self._ensure_not_sensitive(resolved)
        return resolved

    def resolve_write_path(self, path: Path | str) -> Path:
        resolved = self._resolve_user_path(path)
        self._ensure_not_sensitive(resolved)
        self._ensure_inside_any_root(resolved.parent, self.environment.write_roots)
        return resolved

    def is_sensitive_path(self, path: Path | str) -> bool:
        resolved = Path(path)
        return self._is_sensitive(resolved)

    def relative_to_cwd(self, path: Path | str) -> str:
        resolved = Path(path).resolve(strict=False)
        try:
            return resolved.relative_to(self.environment.cwd).as_posix()
        except ValueError:
            return str(resolved)

    def _resolve_user_path(self, path: Path | str) -> Path:
        raw_path = Path(path).expanduser()
        if not raw_path.is_absolute():
            raw_path = self.environment.cwd / raw_path
        return raw_path.resolve(strict=False)

    def _ensure_inside_any_root(self, path: Path, roots: tuple[Path, ...]) -> None:
        if any(_is_relative_to(path, root) for root in roots):
            return
        raise PathAccessError(
            "outside_workspace",
            f"Path is outside the allowed workspace roots: {path}",
            path,
        )

    def _ensure_not_sensitive(self, path: Path) -> None:
        if self._is_sensitive(path):
            raise PathAccessError(
                "sensitive_file",
                f"Path is blocked by sensitive-file rules: {path}",
                path,
            )

    def _is_sensitive(self, path: Path) -> bool:
        parts = [part.casefold() for part in path.parts]
        name = path.name.casefold()
        if name in SENSITIVE_NAMES:
            return True
        if any(fnmatch.fnmatch(name, pattern) for pattern in SENSITIVE_GLOBS):
            return True
        return any(substring in part for part in parts for substring in SENSITIVE_SUBSTRINGS)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        common = os.path.commonpath([str(path), str(root)])
    except ValueError:
        return False
    return common.casefold() == str(root).casefold()
