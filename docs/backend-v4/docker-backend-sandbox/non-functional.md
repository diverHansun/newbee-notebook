# Docker-backed Sandbox Non-functional Requirements

## Security

- Host 侧不得用 `shell=True` 执行 Agent 命令。
- Docker CLI 必须以 argv 形式启动。
- 默认 `--network none`。
- `network_enabled=True` 在本批必须被拒绝，不能被解释为打开网络。
- workspace 只能只读挂载。
- `run_dir` 是唯一默认可写挂载。
- `run_dir` 必须位于配置的 sandbox run root 或 allowlist 下。
- 容器内不得挂载 Docker socket。
- 容器硬化 flags 由代码固化，调用方不能覆盖放宽。
- 默认不透传 host env。

## Reliability

- Docker daemon 不可用时返回明确的 `sandbox_unavailable` 行为，而不是卡住请求。
- 超时必须终止 Docker CLI 进程，并通过唯一容器名或 cidfile 执行 `docker rm -f`，确保 Docker daemon 回收容器。
- 非零退出不是 executor 异常，应正常返回 exit code。
- stdout/stderr 必须截断，避免大输出拖垮后端。

## Portability

- Windows host + Docker Desktop 是首个目标环境。
- Docker bind mount 必须使用 `--mount type=bind,source=...,target=...,readonly` 形式，不使用 `-v <windows-path>:/target:ro`。
- 不依赖 Linux-only host shell 行为。
- 集成测试检测 Docker 不可用时应 skip，而不是失败污染普通 unit gate。

## Performance

- 每次执行启动独立容器，优先安全与确定性，不追求低延迟。
- 默认 timeout 30 秒，调用方只能收紧到更短值。
- 默认输出上限 120KB。

## Observability

- `SandboxResult` 至少包含 exit code、stdout、stderr、timeout、truncated、error code。
- 后续可加 run id、duration ms、docker image、argv hash 到 metadata；本批不要求持久化 exec.json。

## Compatibility

- `bash` 工具 schema 不变。
- `SandboxExecutor` Protocol 不变。
- 未配置 Docker executor 时，现有 fail-closed 行为保持可用。
