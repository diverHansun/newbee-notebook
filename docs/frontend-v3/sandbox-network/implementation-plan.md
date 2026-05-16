# Sandbox Network Implementation Notes

## Goal

Allow agent shell commands to reach the public internet by default, while keeping sandbox containers off the Newbee Docker Compose application network.

## Meaning Of "Compose Sibling"

`compose sibling` means a service container on the same Docker Compose application network as the app stack, for example `postgres`, `redis`, `minio`, `elasticsearch`, or `api`.

This is not about allowing the sandbox to operate other Docker containers. The sandbox does not mount the Docker socket, so it cannot control Docker through the local daemon. The network risk is different: if a sandbox container joins `newbee_notebook_network`, user code could directly connect to internal service ports and bypass Newbee's policy, permission, and business APIs.

## Implemented Direction

- `SandboxRequest.network_enabled` now defaults to `True`.
- `network_enabled=True` maps to a dedicated Docker bridge network named `newbee_skill_net`.
- `network_enabled=False` still maps to Docker `--network none`.
- `DockerRunConfig.network_name` defaults to `newbee_skill_net` and can be overridden with `NEWBEE_SANDBOX_NETWORK_NAME`.
- Reserved network names such as `host`, `bridge`, `none`, and `newbee_notebook_network` are rejected.
- `DockerSandboxNetworkManager` creates the dedicated bridge if it is missing.
- The bridge is created with `com.docker.network.bridge.enable_icc=false`, so sandbox containers keep outbound NAT but are not intended to communicate with other containers on that bridge.
- Warm notebook containers and short-lived sandbox runs both use the same network behavior.
- Network-enabled containers start as root only long enough to add blackhole routes for private/link-local IPv4 ranges, then drop to `DockerRunConfig.user` with `setpriv` before running the requested command.
- The blackhole routes block direct connections to compose container IPs and host-gateway/private addresses while keeping Docker's embedded DNS and public IPv4 egress available.
- If an existing `newbee_skill_net` is found, it must be a managed bridge network with the Newbee sandbox label and `enable_icc=false`; otherwise the sandbox refuses to reuse it.
- Warm notebook containers are rebuilt when the requested network mode changes, because `docker exec` cannot change a running container's network namespace.

## Files

- `newbee_notebook/core/sandbox/contracts.py`: default `network_enabled=True`.
- `newbee_notebook/core/shell/executor.py`: shell requests explicitly use network-enabled sandbox execution.
- `newbee_notebook/core/sandbox/docker_config.py`: adds `network_name` and env loading.
- `newbee_notebook/core/sandbox/docker_network.py`: ensures `newbee_skill_net` exists.
- `newbee_notebook/core/sandbox/docker_command.py`: maps request network intent to Docker `--network` and wraps network-enabled commands with the private-route guard.
- `newbee_notebook/core/sandbox/docker_executor.py`: ensures network for short-lived networked runs.
- `newbee_notebook/core/sandbox/docker_session.py`: ensures network before warm container startup.

## Verification

Unit coverage added:

- Sandbox request default network behavior.
- Shell executor default network behavior.
- Docker command `True -> newbee_skill_net`, `False -> none`.
- Docker executor network creation flow.
- Docker session compatibility with networked warm containers.
- Dedicated network manager reuse/create behavior.
- Existing network validation.
- Warm session rebuild when `network_enabled` changes.

Manual/integration checks should verify:

```bash
python -c "import socket; print(socket.gethostbyname('example.com'))"
```

Expected: succeeds inside sandbox.

```bash
python -c "import socket; print(socket.gethostbyname('postgres'))"
```

Expected: fails unless the host has unrelated DNS for `postgres`.

Additional checks cover direct compose container IPs and `host.docker.internal:5432`, because DNS isolation alone is not sufficient.
