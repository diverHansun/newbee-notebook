from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_runtime_sandbox_executor_singleton_uses_docker_backend(monkeypatch, tmp_path):
    from newbee_notebook.api import dependencies
    from newbee_notebook.core.sandbox.docker_executor import DockerSandboxExecutor

    monkeypatch.setenv("NEWBEE_SANDBOX_BACKEND", "docker")
    monkeypatch.setenv("NEWBEE_SANDBOX_IMAGE", "sandbox-image:latest")
    monkeypatch.setenv("NEWBEE_SANDBOX_RUN_ROOT", str(tmp_path / "runs"))
    dependencies._runtime_sandbox_executor = None
    dependencies._runtime_docker_session_registry = None

    try:
        executor = dependencies.get_runtime_sandbox_executor_singleton()
    finally:
        dependencies._runtime_sandbox_executor = None
        dependencies._runtime_docker_session_registry = None

    assert isinstance(executor, DockerSandboxExecutor)
    assert executor.config.image == "sandbox-image:latest"
    assert executor.config.run_root == (tmp_path / "runs").resolve()


def test_runtime_sandbox_executor_allows_configured_notebook_work_root(
    monkeypatch,
    tmp_path,
):
    from newbee_notebook.api import dependencies

    monkeypatch.setenv("NEWBEE_SANDBOX_BACKEND", "docker")
    monkeypatch.setenv("NEWBEE_SANDBOX_RUN_ROOT", str(tmp_path / "runs"))
    monkeypatch.setenv("NEWBEE_SANDBOX_WORK_ROOT", str(tmp_path / "sandbox-work"))
    dependencies._runtime_sandbox_executor = None
    dependencies._runtime_docker_session_registry = None

    try:
        executor = dependencies.get_runtime_sandbox_executor_singleton()
    finally:
        dependencies._runtime_sandbox_executor = None
        dependencies._runtime_docker_session_registry = None

    assert executor is not None
    assert (tmp_path / "sandbox-work").resolve() in executor.config.additional_run_roots


def test_runtime_docker_session_registry_uses_idle_ttl(monkeypatch, tmp_path):
    from newbee_notebook.api import dependencies

    monkeypatch.setenv("NEWBEE_SANDBOX_SESSION_IDLE_TTL_SECONDS", "42")
    dependencies._runtime_docker_session_registry = None

    try:
        registry = dependencies.get_runtime_docker_session_registry_singleton(
            config=dependencies.build_docker_run_config_from_env(base_dir=tmp_path)
        )
    finally:
        dependencies._runtime_docker_session_registry = None

    assert registry.idle_ttl_seconds == 42


@pytest.mark.anyio
async def test_reap_runtime_docker_sessions_calls_registry(monkeypatch):
    from newbee_notebook.api import dependencies

    class FakeRegistry:
        def __init__(self):
            self.reaped = 0

        async def reap_idle(self):
            self.reaped += 1
            return ["nb1"]

    fake = FakeRegistry()
    dependencies._runtime_docker_session_registry = fake

    try:
        result = await dependencies.reap_runtime_docker_sessions_once()
    finally:
        dependencies._runtime_docker_session_registry = None

    assert result == ["nb1"]
    assert fake.reaped == 1


@pytest.mark.anyio
async def test_stop_runtime_docker_sessions_calls_registry(monkeypatch):
    from newbee_notebook.api import dependencies

    class FakeRegistry:
        def __init__(self):
            self.stopped = False

        async def stop_all(self):
            self.stopped = True

    fake = FakeRegistry()
    dependencies._runtime_docker_session_registry = fake

    try:
        await dependencies.stop_runtime_docker_sessions()
    finally:
        dependencies._runtime_docker_session_registry = None

    assert fake.stopped is True


def test_runtime_sandbox_executor_singleton_can_be_disabled(monkeypatch):
    from newbee_notebook.api import dependencies

    monkeypatch.setenv("NEWBEE_SANDBOX_BACKEND", "none")
    dependencies._runtime_sandbox_executor = None

    try:
        assert dependencies.get_runtime_sandbox_executor_singleton() is None
    finally:
        dependencies._runtime_sandbox_executor = None


def test_runtime_notebook_sandbox_workspace_singleton_uses_configured_root(
    monkeypatch,
    tmp_path,
):
    from newbee_notebook.api import dependencies
    from newbee_notebook.core.sandbox import NotebookSandboxWorkspace

    monkeypatch.setenv("NEWBEE_SANDBOX_WORK_ROOT", str(tmp_path / "sandbox-work"))
    dependencies._runtime_notebook_sandbox_workspace = None

    try:
        workspace = dependencies.get_runtime_notebook_sandbox_workspace_singleton()
    finally:
        dependencies._runtime_notebook_sandbox_workspace = None

    assert isinstance(workspace, NotebookSandboxWorkspace)
    assert workspace.root == (tmp_path / "sandbox-work").resolve()


@pytest.mark.anyio
async def test_runtime_builtin_tool_provider_injects_sandbox_executor(monkeypatch):
    from newbee_notebook.api import dependencies
    from newbee_notebook.core.sandbox import SandboxResult

    class FakeSandboxExecutor:
        def __init__(self):
            self.calls = 0

        async def execute(self, request):
            del request
            self.calls += 1
            return SandboxResult(exit_code=0, stdout="ok\n")

    fake = FakeSandboxExecutor()
    monkeypatch.setattr(
        dependencies,
        "get_runtime_sandbox_executor_singleton",
        lambda: fake,
    )
    dependencies._runtime_builtin_tool_provider = None

    try:
        provider = dependencies.get_runtime_builtin_tool_provider_singleton()
        shell_tool = next(tool for tool in provider.get_tools("agent") if tool.name == "shell")
        result = await shell_tool.execute({"command": "echo ok"})
    finally:
        dependencies._runtime_builtin_tool_provider = None

    assert result.error is None
    assert "ok" in result.content
    assert fake.calls == 1
