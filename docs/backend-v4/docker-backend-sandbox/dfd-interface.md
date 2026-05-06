# Docker-backed Sandbox Data Flow And Interface

## External Interface

Docker-backed executor 实现现有协议：

```python
class SandboxExecutor(Protocol):
    async def execute(self, request: SandboxRequest) -> SandboxResult:
        ...
```

不改变 `SandboxRequest`、`SandboxResult`、`ShellExecutor` 或 `bash` 工具的对外 schema。调用方仍通过 `BuiltinToolProvider(sandbox_executor=...)` 或运行时单例注入 sandbox executor。

## Bash Execution Flow

1. Agent 产生 `bash` 工具调用。
2. `AgentLoop` 将工具 metadata 与参数交给 `core/policy`。
3. `core/policy` 对危险 bash 返回 `ASK`，`core/permission` 处理用户确认。
4. 允许执行后，`core/tools/bash.py` 调用 `ShellExecutor.execute_bash(command)`。
5. `ShellExecutor` 生成 `SandboxRequest(argv=("bash", "-lc", command), cwd, env, timeout, max_output_bytes, run_dir, network_enabled=False)`。
6. `DockerSandboxExecutor` 验证 `network_enabled=False`、`run_dir` 位于受控根目录，并调用 `DockerCommandBuilder` 生成 host 侧 `docker run` argv。
7. 后端用 `asyncio.create_subprocess_exec(*docker_argv)` 启动 Docker CLI。
8. Docker daemon 创建短生命周期容器，在容器内执行 `bash -lc <command>`。
9. executor bounded streaming 读取 stdout/stderr，处理 timeout、确定性 `docker rm -f` 清理、截断、exit code。
10. `bash` tool 将 `SandboxResult` 转成 `ToolCallResult`。

## Data Ownership

- `SandboxRequest.argv`：由 `core/shell` 拥有。
- Docker run argv：由 `core/sandbox/docker_command.py` 生成，不暴露给 LLM。
- workspace mount：只读，属于用户项目目录。
- run_dir mount：可写，属于本次执行的临时输出目录。
- stdout/stderr：由 Docker executor 截断后返回给 tool。
- permission 决策与审计：仍归 `core/permission`，sandbox 不持久化 allow。

## Configuration Interface

建议首批配置项：

| 环境变量 | 默认值 | 含义 |
|---|---|---|
| `NEWBEE_SANDBOX_BACKEND` | `docker` | 选择 sandbox backend；设为 `none` / `off` / `false` 时禁用 |
| `NEWBEE_SANDBOX_IMAGE` | `newbee-notebook/api:latest` | 容器运行镜像 |
| `NEWBEE_SANDBOX_DOCKER_BIN` | `docker` | Docker CLI 路径 |
| `NEWBEE_SANDBOX_TIMEOUT_SECONDS` | `30` | 默认最大执行时间 |
| `NEWBEE_SANDBOX_MAX_OUTPUT_BYTES` | `120000` | stdout/stderr 合计截断上限 |
| `NEWBEE_SANDBOX_CPUS` | `1` | CPU 限制 |
| `NEWBEE_SANDBOX_MEMORY` | `512m` | 内存限制 |
| `NEWBEE_SANDBOX_MEMORY_SWAP` | `512m` | 内存 + swap 限制 |
| `NEWBEE_SANDBOX_PIDS_LIMIT` | `128` | 进程数量限制 |
| `NEWBEE_SANDBOX_USER` | `1000:1000` | 容器内运行用户 |
| `NEWBEE_SANDBOX_TMPFS` | `/tmp:rw,noexec,nosuid,size=64m` | 容器内临时目录 |
| `NEWBEE_SANDBOX_RUN_ROOT` | `.tmp/sandbox-runs` | 自动 run_dir 和可写挂载根目录 |
| `NEWBEE_SANDBOX_WORK_ROOT` | `.tmp/sandbox-work` | notebook 级 `/work` 根目录；运行时会加入 Docker executor 的 allowed run roots |

## API Dependency Integration

当前 `api/dependencies.py` 的 `get_runtime_builtin_tool_provider_singleton()` 需要在实现批次补齐注入：

```text
get_runtime_sandbox_executor_singleton()
  -> NEWBEE_SANDBOX_BACKEND=docker 时构建 DockerSandboxExecutor
  -> Docker 不可用或 backend 为空时返回 None
  -> BuiltinToolProvider(..., sandbox_executor=executor)
```

要求：

- Docker executor 不可用时保持现有 fail-closed 行为。
- Runtime singleton 不应在 import 阶段访问 Docker daemon，避免启动时硬失败。
- 后端 bash-in-container E2E 若要覆盖 API/chat 链路，必须确认该注入已生效；否则只能覆盖 `build_bash_tool()` 核心链路。

## API Testing Interface

本批不新增生产 HTTP 执行端点。bash-in-container 的后端 E2E 采用两层：

- 核心 E2E：真实 Docker daemon + `build_bash_tool()` + `DockerSandboxExecutor`。
- API 注入验证：启动 FastAPI 后确认 `BuiltinToolProvider` 注入 Docker executor，不再返回 `sandbox_unavailable`。
- API 冒烟：启动 FastAPI，验证 OpenAPI、health、notebook/session/chat 基础链路；chat 中真实 LLM 工具调用另需可控 LLM fixture 或后续测试专用 provider。

如果必须经 HTTP 触发 bash，建议后续单独设计受保护的测试-only endpoint，并要求只在 `NEWBEE_ENABLE_TEST_ENDPOINTS=true` 下注册，避免生产暴露任意命令执行。
