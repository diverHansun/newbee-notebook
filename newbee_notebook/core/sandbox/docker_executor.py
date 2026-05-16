"""Docker-backed sandbox executor."""

from __future__ import annotations

import asyncio
import contextlib
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from newbee_notebook.core.sandbox.contracts import (
    SandboxExecutionError,
    SandboxRequest,
    SandboxResult,
    SandboxUnavailableError,
)
from newbee_notebook.core.sandbox.docker_command import DockerCommandBuilder
from newbee_notebook.core.sandbox.docker_config import DockerRunConfig
from newbee_notebook.core.sandbox.docker_network import DockerSandboxNetworkManager


@dataclass(frozen=True)
class DockerProcessResult:
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    truncated: bool = False
    error_code: str | None = None


@dataclass
class _SharedOutputBudget:
    remaining: int
    truncated: bool = False


class LimitedOutputBuffer:
    """Collect decoded output up to a fixed byte budget."""

    def __init__(
        self,
        max_bytes: int,
        *,
        budget: _SharedOutputBudget | None = None,
    ) -> None:
        self._budget = budget or _SharedOutputBudget(max_bytes)
        self._chunks: list[bytes] = []
        self._truncated = False

    def append(self, data: bytes) -> None:
        if not data:
            return
        if self._budget.remaining <= 0:
            self._truncated = True
            self._budget.truncated = True
            return
        keep = min(len(data), self._budget.remaining)
        if keep:
            self._chunks.append(data[:keep])
            self._budget.remaining -= keep
        if keep < len(data):
            self._truncated = True
            self._budget.truncated = True

    @property
    def text(self) -> str:
        return b"".join(self._chunks).decode("utf-8", errors="replace")

    @property
    def truncated(self) -> bool:
        return self._truncated or self._budget.truncated


class DockerProcessRunner(Protocol):
    async def run(
        self,
        argv: tuple[str, ...],
        *,
        stdin: str | None,
        timeout_seconds: float,
        max_output_bytes: int,
    ) -> DockerProcessResult:
        """Run a Docker CLI command and return bounded output."""

    async def cleanup(self, *, docker_bin: str, container_name: str) -> None:
        """Best-effort cleanup for a timed-out container."""


class DockerSubprocessRunner:
    async def run(
        self,
        argv: tuple[str, ...],
        *,
        stdin: str | None,
        timeout_seconds: float,
        max_output_bytes: int,
    ) -> DockerProcessResult:
        stdin_mode = (
            asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=stdin_mode,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except NotImplementedError:
            return await asyncio.to_thread(
                _run_sync_subprocess,
                argv,
                stdin=stdin,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
            )
        except FileNotFoundError as exc:
            raise SandboxUnavailableError(f"Docker CLI not found: {argv[0]}") from exc
        except OSError as exc:
            raise SandboxExecutionError(f"Failed to start Docker CLI: {exc}") from exc

        budget = _SharedOutputBudget(max_output_bytes)
        stdout_buffer = LimitedOutputBuffer(max_output_bytes, budget=budget)
        stderr_buffer = LimitedOutputBuffer(max_output_bytes, budget=budget)
        stdout_task = asyncio.create_task(_read_stream(process.stdout, stdout_buffer))
        stderr_task = asyncio.create_task(_read_stream(process.stderr, stderr_buffer))

        if stdin is not None and process.stdin is not None:
            process.stdin.write(stdin.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()

        try:
            exit_code = await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
            await asyncio.gather(stdout_task, stderr_task)
            return DockerProcessResult(
                exit_code=exit_code,
                stdout=stdout_buffer.text,
                stderr=stderr_buffer.text,
                truncated=budget.truncated,
            )
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(process.wait(), timeout=5)
            for task in (stdout_task, stderr_task):
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.gather(stdout_task, stderr_task)
            return DockerProcessResult(
                exit_code=None,
                stdout=stdout_buffer.text,
                stderr=stderr_buffer.text,
                timed_out=True,
                truncated=budget.truncated,
                error_code="timeout",
            )
        except asyncio.CancelledError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(process.wait(), timeout=5)
            for task in (stdout_task, stderr_task):
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.gather(stdout_task, stderr_task)
            raise

    async def cleanup(self, *, docker_bin: str, container_name: str) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                docker_bin,
                "rm",
                "-f",
                container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(process.wait(), timeout=10)
        except NotImplementedError:
            await asyncio.to_thread(
                _cleanup_sync_subprocess,
                docker_bin=docker_bin,
                container_name=container_name,
            )
        except Exception:
            pass


class DockerSandboxExecutor:
    """Execute sandbox requests with one locked-down Docker container per call."""

    def __init__(
        self,
        *,
        config: DockerRunConfig | None = None,
        runner: DockerProcessRunner | None = None,
        name_factory: Callable[[], str] | None = None,
        session_registry: Any | None = None,
    ) -> None:
        self._config = config or DockerRunConfig()
        self._runner = runner or DockerSubprocessRunner()
        self._name_factory = name_factory
        self._session_registry = session_registry
        self._builder = DockerCommandBuilder(self._config)
        self._network_manager = DockerSandboxNetworkManager(
            self._config,
            runner=self._runner,
        )

    @property
    def config(self) -> DockerRunConfig:
        return self._config

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        if request.sandbox_session_key and self._session_registry is not None:
            process_result = await self._session_registry.execute(request)
            if _looks_like_docker_unavailable(process_result):
                raise SandboxUnavailableError(process_result.stderr.strip() or "Docker is unavailable")
            return _sandbox_result_from_process(process_result)

        if request.network_enabled:
            await self._network_manager.ensure_exists()

        container_name = self._next_container_name()
        run_dir = Path(request.run_dir) if request.run_dir is not None else self._config.run_root / container_name
        command = self._builder.build(
            request,
            container_name=container_name,
            run_dir=run_dir,
        )

        try:
            process_result = await self._runner.run(
                command.argv,
                stdin=request.stdin,
                timeout_seconds=min(request.timeout_seconds, self._config.timeout_seconds),
                max_output_bytes=min(request.max_output_bytes, self._config.max_output_bytes),
            )
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await self._runner.cleanup(
                    docker_bin=self._config.docker_bin,
                    container_name=command.container_name,
                )
            raise
        if process_result.timed_out:
            await self._runner.cleanup(
                docker_bin=self._config.docker_bin,
                container_name=command.container_name,
            )
        if _looks_like_docker_unavailable(process_result):
            raise SandboxUnavailableError(process_result.stderr.strip() or "Docker is unavailable")

        return _sandbox_result_from_process(process_result)

    def _next_container_name(self) -> str:
        if self._name_factory is not None:
            return self._name_factory()
        return f"{self._config.container_prefix}-{uuid.uuid4().hex}"


async def _read_stream(
    stream: asyncio.StreamReader | None,
    buffer: LimitedOutputBuffer,
) -> None:
    if stream is None:
        return
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            return
        buffer.append(chunk)


def _looks_like_docker_unavailable(result: DockerProcessResult) -> bool:
    if result.exit_code != 125:
        return False
    stderr = result.stderr.casefold()
    return (
        "cannot connect to the docker daemon" in stderr
        or "error during connect" in stderr
        or "is the docker daemon running" in stderr
    )


def _run_sync_subprocess(
    argv: tuple[str, ...],
    *,
    stdin: str | None,
    timeout_seconds: float,
    max_output_bytes: int,
) -> DockerProcessResult:
    input_bytes = stdin.encode("utf-8") if stdin is not None else None
    try:
        completed = subprocess.run(
            argv,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SandboxUnavailableError(f"Docker CLI not found: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, truncated = _bounded_output_text(
            exc.stdout,
            exc.stderr,
            max_output_bytes=max_output_bytes,
        )
        return DockerProcessResult(
            exit_code=None,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
            truncated=truncated,
            error_code="timeout",
        )
    except OSError as exc:
        raise SandboxExecutionError(f"Failed to start Docker CLI: {exc}") from exc

    stdout, stderr, truncated = _bounded_output_text(
        completed.stdout,
        completed.stderr,
        max_output_bytes=max_output_bytes,
    )
    return DockerProcessResult(
        exit_code=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        truncated=truncated,
    )


def _cleanup_sync_subprocess(*, docker_bin: str, container_name: str) -> None:
    with contextlib.suppress(Exception):
        subprocess.run(
            (docker_bin, "rm", "-f", container_name),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )


def _bounded_output_text(
    stdout: bytes | str | None,
    stderr: bytes | str | None,
    *,
    max_output_bytes: int,
) -> tuple[str, str, bool]:
    budget = _SharedOutputBudget(max_output_bytes)
    stdout_buffer = LimitedOutputBuffer(max_output_bytes, budget=budget)
    stderr_buffer = LimitedOutputBuffer(max_output_bytes, budget=budget)
    stdout_buffer.append(_output_bytes(stdout))
    stderr_buffer.append(_output_bytes(stderr))
    return stdout_buffer.text, stderr_buffer.text, budget.truncated


def _output_bytes(value: bytes | str | None) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8", errors="replace")


def _sandbox_result_from_process(process_result: DockerProcessResult) -> SandboxResult:
    return SandboxResult(
        exit_code=process_result.exit_code,
        stdout=process_result.stdout,
        stderr=process_result.stderr,
        timed_out=process_result.timed_out,
        truncated=process_result.truncated,
        error_code=process_result.error_code
        or ("timeout" if process_result.timed_out else None),
    )
