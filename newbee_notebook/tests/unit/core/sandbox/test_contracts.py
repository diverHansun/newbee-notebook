from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.sandbox import (
    SandboxRequest,
    SandboxUnavailableError,
    UnavailableSandboxExecutor,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_sandbox_request_requires_argv_sequence(tmp_path: Path):
    with pytest.raises(ValueError, match="argv"):
        SandboxRequest(argv=(), cwd=tmp_path)

    with pytest.raises(ValueError, match="argv"):
        SandboxRequest(argv="echo hi", cwd=tmp_path)  # type: ignore[arg-type]


def test_sandbox_request_normalizes_execution_limits(tmp_path: Path):
    request = SandboxRequest(
        argv=["bash", "-lc", "echo hi"],
        cwd=tmp_path,
        env={"A": 1},
        timeout_seconds=5,
        max_output_bytes=512,
        network_enabled=False,
    )

    assert request.argv == ("bash", "-lc", "echo hi")
    assert request.cwd == tmp_path.resolve()
    assert request.env == {"A": "1"}
    assert request.timeout_seconds == 5
    assert request.max_output_bytes == 512
    assert request.network_enabled is False


def test_sandbox_request_enables_network_by_default(tmp_path: Path):
    request = SandboxRequest(argv=("bash", "-lc", "echo hi"), cwd=tmp_path)

    assert request.network_enabled is True


@pytest.mark.anyio
async def test_unavailable_sandbox_executor_fails_closed(tmp_path: Path):
    executor = UnavailableSandboxExecutor()

    with pytest.raises(SandboxUnavailableError):
        await executor.execute(SandboxRequest(argv=("bash", "-lc", "echo hi"), cwd=tmp_path))
