# sandbox 模块 dfd-interface.md

本文档描述 `newbee_notebook/core/sandbox/` 模块的数据流与对外接口，说明数据如何进入模块、经何种处理、以何种形态输出。设计严格基于 [goals-duty.md](goals-duty.md) 与 [architecture.md](architecture.md)。

---

## 一、Context & Scope（上下文与范围）

sandbox 模块处于工具调用链的**执行隔离节点**：当 Bash 工具需要执行命令时（agent_loop 已通过 policy + permission 裁定允许），Bash 工具创建 run_dir、组装挂载清单，调用 `SandboxExecutor.exec()` 在 docker 子容器中完成隔离执行。

### 与外部模块的交互关系

| 方向 | 模块 | 角色 |
|------|------|------|
| 输入来源 | core/tools/Bash | 调用方，传入 `ExecRequest` |
| 输入来源 | skills（间接） | skill 目录由 skills 模块维护，Bash 工具组装挂载清单时引用 |
| 依赖 | docker daemon | 编排容器生命周期 |
| 依赖 | `newbee_skill_net`（运维层创建） | 专用 bridge 网络 |
| 依赖 | cache volume（cache-writer 维护） | 依赖缓存 named volume |
| 输出去向 | core/tools/Bash | 返回 `ExecResult`（stdout/stderr/exit_code 等） |
| 输出去向 | 文件系统 `tmp/skill-runs/<run_id>/` | 落盘 overflow log 与 exec.json |
| 不交互 | policy / permission | sandbox 被调用时决策已完成 |
| 不交互 | DB | sandbox 无持久字段 |

### 本文档范围

仅描述 sandbox 模块内部的数据流——从接收 `ExecRequest` 到返回 `ExecResult` 的全过程。不描述 Bash 工具如何决定需要调用 sandbox、如何创建 run_dir、如何组装挂载清单。不描述 cache-writer 容器的独立生命周期。

---

## 二、Data Flow Description（数据流描述）

sandbox 的数据流是**一次同步的容器编排管线**：前置校验是纯函数，容器编排涉及 docker SDK 调用。

### 主路径：命令隔离执行

```
core/tools/Bash（已通过 policy + permission）
  │
  │  ExecRequest(command, image, mounts, network, timeout_seconds, env, run_id)
  ▼
SandboxExecutor.exec()
  │
  ├─(1)─ ImageGuard.validate(image)
  │      校验 image 名必须以 @sha256:<digest> 形式引用
  │      对照 configs/sandbox/images.lock 白名单
  │      拒绝可变 tag（:latest / :*）
  │      失败 → ImageError（不启容器，无 docker side effect）
  │
  ├─(2)─ NetworkGuard.normalize(network)
  │      network=True  → "newbee_skill_net"（专用 bridge，可出外网，不可达 compose sibling）
  │      network=False → "none"
  │      拒绝任何 compose 默认网络接入请求
  │      若 newbee_skill_net 不存在 → NetworkError
  │
  ├─(3)─ MountValidator.validate(mounts)
  │      逐项校验：
  │        - host 真实路径 → 必须 :ro（否则拒绝）
  │        - 缓存 volume → 必须 :ro（对 skill 容器）
  │        - 路径归属检查：仅允许 configs/skills/、tmp/skill-runs/、named volumes
  │        - 拒绝 .. / symlink 逃逸 / 绝对路径越界
  │      自动注入三个缓存 volume（:ro）：
  │        newbee_skill_cache_pip → /root/.cache/pip
  │        newbee_skill_cache_npm → /root/.npm
  │        newbee_skill_cache_bun → /root/.bun/install/cache
  │      失败 → MountError（不启容器）
  │
  ├─(4)─ HardenedContainerRunner.run(request, validated_mounts, network_mode)
  │      拼装 docker run 参数：
  │        --rm --user 1000:1000
  │        --cap-drop=ALL --security-opt=no-new-privileges
  │        --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m
  │        --pids-limit=128 --cpus=1 --memory=512m --memory-swap=512m
  │        --network=<network_mode>
  │        -v <mount_1>:<target_1>:ro ...
  │        -v <run_dir>:/work:rw
  │        <image> <command[0]> <command[1]> ...
  │      command 以 argv 形式传入（不经 shell）
  │      env 白名单透传（拦截 LD_PRELOAD / PYTHONPATH 等逃逸向量）
  │
  │      ├─ 启动容器
  │      │
  │      ├─(5)─ OutputCollector.stream(stdout, stderr)
  │      │       流式读取 stdout/stderr
  │      │       单流 > 256KB 时截断，设置 truncated=True
  │      │       完整输出落盘 tmp/skill-runs/<run_id>/stdout.log、stderr.log
  │      │       单文件上限 10MB，超限截断
  │      │
  │      ├─ 等待容器退出
  │      │     exit_code==0 → 正常退出
  │      │     exit_code!=0 → 仍返回 ExecResult（由调用方解读）
  │      │
  │      ├─ 超时到达 → docker kill + TimeoutError
  │      │
  │      ├─ OOM → OOMError + 记录 resource peak
  │      │
  │      └─ docker rm（--rm 已自动清理）
  │
  └─(6)─ 写 exec.json 到 tmp/skill-runs/<run_id>/exec.json
         run_id、image@digest、argv_hash、duration_ms、exit_code、resource_peak、
         mounts 清单、network_mode、error_class
  │
  ▼
ExecResult(stdout, stderr, exit_code, duration_ms, truncated, log_path)
  │
  ▼
core/tools/Bash 解读结果 → 转为 ToolCallResult → agent_loop → mellow
```

### 辅助路径：缓存 volume 维护

```
系统启动时
  │
  ▼
CacheVolumeManager.ensure_volumes()
  │
  └─ docker volume inspect newbee_skill_cache_pip 等
     不存在 → docker volume create

控制面板 "清缓存"
  │
  ▼
CacheVolumeManager.prune()
  │
  └─ 删除并重建三个 cache volume（清空内容但保留 volume 名）

SandboxExecutor.exec() 前置检查
  │
  └─ CacheVolumeManager 确保 volumes 存在
     不存在 → ExecError（视为致命配置错误）
```

### 辅助路径：优雅关闭

```
backend 进程收到 SIGTERM
  │
  ▼
SandboxExecutor.shutdown()
  │
  ├─ 停止受理新 exec 请求
  ├─ 对已启动容器限时等待（≤5s）
  └─ 超时强杀 + 回收
```

### 关键分支条件

| 条件 | 行为 |
|------|------|
| image 非 @sha256: digest 形式 | ImageError，不启容器 |
| image 不在白名单 | ImageError |
| mounts 含 host :rw | MountError，不启容器 |
| mounts 含缓存 volume :rw（对 skill 容器） | MountError |
| mounts 含 .. / symlink 逃逸 | MountError |
| network 请求 compose 默认网络 | NetworkError |
| newbee_skill_net 不存在 | NetworkError |
| command 非 list[str] | ExecRequestError（前置断言） |
| env 含黑名单键 | ExecRequestError |
| 容器超时 | TimeoutError + kill + 清理 |
| OOM | OOMError + 资源 peak |
| exit_code != 0 | 仍返回 ExecResult，不抛异常 |
| docker daemon 不可达 | SandboxUnavailable |

---

## 三、Interface Definition（接口定义）

### 3.1 对外暴露接口

#### SandboxExecutor.exec()

- **调用方**：core/tools/Bash
- **语义**：在隔离的 docker 子容器中执行一次命令
- **输入**：`ExecRequest`
  - `command: list[str]` — argv 形式，第一元素为解释器路径
  - `image: str` — 镜像名，必须为 `@sha256:<digest>` 形式
  - `mounts: list[MountSpec]` — 调用方组装的挂载清单
  - `network: bool = True` — True 走 newbee_skill_net，False 走 none
  - `timeout_seconds: int = 60` — 调用方可收紧，不可放宽
  - `env: dict[str, str] = {}` — 白名单键值对
  - `run_id: str` — 由调用方生成，用于日志追踪
- **输出**：`ExecResult`
  - `stdout: str` — 截断后的标准输出
  - `stderr: str` — 截断后的标准错误
  - `exit_code: int` — 容器退出码
  - `duration_ms: int` — 容器运行时长
  - `truncated: bool` — stdout 或 stderr 是否被截断
  - `log_path: str` — exec.json 文件路径
- **同步/异步**：异步（docker SDK 调用 + 等容器退出）
- **错误**：所有错误转为 `SandboxError` 子类（ImageError / MountError / NetworkError / TimeoutError / OOMError / ExecError），不抛原始 docker 异常

#### CacheVolumeManager.prune()

- **调用方**：控制面板 API（"清缓存"）
- **语义**：清空所有依赖缓存 volume
- **副作用**：删除并重建 `newbee_skill_cache_pip / _npm / _bun`

#### SandboxExecutor.shutdown()

- **调用方**：backend 生命周期管理
- **语义**：优雅停止——停止受理新请求、等待进行中容器结束
- **副作用**：限时等待后强杀超时容器

### 3.2 内部组件接口（供架构理解，外部不调用）

- `ImageGuard.validate(image: str) -> None` — 校验镜像白名单
- `NetworkGuard.normalize(network: bool) -> str` — 规范化网络模式
- `MountValidator.validate(mounts: list[MountSpec]) -> list[MountSpec]` — 校验并注入缓存 volume
- `HardenedContainerRunner.run(request, mounts, network_mode) -> ContainerResult` — 真正启容器
- `OutputCollector.stream(...) -> OutputResult` — 截断与落盘
- `CacheVolumeManager.ensure_volumes() -> None` — 确保 volumes 存在

---

## 四、Data Ownership & Responsibility（数据归属与责任）

### 数据创建责任

| 数据 | 创建者 | 说明 |
|------|--------|------|
| `ExecResult` | sandbox (SandboxExecutor) | 唯一生产者 |
| `exec.json` | sandbox (exec 完成后写入) | 结构化运行日志 |
| `stdout.log` / `stderr.log` | sandbox (OutputCollector) | 完整输出落盘，权限 600 |
| `newbee_skill_cache_*` volumes | 运维层 / CacheVolumeManager.ensure | sandbox 启动时确保存在 |
| `run_id` 与 `tmp/skill-runs/<run_id>/` | core/tools/Bash | sandbox 只挂载，不创建 |

### 数据更新与销毁责任

| 数据 | 责任模块 | 说明 |
|------|----------|------|
| cache volume 内容 | 独立 cache-writer 容器 | skill 容器不写入缓存 volume |
| overflow log（tmp/skill-runs/） | 独立清理任务 | 48h TTL，不在 sandbox 模块 |
| 容器（僵尸清理） | sandbox (docker --rm) | 正常退出自动清理；daemon 中途消失的孤儿由下次启动尝试清理 |

### 当前模块不负责的数据

| 数据 | 责任模块 | 说明 |
|------|----------|------|
| skill 目录（configs/skills/） | skills 模块 | sandbox 只挂载 |
| run_dir 创建 | core/tools/Bash | sandbox 只挂载 |
| 命令内容安全检查 | policy (DangerousCommandMatcher) | sandbox 不做字面量检查 |
| 权限决策 | policy + permission | sandbox 被调用=决策已通过 |
| 镜像构建 | CI + docker/ 目录 | sandbox 只 docker pull |
| `newbee_skill_net` 创建 | 运维层 / 启动探针 | sandbox 只使用 |

---

## 五、与其他模块 dfd-interface 的交叉引用

| 本文档描述的流向 | 对应模块文档 | 衔接点 |
|------------------|-------------|--------|
| ExecRequest 由 Bash 工具传入 | core/tools | Bash 在 policy+permission 允许后创建 run_dir、调用 exec() |
| mounts 中 skill_dir 由 skills 模块提供 | [skills/dfd-interface.md](../skills/dfd-interface.md) | skills 管理 configs/skills/<name>/ |
| env / command 的安全检查在 policy 完成 | [policy/dfd-interface.md](../policy/dfd-interface.md) | policy.D4 危险命令识别 |

---

## 六、自检清单

- [x] 可以清楚说明每条数据从哪里来、到哪里去（Bash → ExecRequest → ImageGuard → NetworkGuard → MountValidator → ContainerRunner → OutputCollector → ExecResult → Bash）
- [x] 所有接口都服务于明确的数据流（exec 是唯一核心入口，prune/shutdown 服务于维护）
- [x] 不存在数据责任不清或重复处理的风险（sandbox 不创建 run_dir、不管理 skill 目录、不做安全决策）
- [x] 与 goals-duty.md 的 Non-Duties 一致（不决策、不管存储、不创建 run_dir、不解析命令、不走 DB）
- [x] 与 architecture.md 的子组件划分一致（SandboxExecutor 编排 ImageGuard / NetworkGuard / MountValidator / HardenedContainerRunner / OutputCollector / CacheVolumeManager）
