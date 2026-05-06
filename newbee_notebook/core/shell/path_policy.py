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
        if self._requires_work_alias_for_writes(path, resolved):
            raise PathAccessError(
                "outside_workspace",
                "Notebook work directory writes must use the /work path alias.",
                resolved,
            )
        self._ensure_not_sensitive(resolved)
        self._ensure_inside_any_root(resolved.parent, self.environment.write_roots)
        return resolved

    def is_sensitive_path(self, path: Path | str) -> bool:
        resolved = Path(path)
        return self._is_sensitive(resolved)

    def relative_to_cwd(self, path: Path | str) -> str:
        resolved = Path(path).resolve(strict=False)
        if self.environment.run_dir is not None:
            try:
                suffix = resolved.relative_to(self.environment.run_dir).as_posix()
                return f"/work/{suffix}" if suffix else "/work"
            except ValueError:
                pass
        try:
            return resolved.relative_to(self.environment.cwd).as_posix()
        except ValueError:
            return str(resolved)

    def _resolve_user_path(self, path: Path | str) -> Path:
        mapped = self._map_container_path(str(path))
        if mapped is not None:
            return mapped.resolve(strict=False)
        raw_path = Path(path).expanduser()
        if not raw_path.is_absolute():
            raw_path = self.environment.cwd / raw_path
        return raw_path.resolve(strict=False)

    def _map_container_path(self, path: str) -> Path | None:
        normalized = str(path or "").strip().replace("\\", "/")
        if normalized == "/workspace":
            return self.environment.cwd
        if normalized.startswith("/workspace/"):
            return self.environment.cwd / normalized[len("/workspace/") :]
        if self.environment.run_dir is None:
            return None
        if normalized == "/work":
            return self.environment.run_dir
        if normalized.startswith("/work/"):
            return self.environment.run_dir / normalized[len("/work/") :]
        return None

    def _requires_work_alias_for_writes(self, path: Path | str, resolved: Path) -> bool:
        if self.environment.allow_workspace_write or self.environment.run_dir is None:
            return False
        if not _is_relative_to(resolved, self.environment.run_dir):
            return False
        normalized = str(path or "").strip().replace("\\", "/")
        return not (normalized == "/work" or normalized.startswith("/work/"))

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
