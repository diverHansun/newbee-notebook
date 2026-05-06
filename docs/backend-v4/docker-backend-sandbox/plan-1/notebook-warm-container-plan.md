# Notebook Warm Container Plan

## Background

当前 `DockerSandboxExecutor` 采用每次 bash 调用创建一个短生命周期容器的方式。这个设计安全、简单、便于回收，但在 notebook 内连续执行多条 bash 命令时会重复承担 Docker 容器启动开销。一次短命容器启动在本地测得约 0.38 到 0.48 秒，单次可接受，连续调用时会变成明显延迟。

本计划基于对 `deepagents`、`kimi-cli`、`OpenHarness` 三个本地项目的 sandbox 设计分析：

- `deepagents`：适合借鉴 backend protocol，将 bash 与 read/grep/glob/edit/write 放在同一个 sandbox backend 能力边界下。
- `kimi-cli`：适合借鉴 background task、非交互 shell、日志 tail、stop/list/output 等长任务体验。
- `OpenHarness`：适合借鉴 session 级长期 Docker 容器，通过 `docker exec` 复用容器执行命令。

## Goals

- 建立 notebook 级 `/work` 目录，让同一 notebook 下多个 session 的 bash 命令共享可写工作区。
- 在首次 bash 调用时按需创建 notebook 级 warm container，后续 bash 通过 `docker exec` 进入同一个容器。
- 保留现有 Docker 硬化参数：网络关闭、只读 workspace、可写 `/work`、非 root、cap drop、no-new-privileges、资源限制。
- 保持 `SandboxExecutor.execute(SandboxRequest)` 协议稳定，避免把 Docker 生命周期细节暴露给 tool 层。
- 为后续 background bash task 和 filesystem tools 接入 sandbox backend 留出稳定扩展点。

## Non-goals

- 本批不实现交互式 terminal 或持续 shell state。
- 本批不开放容器网络。
- 本批不把 Docker socket 挂入 sandbox 容器。
- warm container 首批不直接替换 read/grep/glob/edit/write 的实现；后续按 Batch 5 逐步接入 sandbox backend。

## Implementation Batches

### Batch 1: NotebookSandboxWorkspace

实现 notebook 级可写目录管理。

职责：

- 根据 `notebook_id` 生成稳定目录：`.tmp/sandbox-work/notebooks/<notebook_id>/work`
- 对 notebook id 做 slug 化，避免路径穿越和非法文件名。
- 返回 host 侧 `work_dir` 与容器侧 `/work` 的映射信息。
- 同一个 notebook 下不同 session 共享同一个 `work_dir`。

验收标准：

- 相同 notebook id 返回相同目录。
- 不同 notebook id 返回不同目录。
- 恶意 id 不能逃逸 sandbox work root。
- 目录创建幂等。

### Batch 2: DockerSandboxSessionRegistry

实现 notebook 级 warm container 生命周期。

职责：

- `get_or_create(notebook_id, cwd, work_dir)`：没有容器时 `docker run -d ... tail -f /dev/null` 创建容器。
- `exec(notebook_id, request)`：通过 `docker exec -w /workspace ... bash -lc <command>` 执行命令。
- `stop(notebook_id)`：停止并删除对应容器。
- `reap_idle(now)`：回收超过 TTL 的空闲容器。

验收标准：

- 第一次执行会创建容器。
- 第二次执行复用同一容器，不再调用 `docker run`。
- `stop()` 会调用 `docker stop` 并清除 registry 状态。
- 超过 TTL 后 `reap_idle()` 会回收容器。

### Batch 3: Bash Tool Integration

让 `core/tools/bash.py` 通过 `ShellExecutor -> SandboxExecutor` 优先使用 warm container executor。

职责：

- 默认仍保持 fail-closed。
- 在 API dependency 中构建 notebook aware sandbox executor。
- 若请求缺少 notebook 上下文，保留当前短生命周期 executor 或明确降级策略。
- 输出格式仍为 `Exit code`、`STDOUT`、`STDERR`、`timed_out`、`truncated`。

验收标准：

- bash 成功、非零退出、timeout、输出截断行为不回归。
- 同一 notebook 连续 bash 调用共享 `/work` 文件。
- workspace 仍为只读，写入 `/workspace` 失败，写入 `/work` 成功。

### Batch 4: Background Bash Task

借鉴 `kimi-cli`，将长任务从普通 bash 中分离。

职责：

- 创建 task id、状态文件、日志文件。
- 支持查询 output tail、停止任务、列出任务。
- 日志保存在 notebook 级 `/work` 或专用 task log root 下。

验收标准：

- 长任务不会阻塞普通请求。
- 可查询 partial output。
- 可停止运行中的 task。
- task 状态在后端重启后的恢复策略明确。

### Batch 5: Filesystem Tools On Sandbox Backend

借鉴 `deepagents`，逐步让 read/grep/glob/edit/write 通过 sandbox backend 执行。

职责：

- 将 filesystem tools 与 bash 共享 notebook `/work` 和 workspace 边界。
- read/grep/glob 默认只读，write/edit 继续经过 permission/policy 决策门。
- 大文件读写、替换、grep 使用 sandbox 内部脚本，避免把复杂文件处理暴露给 host shell。

验收标准：

- filesystem tools 与 bash 对同一 `/work` 的视图一致。
- 写操作不能绕过 permission/policy。
- 路径穿越、symlink escape、二进制/大文件边界均有测试覆盖。

## Recommended First Slice

第一批实施只做 Batch 1，并为 Batch 2 准备接口命名，不直接引入长期容器状态。理由：

- notebook 级 `/work` 是低风险基础能力。
- 它可以立即改善 bash 多 session 文件共享问题。
- 即使后续 warm container 设计调整，`NotebookSandboxWorkspace` 仍然可复用。
- 它为 Docker 短生命周期 executor 和长期 container executor 提供共同的路径约束。

## Batch 2 Implementation Notes

Batch 2 已落地 notebook 级 warm container：

- `DockerSandboxSessionRegistry` 负责 `get_or_create`、`docker exec`、`stop()`、`stop_all()`、`reap_idle()`。
- `DockerSandboxExecutor` 在 `SandboxRequest.sandbox_session_key` 存在且配置了 registry 时优先走 warm container；没有 session key 时保留短生命周期 `docker run --rm` 行为。
- `ShellEnvironment.sandbox_session_key` 由 `SessionManager` 设置为当前 `notebook_id`，同一 notebook 下多个 session 会共享同一个 Docker 容器和 `/work`。
- registry 使用 per-key `asyncio.Lock` 避免同 notebook 并发首次 bash 时重复 `docker run --name <same>`。
- FastAPI lifespan 启动 idle reaper，并在 shutdown 时停止 reaper 与所有 active sandbox sessions。
- Docker daemon 不可用时 warm startup 会映射为 `SandboxUnavailableError`，保持与短生命周期 executor 的错误语义一致。
- 后续审阅补充的取消语义已纳入实现：短生命周期 `docker run` 在调用被取消时会执行容器清理；warm container 首次启动期间被取消时会按确定容器名做 best-effort cleanup；idle reaper 不会回收正在执行命令的 session。

## Batch 3 Implementation Notes

Batch 3 已将 `core/tools/bash.py` 接入 `ShellExecutor -> DockerSandboxExecutor`：

- notebook-scoped runtime 会把 `ShellEnvironment.sandbox_session_key` 设置为当前 `notebook_id`。
- 同一 notebook 下多个 session 的 bash 调用会共享同一个 `/work` 目录和 warm container。
- 没有 `sandbox_session_key` 的调用保留短生命周期 `docker run --rm` 行为。
- `bash` 工具继续声明 `ToolClass.BASH`、`RiskLevel.DANGEROUS`、`sandbox_required=True`，由全局 policy/permission 决定是否执行。
- `background=true` 的 bash 调用在 schema 和运行时都要求提供 `description`。

## Batch 4 Implementation Notes

Batch 4 已实现 in-process background bash task：

- `BackgroundBashTaskManager` 管理 task id、状态、日志和取消。
- `bash` 支持 `background=true` 后返回 task id，不阻塞当前工具调用。
- 新增 `bash_task_list`、`bash_task_output`、`bash_task_stop` 三个工具。
- `bash_task_list/output` 是 `READ/SAFE`；`bash_task_stop` 是 `BASH/MODERATE` 且 `sandbox_required=True`。
- `wait(timeout_seconds=...)` 只做有界等待，不会因为 timeout 取消后台任务。
- `stop()` 对 pending/running 状态都有兜底停止记录，避免 start 后立即 stop 留下 pending。
- 后端进程重启后的 task 恢复当前只保留日志文件可读；in-process running task 不做恢复，这是后续持久化任务调度批次的边界。

## Filesystem Boundary Notes

当前 read/grep/glob/edit/write 仍是 host-side Python 工具，不是在容器内执行命令。为符合 notebook sandbox 规则，request-scoped `ShellEnvironment` 使用如下边界：

- `/workspace/...` 映射到宿主 workspace，只读。
- `/work/...` 映射到 notebook 级可写 work dir。
- `read/grep/glob` 可读取 `/workspace` 与 `/work` 范围内的非敏感 UTF-8 文件。
- `write/edit` 在 notebook-scoped runtime 下只允许写 `/work`，不能修改 `/workspace` 对应的宿主文件。
- `grep` 会对递归候选文件逐个重新执行 path policy，避免 symlink escape 读取外部宿主文件。

因此，对“read/grep/glob/edit/write 是否能读取容器外宿主机文件”的当前回答是：

- 它们不是任意 host 文件工具，不能读取允许 roots 之外的宿主机文件。
- 它们可以读取 `/workspace` 对应的宿主 workspace 文件，因为这也是容器只读挂载能看到的 notebook workspace 视图。
- 它们可以读写 `/work` 对应的 notebook work dir，因为这是容器可写挂载，也是 notebook 内多 session 共享的工作区。
- 它们不能修改 `/workspace` 宿主文件；即使 permission 允许了工具调用，路径策略仍会拒绝 workspace 写入。
- 它们目前不读取容器 rootfs 中未挂载的路径，例如 `/etc`、`/usr`。如果后续需要这种能力，应通过 sandbox backend helper 明确实现，而不是放宽 host path policy。

Batch 5 的下一步是把 filesystem tools 进一步接入 sandbox backend，使工具执行视角更接近 deepagents 的 backend protocol。当前实现先保证宿主写边界不被 tool surface 绕开，并通过 Docker E2E 验证 bash 与 filesystem tools 对 `/work` 的视图一致。

## Batch 5 Current Acceptance

已覆盖的最小验收：

- `bash` 在 warm container 写入 `/work` 后，`read_file`、`grep_files`、`glob_files` 可以看到同一文件。
- `edit_file`、`write_file` 对 `/work` 的修改可以被后续 warm container bash 读到。
- `write_file` 尝试修改 `/workspace` 会返回 `outside_workspace`，宿主 workspace 文件保持不变。
- `AgentLoop + PolicyDecider + PermissionGateway + write_file` 联测验证：permission 拒绝时不落盘，permission 允许时仍只能写 `/work`。

## Test Profile

- 模块原型：基础设施模块 + 桥接/适配模块。
- 主要测试类型：unit + integration。
- mock 边界：unit 测试 mock Docker runner；integration 测试使用真实 Docker daemon，Docker 不可用时 skip。
- 测试归属目录：
  - `newbee_notebook/tests/unit/core/sandbox/`
  - `newbee_notebook/tests/integration/core/sandbox/`
  - `newbee_notebook/tests/integration/core/tools/`

## Open Questions For Later Batches

- warm container TTL 当前默认采用 30 分钟，并通过 FastAPI lifespan reaper 自动回收空闲容器。
- API 层已通过 `SessionManager._build_tool_environment()` 将 `notebook_id` 注入 `ShellEnvironment.sandbox_session_key`，并将 notebook work dir 注入 `run_dir`。
- background bash task 当前使用 `(run_dir or cwd)/.newbee-background-tasks` 作为日志根目录；后端重启恢复 running task 不属于当前批次。
- 后续仍需评估是否为 warm container 增加最大数量限制、LRU 回收，以及跨进程/多 worker 的 session registry 协调。
- 后续 Batch 5 仍需评估是否把 read/grep/glob/edit/write 的执行从 host-side Python 进一步迁移到 sandbox backend helper。
