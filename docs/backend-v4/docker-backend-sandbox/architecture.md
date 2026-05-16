# Docker-backed Sandbox Architecture

## Architecture Overview

Docker-backed sandbox 以现有 `SandboxExecutor` 协议为稳定边界，只新增一个具体实现：

```text
core/tools/bash.py
  -> core/shell/ShellExecutor
  -> core/sandbox/DockerSandboxExecutor
  -> docker CLI
  -> ephemeral container
```

模块由三个生产子组件组成：

- `DockerSandboxExecutor`：对外实现 `execute(request)`，编排命令构造、进程启动、超时、输出截断和结果映射。
- `DockerRunConfig`：集中保存镜像名、容器内工作目录、资源限制、网络模式、输出限制和 Docker binary 路径。
- `DockerCommandBuilder`：纯函数组件，把 `SandboxRequest + DockerRunConfig` 转成 `docker run ...` argv。

Docker CLI、daemon 与镜像 preflight 暂放在 integration test helper 中，不在生产启动阶段主动访问 Docker，避免 API import 或启动时硬失败。

## File Layout

```text
newbee_notebook/core/sandbox/
  __init__.py
  contracts.py
  executor.py
  docker_executor.py
  docker_config.py
  docker_command.py

newbee_notebook/tests/unit/core/sandbox/
  test_docker_command.py
  test_docker_executor.py

newbee_notebook/tests/integration/core/sandbox/
  test_docker_bash_executor.py

newbee_notebook/tests/integration/core/tools/
  test_bash_tool_docker.py
```

后续如果引入专用 runtime 镜像，再补：

```text
docker/sandbox/
  Dockerfile
```

## Container Shape

每次执行使用 `docker run --rm` 创建短生命周期容器：

- `--network none`
- `--read-only`
- `--cap-drop ALL`
- `--security-opt no-new-privileges`
- `--user 1000:1000`
- `--pids-limit 128`
- `--cpus 1`
- `--memory 512m`
- `--memory-swap 512m`
- `--tmpfs /tmp:rw,noexec,nosuid,size=64m`
- 每次运行使用唯一容器名 `newbee-sandbox-<uuid>`，或等价 `--cidfile` 方案，便于 timeout 后确定性清理。
- workspace 以 `--mount type=bind,source=<abs>,target=/workspace,readonly` 挂载，避免 Windows 盘符与 `-v ...:ro` 解析冲突。
- `run_dir` 以 `--mount type=bind,source=<abs>,target=/work` 挂载为唯一可写 host bind mount。
- 容器工作目录默认为 `/workspace`
- 环境变量只传 `SandboxRequest.env` 中显式提供的键值，并强制覆盖 `HOME=/tmp`

## Path Invariants

首批实现不扩展 `SandboxRequest`。Docker executor 按以下规则解释现有字段：

- `request.cwd` 被视为本次唯一 workspace root，并只读挂载到 `/workspace`。
- 如果调用方需要多 root 或 skill root，可在后续扩展 `SandboxRequest`；本批不隐式挂载 `additional_roots` 或 `skill_roots`。
- `request.run_dir` 如果存在，必须位于 `DockerRunConfig.run_root` 或显式 allowlist 下；否则拒绝执行。
- `request.run_dir` 如果不存在，executor 在 `DockerRunConfig.run_root/newbee-sandbox-<uuid>` 下创建临时 run dir，并挂载到 `/work`。
- 容器内脚本应把输出产物写入 `/work`，而不是写 `/workspace`。

## Command Strategy

Docker executor 不解析 Agent 命令。它只消费 `SandboxRequest.argv`。

当前 `ShellExecutor` 会把 bash 字符串转换成：

```python
SandboxRequest(argv=("bash", "-lc", command), ...)
```

Docker executor 将该 argv 作为容器内命令附加在 `docker run` argv 尾部。这里存在 shell，但 shell 在容器内，不在 host 上；host 侧只运行 `docker` CLI。

## Error Handling

- Docker CLI 不存在或 daemon 不可达：抛 `SandboxUnavailableError`。
- `request.network_enabled=True`：拒绝执行，返回或抛出 `network_disabled` 语义错误；本批不开放网络。
- Docker 进程启动失败：抛 `SandboxExecutionError`。
- 容器超时：终止 Docker CLI 进程后，必须执行 `docker rm -f <container-name-or-cid>` 做确定性清理，再返回 `SandboxResult(exit_code=None, timed_out=True, error_code="timeout")`。
- 容器非零退出：返回 `SandboxResult(exit_code=<code>)`，由 bash tool 映射为 `nonzero_exit`。
- 输出超过限制：stdout/stderr 通过 bounded streaming read 截断，`truncated=True`；达到上限后继续 drain 到进程结束或 timeout，但不继续累积到内存。

## Trade-offs

- 使用 Docker CLI 比 docker-py 少一个依赖，但错误结构不如 SDK 精细；本批通过 stderr 与 exit code 做足够稳定的映射。
- 默认使用开发期镜像可以快速完成 bash-in-container E2E，但供应链安全不如 digest lock；专用 runtime 镜像和 digest lock 放入后续硬化批次。
- `run_dir` 可写而 workspace 只读，会让脚本显式把产物写入 `/work`；这比让容器直接改 workspace 更安全。
