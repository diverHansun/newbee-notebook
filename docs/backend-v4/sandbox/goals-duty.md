# sandbox 模块 goals-duty.md

本文档定义 `newbee_notebook/core/sandbox/` 模块的设计目标与职责边界。

---

## 一、模块定位

**一句话说明**：sandbox 模块是"命令执行的隔离层"——当 Bash 工具收到一条需要在受限环境执行的命令时（典型来自 skill 脚本，也可能来自其它需要隔离的通用工具），sandbox 模块负责启动 docker 子容器、挂载最小必需文件、执行命令、回收输出与资源，向上游工具屏蔽所有 docker 细节。当前阶段三条硬性安全前提：
- 所有 host 真实路径在沙箱内**一律 `:ro`**——写入只能进 sandbox 内部可写区
- 子容器**不加入 compose 默认网络**——skill 脚本不能直接访问 postgres / backend / 其它 sibling 服务，但可出外网
- 子容器**无 docker socket / 非 root 用户 / cap-drop=ALL / no-new-privileges**——即便逃逸也无提权能力

**如果没有这个模块**：
- skill 的脚本会直接在 backend 容器中执行，与业务代码/数据库同权限
- Bash 工具需自行处理 docker SDK、挂载、网络、超时、资源限制，职责膨胀
- 容器编排逻辑散落在 skills / Bash 模块内，与 skill 注册/管理强耦合
- 依赖缓存只能每次重装，skill 冷启动体验差
- docker 部署、镜像版本、资源配额的变更反复渗透到上层

---

## 二、Design Goals（设计目标）

### G1：与调用方解耦

sandbox 对 Bash 工具暴露的接口只有一个"执行一次命令"的函数，签名内不出现任何 docker 概念。上游只知道"我给命令 + 挂载清单 + 超时，拿到 stdout/stderr/exit_code"，不知道底层是 docker / firejail / bubblewrap。

### G2：A3 生命周期

每次调用**启动即销毁**（`docker run --rm`），保证强隔离与零状态污染。依赖缓存通过 named docker volume 共享，但**缓存 volume 也 `:ro` 挂载**——避免恶意 skill 污染全局缓存影响后续 skill（见 D5）。

### G3：最小挂载 + host 只读

每次执行都显式声明挂载清单。默认集合是 `<skill_dir>:/skill:ro` + `<run_dir>:/work:rw` + 三个依赖缓存 named volume `:ro`。所有 host 真实路径必须以 `:ro` 挂载，没有例外。`/work` 对应 `tmp/skill-runs/<run_id>/` 这类隔离临时目录，其内容不视为 host 业务文件。挂载清单内出现 host 路径 + `:rw` 直接拒绝执行。

### G4：网络隔离

子容器使用专用 bridge `newbee_skill_net`（不是 compose 默认网络）。该网络仅能出外网，不能访问 compose 内其它 service（postgres / backend / minio / elasticsearch）。

- 默认 `network=True` 表示"可出外网、不可访问 sibling"
- `network=False` 则 `--network=none`
- **从不暴露**"加入 compose 默认网络"这一选项

实现细节：`newbee_skill_net` 在 newbee 启动时由运维层或 sandbox 启动探针创建，使用 docker 默认网络不与 compose 的 `newbee_default` 连通。

### G5：容器硬化

子容器创建必须携带以下 flags：
- `--user 1000:1000`（非 root）
- `--cap-drop=ALL`
- `--security-opt=no-new-privileges`
- `--read-only`（根文件系统只读）
- `--tmpfs /tmp:rw,noexec,nosuid,size=64m`
- `--pids-limit=128`
- `--cpus=1` `--memory=512m` `--memory-swap=512m`
- 绝不挂 `/var/run/docker.sock`、绝不 `--privileged`、绝不 `--network=host`、绝不挂 `/dev/*` 或 `/proc/1`

### G6：磁盘限制

- `/work` 目录软配额（通过镜像层 quota 或 tmpfs 大小 cap）
- 缓存 volume 虽可写状态（由 sandbox 自身维护），但**对 skill 容器仅 `:ro` 挂载**
- stdout/stderr overflow log（D7）单文件上限 10MB，容器总体写盘阈值 100MB，超出 kill

### G7：镜像白名单 + 版本 pin

仅允许：
- `newbee-skill-runtime:<digest>`（主镜像，推荐所有 skill 使用）
- `python@sha256:<digest>` / `node@sha256:<digest>` / `denoland/deno@sha256:<digest>` / `oven/bun@sha256:<digest>`（按需覆盖）

**拒绝可变 tag**（`:latest` / `:*`）。白名单以 digest 形式硬编码或由 `configs/sandbox/images.lock` 管理，随 newbee 版本发布。SKILL.md 不能指定镜像（见 skills N10），若 skill 需特殊依赖只能通过装入到 `newbee-skill-runtime` 或用户自行扩展白名单（未来 v2）。

### G8：argv-only 命令执行

`exec()` 接收的 `command` 必须是 `list[str]`（argv 形式）。**不接受 shell 字符串**。若需要管道/重定向，调用方自行分解为多次调用或 heredoc 方式传入。这是为了消除引号/注入攻击面。

### G9：env 白名单

默认不透传任何 host 环境变量。`env` 参数是显式白名单（`dict[str, str]`）。不允许传入 `PYTHONPATH` / `LD_PRELOAD` / `NODE_OPTIONS` 等逃逸向量（硬编码黑名单拦截）。

### G10：可观测

每次执行输出结构化日志（run_id、image digest、argv hash、duration、exit_code、resource peak、mount 清单），便于排查 skill 失败与性能问题。日志落盘到 `tmp/skill-runs/<run_id>/` 便于定位；不入 DB。

---

## 三、Duties（职责）

### D1：暴露 exec 接口

提供 `exec(req: ExecRequest) -> ExecResult`。`ExecRequest` 字段：
- `command: list[str]`（argv）
- `image: str`（镜像名，必须在白名单；默认 `newbee-skill-runtime:<digest>`）
- `mounts: list[MountSpec]`（调用方组装）
- `network: bool = True`（True = `newbee_skill_net`；False = `none`）
- `timeout_seconds: int = 60`（调用方可收紧，不可放宽）
- `env: dict[str, str] = {}`（白名单键值对）
- `run_id: str`（由调用方生成，用于日志追踪）

`ExecResult` 字段：`stdout`、`stderr`、`exit_code`、`duration_ms`、`truncated`、`log_path`。

### D2：容器生命周期编排

- `docker run --rm` 启动容器，所有 G5 flags 一次性组合
- argv 作为容器 CMD 传入（不经 shell）
- 超时到达强制 `docker kill` + 清理
- OOM / 超时 / 镜像缺失 / 磁盘爆满均转为结构化错误码（`SandboxError` 子类），不抛原始 docker 异常

### D3：镜像管理

- `docker pull` 首次拉取（启动预热推荐）；有超时兜底
- 非白名单镜像直接拒绝，返回 `ImageError`
- 白名单内但 digest 不匹配（用户指定的 tag 解析到不同 digest）也拒绝

### D4：挂载策略校验

- host 真实路径一律 `:ro`，否则拒绝
- 校验路径归属允许的根目录：`configs/skills/`、`tmp/skill-runs/`、`newbee_skill_cache_*` named volumes
- 拒绝 `..`、拒绝符号链接逃逸（实现用 `os.path.realpath` + 前缀检查）
- `tmp/skill-runs/<run_id>/` 这类隔离临时目录可 `:rw`
- 缓存 volume 对 skill 容器一律 `:ro`（见 D5）

### D5：依赖缓存 volume 维护

- 启动时确保 `newbee_skill_cache_pip / cache_npm / cache_bun` 三个 named volume 存在
- **缓存预热**由独立的"cache-writer"容器完成（newbee 部署时或控制面板手动触发），skill 容器从不挂缓存为 `:rw`
- 暴露清理接口（控制面板"清缓存"）

### D6：优雅关闭

进程收 SIGTERM 时停止受理新 exec；已启动容器限时等待结束，超时强杀；释放 volume handle。

### D7：输出截断与回流

stdout/stderr 超过阈值（如 256KB/流）时截断并设置 `truncated=True`。完整输出落盘 `tmp/skill-runs/<run_id>/` 的 `stdout.log` / `stderr.log`（单文件 ≤10MB）。落盘文件被标记为 `600` 权限，48 小时后由运维清理任务回收（清理任务不在本模块）。

### D8：结构化日志

每次 exec 写一条 JSON 行到 `tmp/skill-runs/<run_id>/exec.json`（run_id / image@digest / argv_hash / duration_ms / exit_code / resource_peak / mounts / network_mode）。可被控制面板的"Skills 最近运行"页面读取展示。

---

## 四、Non-Duties（非职责）

### N1：不定义调用方的业务语义

sandbox 不知道被执行的命令属于哪个 skill、为什么执行。它只看见 `ExecRequest`。

### N2：不做权限决策

是否允许调用 sandbox 由 policy + permission 决定。sandbox 被调用到这一步意味着决策已完成。

### N3：不管理 skill 存储

`configs/skills/<name>/` 的创建/删除/安装属于 skills 模块。sandbox 只挂载。

### N4：不创建 run_dir

`tmp/skill-runs/<run_id>/` 由**调用方（Bash 工具）** 在调 `exec()` 之前创建。sandbox 只挂载、不 mkdir。`run_id` 也由调用方生成。

### N5：不实现 Bash/Read/Glob/Grep 工具本身

这些工具在 `core/tools/`。sandbox 是它们的依赖项。

### N6：不提供脚本解释器

sandbox 不替调用方选 python / node。argv 第一元素即解释器路径。

### N7：不跨调用保留容器

不实现 A2 长连模式。

### N8：不维护镜像构建

`newbee-skill-runtime` 镜像 Dockerfile 在 `docker/`，由 CI 构建并推送。sandbox 运行时只 `docker pull`。

### N9：不走数据库

sandbox 无持久字段，日志仅落盘。

### N10：不解析命令内容

不做 `rm -rf` 等字面量检查（那是 policy 的事）。

### N11：不允许任何方式写 host

当前阶段无逃生口。若未来要支持"sandbox 输出回写 host"，必须经独立设计 + 显式工具，不在本模块默认接口内。

### N12：不处理 skill 脚本的入参协议

stdin/stdout JSON 双通道语义由 skills 模块与 mellow 约定。sandbox 对 stdin 只透传字节、对 stdout 只收集字节。

### N13：不暴露 compose 内部网络

永远不支持 `--network=newbee_default`。即便 yolo 档位也不放开此项——这是硬性威胁隔离，不是 UX 决定。

---

## 五、设计约束与假设

### 约束

1. **依赖 docker socket**：backend 容器必须能访问 `/var/run/docker.sock` 或远端 docker API；子容器**绝不**共享此 socket
2. **镜像白名单以 digest 形式硬编码**：随 newbee 发版升级
3. **单 daemon 假设**：初期只支持本机 docker daemon
4. **cache volume 单向**：只由独立 cache-writer 容器写入；skill 容器仅读
5. **argv-only**：调用方必须把命令拆成 argv，不允许任何形式的 shell 字符串
6. **`newbee_skill_net` 预先存在**：由运维层或 sandbox 启动探针创建；若不存在则 `exec()` 返回 `NetworkError`
7. **不支持非 docker 部署**：若用户在非 docker 环境部署 newbee，sandbox 不可用，skill 功能整体降级（skills 模块负责降级处理）

### 假设

1. docker daemon 在 newbee 启动前已就绪
2. `newbee-skill-runtime:<digest>` 镜像已构建/推送
3. 调用方（Bash 工具）负责创建 `run_dir` 与组装挂载清单
4. skills 模块负责创建/维护 `configs/skills/<name>/`
5. 容器内用户 1000:1000、工作目录 `/work` 由镜像固定

---

## 六、与其他模块的关系

| 模块 | 关系 | 说明 |
|------|------|------|
| core/tools（Bash） | 被依赖 | Bash 判定需要隔离时创建 run_dir → 调 `sandbox.exec` |
| skills | 间接 | skills 准备 skill 目录；sandbox 挂载但不创建 |
| policy / permission | 上游 | 调用到 sandbox 表示决策已通过 |
| docker daemon | 依赖 | 编排主力；`newbee_skill_net` 网络由其提供 |
| 运维层（docker-compose） | 依赖 | 预构建镜像、创建 `newbee_skill_net`、运行 cache-writer |
| AppSettingsService | 极少 | 仅"清理缓存"等维护操作读少量配置 |
| 控制面板（前端） | 被依赖（间接） | 通过 Bash 调用链观察运行；维护入口通过专用 API |

---

## 七、文档自检

- [x] 可以用一句话说明模块存在意义（命令执行的隔离层）
- [x] 可以清楚回答"不该做什么"（不决策、不管理存储、不创建 run_dir、不实现工具、不解析命令、不走 DB、不暴露 compose 网络）
- [x] 与 skills / policy / permission / core/tools 边界清晰
- [x] 所有职责可被验证（exec 接口单测、挂载校验单测、镜像白名单单测、网络隔离集成测、硬化 flags 集成测）
- [x] A3 生命周期 + named volume `:ro` 缓存防污染
- [x] 三条硬性隔离（host ro / 网络隔离 / 容器硬化）覆盖 codex 指出的供应链风险与 docker socket 风险
- [x] argv-only 消除 shell 注入
- [x] env 白名单消除逃逸向量
