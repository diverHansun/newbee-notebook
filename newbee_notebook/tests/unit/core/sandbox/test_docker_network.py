from __future__ import annotations

import pytest

from newbee_notebook.core.sandbox.docker_config import DockerRunConfig
from newbee_notebook.core.sandbox.docker_executor import DockerProcessResult
from newbee_notebook.core.sandbox.docker_network import DockerSandboxNetworkManager

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend():
    return "asyncio"


class RecordingRunner:
    def __init__(self, inspect_result: DockerProcessResult):
        self.inspect_result = inspect_result
        self.runs: list[tuple[str, ...]] = []

    async def run(
        self,
        argv: tuple[str, ...],
        *,
        stdin: str | None,
        timeout_seconds: float,
        max_output_bytes: int,
    ) -> DockerProcessResult:
        del stdin, timeout_seconds, max_output_bytes
        self.runs.append(argv)
        if argv[:3] == ("docker", "network", "inspect"):
            return self.inspect_result
        return DockerProcessResult(exit_code=0, stdout="created\n")


VALID_NETWORK_JSON = """
[
  {
    "Name": "newbee_skill_net",
    "Driver": "bridge",
    "Internal": false,
    "Labels": {"com.newbee_notebook.role": "sandbox"},
    "Options": {"com.docker.network.bridge.enable_icc": "false"}
  }
]
"""


@pytest.mark.parametrize("network_name", ["none", "host", "bridge", "newbee_notebook_network"])
def test_docker_run_config_rejects_unsafe_network_names(network_name: str):
    with pytest.raises(ValueError, match="network_name"):
        DockerRunConfig(network_name=network_name)


@pytest.mark.anyio
async def test_network_manager_creates_isolated_bridge_when_missing():
    runner = RecordingRunner(DockerProcessResult(exit_code=1, stderr="not found"))
    manager = DockerSandboxNetworkManager(
        DockerRunConfig(network_name="newbee_skill_net"),
        runner=runner,
    )

    await manager.ensure_exists()

    assert runner.runs == [
        ("docker", "network", "inspect", "newbee_skill_net"),
        (
            "docker",
            "network",
            "create",
            "--driver",
            "bridge",
            "--opt",
            "com.docker.network.bridge.enable_icc=false",
            "--label",
            "com.newbee_notebook.role=sandbox",
            "newbee_skill_net",
        ),
    ]


@pytest.mark.anyio
async def test_network_manager_reuses_existing_network():
    runner = RecordingRunner(DockerProcessResult(exit_code=0, stdout=VALID_NETWORK_JSON))
    manager = DockerSandboxNetworkManager(
        DockerRunConfig(network_name="newbee_skill_net"),
        runner=runner,
    )

    await manager.ensure_exists()
    await manager.ensure_exists()

    assert runner.runs == [("docker", "network", "inspect", "newbee_skill_net")]


@pytest.mark.anyio
async def test_network_manager_rejects_existing_network_with_wrong_shape():
    runner = RecordingRunner(
        DockerProcessResult(
            exit_code=0,
            stdout="""
            [
              {
                "Name": "newbee_skill_net",
                "Driver": "bridge",
                "Internal": false,
                "Labels": {},
                "Options": {}
              }
            ]
            """,
        )
    )
    manager = DockerSandboxNetworkManager(
        DockerRunConfig(network_name="newbee_skill_net"),
        runner=runner,
    )

    with pytest.raises(Exception, match="not a managed sandbox network"):
        await manager.ensure_exists()
