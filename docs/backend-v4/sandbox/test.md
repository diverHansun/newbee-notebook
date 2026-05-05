# sandbox 模块 test.md

本文档说明如何验证 `newbee_notebook/core/sandbox/` 模块在真实协作环境中的正确性。设计基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md)、[dfd-interface.md](dfd-interface.md)。

sandbox 是一个**混合原型模块**：前置校验层（ImageGuard / NetworkGuard / MountValidator）是纯逻辑子组件；容器编排层（HardenedContainerRunner）是外部依赖封装（docker daemon）；整体对外接口（SandboxExecutor）对外表现为桥接/适配。

---

## 一、Module Test Profile（模块测试档案）

- **模块原型**：混合原型（桥接/适配 + 外部依赖封装 + 纯逻辑子组件）
- **主要测试类型**：
  - 前置校验层：unit
  - 容器编排层：contract（docker daemon mock 边界）
  - 整体 exec 流程：integration
- **Mock 边界**：
  - docker SDK（docker-py）：integration 用真实 daemon 或 mock；unit 用 mock 验证调用参数
  - 文件系统 `tmp/skill-runs/` / `configs/skills/`：unit 用 tmp_path fixture；integration 用真实路径
  - 外部模块（Bash 工具）：不 mock（sandbox 的调用方在集成测试中用真实调用）
- **测试归属目录**：`tests/unit/core/sandbox/` + `tests/integration/core/sandbox/` + `tests/contract/core/sandbox/`

---

## 二、Test Scope（测试范围）

### 覆盖

#### 纯逻辑子组件（unit test 侧重）

- ImageGuard：镜像白名单校验（digest 形式、白名单匹配、拒绝可变 tag）
- NetworkGuard：network 参数规范化（True → newbee_skill_net，False → none，拒绝 compose 默认网络）
- MountValidator：挂载校验（host :ro 强制、缓存 :ro 对 skill 容器、路径归属、.. 与 symlink 拒绝、自动注入缓存 volume）
- OutputCollector：截断逻辑（阈值精确性、truncated flag、落盘格式）

#### 容器编排层（contract test 侧重）

- HardenedContainerRunner：docker flags 完整拼装（硬化 flags 不可被参数覆盖放宽、command 以 argv 传入不经 shell、env 白名单与黑名单、超时强杀、OOM 检测）
- SandboxExecutor.exec()：ExecRequest → ExecResult 的契约（输入字段验证、输出字段完整性、错误映射为 SandboxError 子类而非原始 docker 异常）

#### 整体集成

- 端到端 exec 流程：镜像校验 → 网络规范化 → 挂载校验 → 容器启停 → 输出收集 → ExecResult
- CacheVolumeManager：volume 存在性保障与清理

### 不覆盖

- Bash 工具如何决定调用 sandbox（属于 core/tools 测试范围）
- run_id 与 run_dir 的创建（属于 Bash 工具测试范围）
- skill 目录的创建与维护（属于 skills 测试范围）
- docker daemon 可用性探测（属于运维层/启动脚本）
- `newbee_skill_net` 的创建（属于运维层/启动探针）
- cache-writer 容器的预热逻辑（独立组件）
- 48h 日志清理任务（独立定时任务，不在本模块）

---

## 三、Critical Scenarios（关键场景）

### 前置校验层（纯逻辑，unit test）

| # | 场景 | 预期结果 |
|---|------|---------|
| 1 | image 为 `newbee-skill-runtime@sha256:<digest>` | ImageGuard 放行 |
| 2 | image 为 `python:latest`（可变 tag） | ImageError，拒绝 |
| 3 | image 为 `python:*`（通配 tag） | ImageError，拒绝 |
| 4 | image 为 `python@sha256:<digest>` 不在白名单 | ImageError |
| 5 | network=True → 返回 "newbee_skill_net" | NetworkGuard 放行 |
| 6 | network=False → 返回 "none" | NetworkGuard 放行 |
| 7 | network 请求 compose 默认网络 | NetworkError，拒绝 |
| 8 | mount 中 host 路径声明 :rw | MountError，拒绝 |
| 9 | mount 中缓存 volume 对 skill 容器声明 :rw | MountError，拒绝 |
| 10 | mount 中路径含 `..` | MountError，拒绝 |
| 11 | mount 中路径经 symlink 逃逸到允许根目录外 | MountError，拒绝 |
| 12 | mount 清单不含缓存 volume | 自动注入 pip/npm/bun 三个 `:ro` 条目 |
| 13 | 正常 mount（skill_dir :ro + run_dir :rw） | MountValidator 放行，返回完整挂载清单 |
| 14 | OutputCollector 收集 ≤ 256KB | truncated=False，完整输出在 ExecResult |
| 15 | OutputCollector 收集 > 256KB | truncated=True，截断输出在 ExecResult，完整输出落盘 |

### 容器编排层（contract test）

| # | 场景 | 预期结果 |
|---|------|---------|
| 16 | exec 成功（exit_code=0） | ExecResult(exit_code=0, stdout=..., stderr=..., truncated=False) |
| 17 | exec 失败（exit_code!=0） | 仍返回 ExecResult（exit_code 非零），不抛异常 |
| 18 | command 以 argv 形式传入（不经 shell） | docker run cmd 参数无 `sh -c` 包裹 |
| 19 | 硬化 flags 完整拼装 | `--user 1000:1000`、`--cap-drop=ALL`、`--security-opt=no-new-privileges`、`--read-only`、`--tmpfs /tmp:rw,noexec,nosuid,size=64m`、`--pids-limit=128`、`--cpus=1`、`--memory=512m`、`--memory-swap=512m` 全部在 docker run 参数中 |
| 20 | 调用方不能覆盖硬化 flags | 即使 ExecRequest 无对应字段，硬化 flags 仍生效（代码固化） |
| 21 | 容器超时 | TimeoutError + docker kill 被调用 |
| 22 | 容器 OOM | OOMError + resource_peak 被记录 |
| 23 | docker daemon 不可达 | SandboxUnavailable（或 ExecError），不抛原始 docker 异常 |
| 24 | env 白名单透传正常键值 | `env={"MY_VAR": "hello"}` 出现在容器 env 中 |
| 25 | env 含黑名单键（LD_PRELOAD） | ExecRequestError，不启容器 |

### 集成测试

| # | 场景 | 预期结果 |
|---|------|---------|
| 26 | 完整 exec 流程：echo hello | exit_code=0, stdout="hello\n" |
| 27 | 完整 exec 流程：写文件到 /work | exit_code=0，文件写入 /work 成功 |
| 28 | /work 内容在容器销毁后调用方可见（在 run_dir） | Bash 工具可读 run_dir 中的输出文件 |
| 29 | 安全测试：容器内 `cat /etc/shadow` | 失败或被拒绝（--read-only + 非 root 用户） |
| 30 | 安全测试：容器内 `ping postgres`（compose sibling） | 失败（newbee_skill_net 不可达 compose 内部） |
| 31 | 安全测试：容器内 `mount` / `chmod` | 失败（--security-opt=no-new-privileges） |
| 32 | CacheVolumeManager.ensure_volumes：初启创建 | 不存在的 volume 被 docker volume create |
| 33 | CacheVolumeManager.prune：清缓存 | 删除并重建三个 cache volume |

### 生命周期与日志

| # | 场景 | 预期结果 |
|---|------|---------|
| 34 | 优雅关闭：SIGTERM 后停止受理新 exec | `shutdown()` 后调用 `exec()` 返回 ExecError |
| 35 | 优雅关闭：等待进行中容器结束 | `shutdown()` 后已启动的容器仍正常运行至结束再回收 |
| 36 | 优雅关闭：超时强杀 | 容器运行超过 5s 宽限期后被 docker kill |
| 37 | exec.json 落盘内容完整性 | 文件含 run_id / image@digest / argv_hash / duration_ms / exit_code / resource_peak / mounts / network_mode / error_class 全部字段 |
| 38 | exec.json 落盘权限 | 文件权限为 600（仅 owner 可读写） |

---

## 四、Contract Specification（契约规约）

### SandboxExecutor.exec() 对内承诺

- **输入约束**：`command` 必须是 `list[str]`；`image` 必须为 `@sha256:<digest>` 形式且在 images.lock 白名单中；`mounts` 中 host 路径必须 `:ro`；`env` 不含黑名单键；`timeout_seconds` 调用方只能收紧不可放宽
- **输出承诺**：永远返回 `ExecResult` 或抛出 `SandboxError` 子类，不透传 docker SDK 原生异常
- **错误码语义**：

| 错误类型 | 触发条件 | 是否产生 docker side effect |
|---------|---------|--------------------------|
| ImageError | 镜像非白名单/非 digest 形式 | 否 |
| MountError | 挂载校验失败 | 否 |
| NetworkError | 网络模式非法或 newbee_skill_net 不存在 | 否 |
| ExecRequestError | command 非 list / env 含黑名单 | 否 |
| TimeoutError | 容器超时 | 是（容器被 kill） |
| OOMError | 容器 OOM | 是（容器已退出） |
| ExecError | 其他容器级失败 | 可能（容器已启动） |
| SandboxUnavailable | docker daemon 不可达 | 否 |

- **资源限制不可放宽**：调用方只能传更严格的 timeout_seconds（≤ 60）和 env 白名单的子集，硬化 flags 完全不可覆盖
- **容器生命周期不可控**：调用方不能控制容器复用（每次 exec 启停）、不能获取容器 ID、不能挂 docker socket

### Error 层级稳定承诺

`SandboxError` 层级对外稳定：新增错误子类不破坏现有调用方的 catch 逻辑；现有子类不删除、不重命名。

---

## 五、Integration Points（集成点测试）

| 集成点 | 测试类型 | 验证重点 |
|--------|---------|---------|
| Bash 工具 → SandboxExecutor.exec() | integration | ExecRequest 字段完整传入；ExecResult 正确解析为 ToolCallResult |
| SandboxExecutor → docker daemon | integration | 容器成功启停；硬化 flags 生效；网络模式正确 |
| SandboxExecutor → 文件系统（tmp/skill-runs/） | integration | exec.json 写入；stdout.log/stderr.log 落盘且权限 600 |
| CacheVolumeManager → docker daemon | integration | volume 创建/存在性检查/清理 |
| SandboxExecutor → newbee_skill_net | integration | 容器内可出外网（curl https://example.com），不可达 compose sibling（ping postgres 失败） |

---

## 六、Verification Strategy（验证策略）

### 执行环境

- unit 测试：纯 Python，无需 docker（前置校验层全部可单测）
- contract 测试：需要 docker daemon（或 mock docker SDK）验证容器编排参数
- integration 测试：需要 docker daemon + `newbee_skill_net` + 预构建的 `newbee-skill-runtime` 镜像
- CI 环境：docker-in-docker 或宿主机 docker socket

### 测试组织

```
tests/unit/core/sandbox/
├── test_image_guard.py              # ImageGuard 白名单/拒绝矩阵
├── test_network_guard.py            # NetworkGuard 模式规范化
├── test_mount_validator.py          # MountValidator 校验规则 + 缓存注入
├── test_output_collector.py         # OutputCollector 截断阈值与落盘
└── test_contracts.py                # ExecRequest/ExecResult 字段验证

tests/contract/core/sandbox/
├── test_exec_contract.py            # exec() 的输入输出契约（含错误映射）
└── test_hardened_flags.py           # 硬化 flags 不可覆盖

tests/integration/core/sandbox/
├── test_exec_flow.py                # 端到端 exec 流程
├── test_security_enforcement.py     # 安全测试（容器内 cat /etc/shadow、ping postgres 等）
└── test_cache_volume.py             # CacheVolumeManager ensure/prune
```

### 关键测试模式

- **前置校验参数化**：ImageGuard 白名单/拒绝矩阵用 parametrize 覆盖所有镜像变体
- **硬化 flags 不可覆盖**：mock docker SDK 的 `containers.run()`，断言传入参数固定包含所有硬化 flags
- **安全测试**：真实启动容器，执行攻击命令（cat /etc/shadow、ping postgres、mount、chmod），断言全部失败
- **错误不透传**：mock docker SDK 抛 `docker.errors.DockerException`，断言 SandboxExecutor 转为 `ExecError` 而非透传
- **argv-only**：验证 docker run 参数不含 `sh` `-c` 等 shell 包装
