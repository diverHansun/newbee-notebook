# Docker-backed Sandbox Test Plan

## Module Test Profile

- 模块原型：外部依赖封装 + 工具链适配。
- Unit 测试：不需要 Docker，验证 Docker argv 构造、输出截断、错误映射。
- Integration 测试：需要 Docker daemon 和本地 runtime 镜像，验证容器真实执行。
- API smoke：需要 FastAPI 启动，验证后端服务和 OpenAPI 可达；bash HTTP 触发依赖后续可控 LLM 或测试-only endpoint。

## Unit Tests

目录：

```text
newbee_notebook/tests/unit/core/sandbox/
  test_docker_command.py
  test_docker_executor.py
```

关键场景：

- `DockerCommandBuilder` 生成的 argv 包含 `docker run --rm`。
- argv 包含硬化 flags：`--network none`、`--read-only`、`--cap-drop ALL`、`--security-opt no-new-privileges`、`--pids-limit`、`--cpus`、`--memory`、`--memory-swap`、`--tmpfs`。
- workspace mount 使用 `--mount type=bind,source=<abs>,target=/workspace,readonly`。
- run_dir mount 使用 `--mount type=bind,source=<abs>,target=/work`。
- 容器命令位于 argv 末尾，不经 host shell 拼接。
- `network_enabled=True` 被拒绝，不能生成 `--network bridge` 或其他联网参数。
- `run_dir` 位于 run root 之外时被拒绝。
- 输出超过 `max_output_bytes` 时通过 bounded streaming read 截断并标记 `truncated=True`。
- Docker unavailable 映射为 `SandboxUnavailableError`。
- timeout 映射为 `SandboxResult(timed_out=True, error_code="timeout")`。
- timeout 后执行 `docker rm -f <container>`，没有残留 `newbee-sandbox-*` 容器。

## Integration Tests

目录：

```text
newbee_notebook/tests/integration/core/sandbox/
  test_docker_bash_executor.py

newbee_notebook/tests/integration/core/tools/
  test_bash_tool_docker.py
```

关键场景：

- `bash -lc "echo hello"` 在容器内执行，stdout 为 `hello`。
- `bash -lc "exit 7"` 返回 exit code 7，不抛 executor 异常。
- `bash -lc "sleep 99"` 在 1 秒 timeout 下返回 timeout。
- 写入 `/work/out.txt` 后 host `run_dir/out.txt` 可见。
- 尝试写 workspace 只读挂载失败。
- 默认网络下访问 compose sibling 失败。
- `build_bash_tool(..., sandbox_executor=DockerSandboxExecutor(...))` 返回 `ToolCallResult(error=None)`。
- Docker-backed executor 注入 `BuiltinToolProvider` 后，bash 工具不再走 `UnavailableSandboxExecutor`。

Integration 测试必须标记：

```python
pytestmark = [pytest.mark.integration]
```

Docker 或 runtime 镜像不可用时使用 `pytest.skip(...)` 并输出可执行 preflight 提示：

```powershell
docker image inspect $env:NEWBEE_SANDBOX_IMAGE
docker run --rm $env:NEWBEE_SANDBOX_IMAGE bash --version
```

## Backend E2E Acceptance

本批验收命令建议：

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\core\sandbox newbee_notebook\tests\unit\core\shell newbee_notebook\tests\unit\core\tools\test_bash_tool.py -q
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\integration\core\sandbox newbee_notebook\tests\integration\core\tools\test_bash_tool_docker.py -q
```

Preflight：

```powershell
if (-not $env:NEWBEE_SANDBOX_IMAGE) { $env:NEWBEE_SANDBOX_IMAGE = "newbee-notebook/api:latest" }
docker image inspect $env:NEWBEE_SANDBOX_IMAGE
docker run --rm $env:NEWBEE_SANDBOX_IMAGE bash --version
docker ps -a --filter "name=newbee-sandbox-" --format "{{.Names}}"
```

后端服务 smoke：

```powershell
.\.venv\Scripts\python.exe main.py --host 127.0.0.1 --port 8000
curl.exe http://127.0.0.1:8000/api/v1/health
curl.exe http://127.0.0.1:8000/openapi.json
```

## Stop Conditions

- Stop if implementation needs `shell=True` or host PowerShell/cmd/bash to execute Agent command.
- Stop if Docker executor requires mounting Docker socket into sandbox container.
- Stop if workspace must be mounted writable to pass tests.
- Stop if an HTTP endpoint would expose arbitrary command execution without an explicit test-only guard.
- Stop if Docker integration tests pass only by reaching compose sibling services.
- Stop if timeout tests leave any `newbee-sandbox-*` container behind.
