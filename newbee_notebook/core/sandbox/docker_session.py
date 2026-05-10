"""Notebook-scoped warm Docker container sessions."""

from __future__ import annotations

import hashlib
import asyncio
import contextlib
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from newbee_notebook.core.sandbox.contracts import (
    SandboxExecutionError,
    SandboxRequest,
    SandboxUnavailableError,
)
from newbee_notebook.core.sandbox.docker_command import DockerCommandBuilder
from newbee_notebook.core.sandbox.docker_config import DockerRunConfig
from newbee_notebook.core.sandbox.docker_executor import (
    DockerProcessResult,
    DockerProcessRunner,
    DockerSubprocessRunner,
)

_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


@dataclass(frozen=True)
class DockerSandboxSession:
    key: str
    container_name: str
    workspace_dir: Path
    run_dir: Path
    last_used_at: float


class DockerSandboxSessionRegistry:
    """Manage reusable Docker containers keyed by notebook/session scope."""

    def __init__(
        self,
        *,
        config: DockerRunConfig,
        runner: DockerProcessRunner | None = None,
        idle_ttl_seconds: float = 30 * 60,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._config = config
        self._runner = runner or DockerSubprocessRunner()
        self._idle_ttl_seconds = float(idle_ttl_seconds)
        self._clock = clock or time.monotonic
        self._builder = DockerCommandBuilder(config)
        self._sessions: dict[str, DockerSandboxSession] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._inflight: dict[str, int] = {}

    @property
    def idle_ttl_seconds(self) -> float:
        return self._idle_ttl_seconds

    def container_name_for(self, key: str) -> str:
        normalized = _normalize_key(key)
        prefix = self._config.container_prefix
        base = _SAFE_NAME_RE.sub("-", normalized).strip("-_.").lower() or "session"
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
        available = max(1, 63 - len(prefix) - len(digest) - 2)
        return f"{prefix}-{base[:available].strip('-_.') or 'session'}-{digest}"

    def get_active_session(self, key: str) -> DockerSandboxSession | None:
        return self._sessions.get(_normalize_key(key))

    async def execute(self, request: SandboxRequest) -> DockerProcessResult:
        key = _normalize_key(request.sandbox_session_key)
        if request.run_dir is None:
            raise SandboxExecutionError("sandbox_session_key requires run_dir")

        session = await self._get_or_create(request, key=key)
        exec_command = self._builder.build_session_exec(
            request,
            container_name=session.container_name,
            workspace_dir=session.workspace_dir,
            run_dir=session.run_dir,
        )
        self._mark_inflight(key, session)
        try:
            try:
                result = await self._runner.run(
                    exec_command.argv,
                    stdin=request.stdin,
                    timeout_seconds=min(request.timeout_seconds, self._config.timeout_seconds),
                    max_output_bytes=min(request.max_output_bytes, self._config.max_output_bytes),
                )
            except asyncio.CancelledError:
                await self.stop(key)
                raise
            if result.timed_out:
                await self.stop(key)
                return result
            self._sessions[key] = DockerSandboxSession(
                key=key,
                container_name=session.container_name,
                workspace_dir=session.workspace_dir,
                run_dir=session.run_dir,
                last_used_at=self._clock(),
            )
            return result
        finally:
            self._unmark_inflight(key)

    async def stop(self, key: str) -> None:
        normalized = _normalize_key(key)
        session = self._sessions.pop(normalized, None)
        if session is None:
            return
        command = self._builder.build_session_stop(container_name=session.container_name)
        await self._runner.run(
            command.argv,
            stdin=None,
            timeout_seconds=15,
            max_output_bytes=8_000,
        )

    async def stop_all(self) -> None:
        for key in list(self._sessions):
            await self.stop(key)

    async def reap_idle(self, *, now: float | None = None) -> list[str]:
        current = self._clock() if now is None else float(now)
        expired = [
            key
            for key, session in self._sessions.items()
            if self._inflight.get(key, 0) <= 0
            and current - session.last_used_at >= self._idle_ttl_seconds
        ]
        for key in expired:
            await self.stop(key)
        return expired

    async def _get_or_create(
        self,
        request: SandboxRequest,
        *,
        key: str,
    ) -> DockerSandboxSession:
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            return await self._get_or_create_locked(request, key=key)

    async def _get_or_create_locked(
        self,
        request: SandboxRequest,
        *,
        key: str,
    ) -> DockerSandboxSession:
        now = self._clock()
        existing = self._sessions.get(key)
        if existing is not None:
            return DockerSandboxSession(
                key=existing.key,
                container_name=existing.container_name,
                workspace_dir=existing.workspace_dir,
                run_dir=existing.run_dir,
                last_used_at=now,
            )

        container_name = self.container_name_for(key)
        start_command = self._builder.build_session_start(
            request,
            container_name=container_name,
            run_dir=request.run_dir or self._config.run_root / container_name,
        )
        try:
            start_result = await self._run_start_command(start_command.argv)
        except asyncio.CancelledError:
            await self._cleanup_container(container_name)
            raise
        if _looks_like_container_name_conflict(start_result):
            await self._cleanup_container(container_name)
            try:
                start_result = await self._run_start_command(start_command.argv)
            except asyncio.CancelledError:
                await self._cleanup_container(container_name)
                raise
        if start_result.exit_code != 0:
            await self._cleanup_container(container_name)
            if _looks_like_docker_unavailable(start_result):
                raise SandboxUnavailableError(
                    start_result.stderr.strip()
                    or start_result.stdout.strip()
                    or "Docker is unavailable"
                )
            raise SandboxExecutionError(
                start_result.stderr.strip()
                or start_result.stdout.strip()
                or f"Failed to start Docker sandbox session: {container_name}"
            )
        session = DockerSandboxSession(
            key=key,
            container_name=container_name,
            workspace_dir=start_command.workspace_dir,
            run_dir=start_command.run_dir,
            last_used_at=now,
        )
        self._sessions[key] = session
        return session

    async def _run_start_command(self, argv: tuple[str, ...]) -> DockerProcessResult:
        return await self._runner.run(
            argv,
            stdin=None,
            timeout_seconds=min(15, self._config.timeout_seconds),
            max_output_bytes=8_000,
        )

    async def _cleanup_container(self, container_name: str) -> None:
        with contextlib.suppress(Exception):
            await self._runner.cleanup(
                docker_bin=self._config.docker_bin,
                container_name=container_name,
            )

    def _mark_inflight(self, key: str, session: DockerSandboxSession) -> None:
        self._inflight[key] = self._inflight.get(key, 0) + 1
        self._sessions[key] = DockerSandboxSession(
            key=session.key,
            container_name=session.container_name,
            workspace_dir=session.workspace_dir,
            run_dir=session.run_dir,
            last_used_at=self._clock(),
        )

    def _unmark_inflight(self, key: str) -> None:
        count = self._inflight.get(key, 0) - 1
        if count > 0:
            self._inflight[key] = count
            return
        self._inflight.pop(key, None)


def _normalize_key(key: str | None) -> str:
    normalized = str(key or "").strip()
    if not normalized:
        raise SandboxExecutionError("sandbox_session_key is required")
    return normalized


def _looks_like_docker_unavailable(result: DockerProcessResult) -> bool:
    if result.exit_code != 125:
        return False
    stderr = result.stderr.casefold()
    return (
        "cannot connect to the docker daemon" in stderr
        or "error during connect" in stderr
        or "is the docker daemon running" in stderr
    )


def _looks_like_container_name_conflict(result: DockerProcessResult) -> bool:
    if result.exit_code != 125:
        return False
    output = f"{result.stderr}\n{result.stdout}".casefold()
    return "container name" in output and "already in use" in output
