# Docker-backed Sandbox Goals And Duty

## Context

上一批已经完成 `core/sandbox` 的执行契约、`core/shell` 的 bash 适配，以及 `core/tools/bash.py` 的 fail-closed 行为。本批目标是在不直接执行 host shell 的前提下，补上 Docker-backed executor，让 `bash` 工具可以在短生命周期容器中真实执行，并能在后端完成 bash-in-container 验收。

本文档是 `docs/backend-v4/sandbox/` 长期完整设计的当前批次落地稿。长期设计中的 cache writer、digest lock、复杂 volume 管理和日志保留策略不在本批一次性完成。

## Goals

- 实现 `DockerSandboxExecutor`，满足现有 `SandboxExecutor.execute(SandboxRequest)` 协议。
- 每次 bash 调用启动一个独立容器，执行完成后自动删除容器。
- Agent 生成的命令只在容器内执行；后端只调用 Docker CLI 控制 Docker daemon，不调用 `shell=True`、PowerShell、cmd 或 host bash 执行用户命令。
- 默认网络为 `none`，除非后续明确设计允许网络。
- 本批即使 `SandboxRequest.network_enabled=True`，Docker executor 也必须拒绝执行并返回明确错误，不能自动打开网络。
- 默认只读挂载 workspace，按需挂载 `run_dir` 为可写目录。
- 固化容器硬化参数，调用方不能放宽：非 root、cap drop、no-new-privileges、read-only rootfs、tmpfs、CPU/内存/pids 限制。
- 将容器 stdout/stderr/exit code/timeout/truncated 映射为现有 `SandboxResult`，保持 `bash` 工具 schema 不变。
- 提供 Docker daemon 可用性、bash 成功、非零退出、超时、输出截断、写入 run_dir、workspace 只读、网络隔离等后端 E2E 测试。

## Non-goals

- 不实现长期 image digest lock 和镜像供应链发布流程。
- 不实现 cache writer、pip/npm/bun 只读缓存 volume。
- 不支持后台 bash 任务。
- 不支持容器复用、worker pool 或预热容器。
- 不把 Docker socket 挂入 sandbox 容器。
- 不把 compose 内部网络暴露给 sandbox 容器。
- 不新增一个通用“执行任意命令”的生产 HTTP API。bash 执行仍只通过 agent 工具链或测试 harness 进入。

## Duty Boundary

- `core/sandbox` 负责 Docker 容器执行、硬化参数、超时回收、输出截断和错误映射。
- `core/shell` 负责把 bash 请求转换为 `SandboxRequest`，并保持当前 timeout/output limit 规则。
- `core/tools/bash.py` 负责 Agent 可见 schema、tool metadata 和 `ToolCallResult` 格式。
- `core/policy` 与 `core/permission` 继续负责 bash 风险裁定与确认，不下沉到 sandbox。
- Docker image 构建、Docker daemon 安装和 Docker Desktop 启动属于运行环境前置条件。

## Initial Decisions

- 本批使用 Docker CLI，而不是 docker-py。理由是项目当前没有 docker Python 依赖，CLI 可通过 `asyncio.create_subprocess_exec` 以 argv 形式调用，依赖面更小。
- 初始运行镜像默认使用本地可配置镜像 `NEWBEE_SANDBOX_IMAGE`；若未配置，优先使用本地已有的 `newbee-notebook/api:latest` 作为开发期 runtime。测试前必须执行 `docker image inspect <image>` 和 `docker run --rm <image> bash --version` preflight；镜像缺失时 integration 测试 skip 并给出构建提示。后续可切换为专用 `newbee-notebook/sandbox-runtime:<version>`。
- Docker executor 默认启用条件为显式配置或本地开发依赖注入。生产环境若 Docker 不可用，应继续 fail-closed。
