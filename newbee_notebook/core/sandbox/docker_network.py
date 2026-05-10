"""Docker bridge network management for sandbox containers."""

from __future__ import annotations

from typing import Any, Protocol

from newbee_notebook.core.sandbox.contracts import (
    SandboxExecutionError,
    SandboxUnavailableError,
)
from newbee_notebook.core.sandbox.docker_config import DockerRunConfig


class DockerNetworkRunner(Protocol):
    async def run(
        self,
        argv: tuple[str, ...],
        *,
        stdin: str | None,
        timeout_seconds: float,
        max_output_bytes: int,
    ) -> Any:
        """Run a Docker CLI command and return an object with process fields."""


class DockerSandboxNetworkManager:
    """Ensure the dedicated outbound sandbox network exists."""

    def __init__(self, config: DockerRunConfig, *, runner: DockerNetworkRunner) -> None:
        self._config = config
        self._runner = runner
        self._ready = False

    @property
    def network_name(self) -> str:
        return self._config.network_name

    async def ensure_exists(self) -> None:
        if self._ready:
            return

        inspect_result = await self._runner.run(
            (
                self._config.docker_bin,
                "network",
                "inspect",
                self._config.network_name,
            ),
            stdin=None,
            timeout_seconds=10,
            max_output_bytes=8_000,
        )
        if _exit_code(inspect_result) == 0:
            self._ready = True
            return
        if _looks_like_docker_unavailable(inspect_result):
            raise SandboxUnavailableError(_message(inspect_result) or "Docker is unavailable")

        create_result = await self._runner.run(
            (
                self._config.docker_bin,
                "network",
                "create",
                "--driver",
                "bridge",
                "--opt",
                "com.docker.network.bridge.enable_icc=false",
                "--label",
                "com.newbee_notebook.role=sandbox",
                self._config.network_name,
            ),
            stdin=None,
            timeout_seconds=10,
            max_output_bytes=8_000,
        )
        if _exit_code(create_result) == 0 or "already exists" in _message(create_result).casefold():
            self._ready = True
            return
        if _looks_like_docker_unavailable(create_result):
            raise SandboxUnavailableError(_message(create_result) or "Docker is unavailable")
        raise SandboxExecutionError(
            _message(create_result)
            or f"failed to create Docker sandbox network: {self._config.network_name}"
        )


def _exit_code(result: Any) -> int | None:
    return getattr(result, "exit_code", None)


def _message(result: Any) -> str:
    return "\n".join(
        part
        for part in [
            str(getattr(result, "stderr", "") or "").strip(),
            str(getattr(result, "stdout", "") or "").strip(),
        ]
        if part
    )


def _looks_like_docker_unavailable(result: Any) -> bool:
    if _exit_code(result) != 125:
        return False
    output = _message(result).casefold()
    return (
        "cannot connect to the docker daemon" in output
        or "error during connect" in output
        or "is the docker daemon running" in output
    )
