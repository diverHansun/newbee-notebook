# sandbox 模块 architecture.md

本文档描述 `newbee_notebook/core/sandbox/` 模块的内部结构与设计选择。设计严格服从 [goals-duty.md](goals-duty.md)：A3 生命周期（每次启停 + named volume `:ro` 缓存）、host 强制 `:ro`、网络隔离（`newbee_skill_net`，不可达 compose sibling）、容器硬化（非 root + cap-drop 等）、镜像白名单 by digest、argv-only、env 白名单。

---

## 一、Architecture Overview（总体架构）

sandbox 模块由七个子组件组成，职责按"请求路径"自上而下排列：

1. **SandboxExecutor（对外门面）** — 暴露 `exec()` 接口；编排其余子组件，最终返回 `ExecResult`。
2. **MountValidator（挂载校验层）** — 校验挂载清单：host 路径一律 `:ro`、缓存 volume 一律 `:ro`、路径归属允许根目录、禁止 symlink 逃逸、禁止 `..`。
3. **ImageGuard（镜像白名单层）** — 仅允许以 `@sha256:<digest>` 形式引用的预构建镜像，拒绝可变 tag（`:latest` / `:*`）。
4. **NetworkGuard（网络隔离层）** — 强制使用 `newbee_skill_net` 或 `none`；任何访问 compose 默认网络的请求直接拒绝。启动探针负责确保 `newbee_skill_net` 存在。
5. **HardenedContainerRunner（硬化容器编排）** — 拼装所有硬化 flags（`--user 1000:1000`、`--cap-drop=ALL`、`--security-opt=no-new-privileges`、`--read-only`、`--tmpfs`、`--pids-limit`、`--cpus`、`--memory`），`docker run --rm` 启动，管理超时/kill/回收。
6. **CacheVolumeManager（缓存 volume 维护）** — 启动时确保 `newbee_skill_cache_pip / _npm / _bun` 存在；**暴露给 skill 容器仅 `:ro`**；写入由独立的 cache-writer 容器完成（见下）。
7. **OutputCollector（输出截断与回流）** — 截断 stdout/stderr 超阈值部分、落盘 overflow log、产出结构化 `exec.json`。

### 内部依赖

```
SandboxExecutor
├── ImageGuard            （校验 image@digest 属于白名单）
├── MountValidator        （校验 mounts；注入 cache volume ro 条目）
├── NetworkGuard          （规范化 network 参数 → newbee_skill_net / none）
├── HardenedContainerRunner（真正启容器 + 等退出 + kill/回收）
│   └── OutputCollector   （截断 + 落盘）
└── CacheVolumeManager    （启动时保证 volumes 存在；清理接口）
```

### 执行路径（高层）

1. 调用方 `SandboxExecutor.exec(ExecRequest)`
2. ImageGuard 校验 image 名（必须 `@sha256:` 形式）
3. NetworkGuard 规范化 network 参数
4. MountValidator 校验 mounts（host `:ro`、缓存 `:ro`）
5. HardenedContainerRunner 拼 docker flags 启容器
6. OutputCollector 流式读 stdout/stderr，超阈值截断 + 落盘
7. 容器退出或超时 → kill + 清理
8. 返回 `ExecResult`

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. Facade — SandboxExecutor

对 Bash 工具单一入口，屏蔽 docker 概念。服务于 goals-duty **G1**。

### 2. Guard Clause — MountValidator / ImageGuard / NetworkGuard

三层前置校验全是纯函数，失败立即返回错误、不产生 docker side effect。便于单测。服务于 goals-duty **G3 / G4 / G7**。

### 3. Immutable Hardening — HardenedContainerRunner

**硬化 flags 写死在代码里**，不可被调用方参数覆盖放宽。调用方只能传更严格的值（更短 timeout、更低 memory）。codex 明确指出"sandbox 边界取决于 flags 完美无误"，代码固化比配置化更可靠。服务于 goals-duty **G5**。

### 4. One-Way Cache — CacheVolumeManager

codex P1 指出可写缓存 volume 会被恶意 skill 污染，影响后续 skill。**设计**：缓存 volume 对 skill 容器**永远 `:ro`**；写入由独立的 `newbee-skill-cache-writer` 容器在 newbee 启动时/用户点"刷新缓存"时运行，该 writer 容器不执行用户代码、只装依赖。服务于 goals-duty **G2 + G6 + D5**。

### 5. argv-only — ExecRequest.command: list[str]

接口层禁止 shell 字符串。codex 指出字面量注入无法穷举防御，消除问题的办法是**不让 shell 参与**。调用方必须自己拆 argv。服务于 goals-duty **G8**。

### 6. env allowlist — HardenedContainerRunner

默认不透传 host env；调用方显式传白名单键值；黑名单拦截逃逸向量（`LD_PRELOAD` / `PYTHONPATH` / `NODE_OPTIONS` 等）。服务于 goals-duty **G9**。

### 7. 未抽 `SandboxBackend` 协议

只支持 docker。codex 同意 YAGNI。**代价**：未来切 podman / k8s 需重构，但目前无此需求。

### 8. 未使用 Worker Pool / Pre-warm Container

坚持 A3。服务于 goals-duty **G2 + N7**。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

```
newbee_notebook/core/sandbox/
├── __init__.py                     # 对外导出 SandboxExecutor / ExecRequest / ExecResult / SandboxError 层级
├── executor.py                     # SandboxExecutor（Facade）
├── image_guard.py                  # ImageGuard + digest 白名单常量
├── mount_validator.py              # MountValidator（host :ro / cache :ro / path 归属）
├── network_guard.py                # NetworkGuard（newbee_skill_net / none 两选一）
├── container_runner.py             # HardenedContainerRunner（拼 docker flags）
├── cache_volume.py                 # CacheVolumeManager（volume 存在性 + 清理接口）
├── output_collector.py             # OutputCollector（截断 + 落盘）
├── errors.py                       # SandboxError / ImageError / MountError / NetworkError / TimeoutError / OOMError / ExecError
└── contracts.py                    # ExecRequest / ExecResult / MountSpec / ResourceLimits 数据类

configs/sandbox/
└── images.lock                     # 白名单 digest 清单（随 newbee 版本发布）

docker/
└── skill-runtime/
    ├── Dockerfile                  # 构建 newbee-skill-runtime:<digest>
    └── cache-writer.Dockerfile     # 构建 newbee-skill-cache-writer（装依赖的 writer 容器）
```

### 稳定接口 vs 内部实现

- **对外稳定**：`SandboxExecutor.exec`、`CacheVolumeManager.prune()`、`contracts.py` 数据类、`errors.py` 异常层级
- **内部可演化**：docker SDK vs docker CLI、output 截断阈值、log 格式

### errors.py 分级

- `SandboxError`（基类）
- `ImageError`（镜像白名单拒绝、digest 不匹配）
- `MountError`（路径违规）
- `NetworkError`（`newbee_skill_net` 不存在）
- `TimeoutError` / `OOMError` / `ExecError`（容器级失败）

调用方（Bash 工具）可按类型映射到不同 tool error 反馈给 mellow。

### 不包含的子组件

- **docker daemon 可用性探测**：由 newbee 启动脚本完成
- **skill 目录与 run_dir 的创建**：由 skills / Bash 工具负责；sandbox 只挂不 mkdir
- **`newbee_skill_net` 的创建**：由运维层或 newbee 启动探针；sandbox 只使用
- **cache-writer 容器编排**：独立启动脚本；sandbox 不管理其生命周期
- **权限/决策逻辑**：不在本模块

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 放弃方案：默认加入 compose 网络

被放弃是因为 skill 将直接可达 postgres / backend / elasticsearch，绕过 policy/permission 与审计。**代价**：skill 若需要访问业务数据，必须由 mellow 先拉取到 `/work/in/` 再喂给脚本；这是正确的信任边界。

### 放弃方案：允许 host 路径 `:rw`

硬性放弃。**代价**：skill 不能直接把生成物写回 host 某用户路径（如桌面）；未来若要支持，走独立工具（sandbox→`/work/out/`→mellow 读→经显式 file_export 工具写 host），不破坏 sandbox 边界。

### 放弃方案：可变 tag 镜像白名单

`python:*` / `latest` 被拒绝。**代价**：新镜像版本需要在 `configs/sandbox/images.lock` 更新 digest 并随版本发布；但这是供应链安全的必要成本。

### 放弃方案：运行时 docker pull 兜底

codex 指出运行时 pull 会挂/失败不可预测。**改为**：newbee 启动时预热所有白名单镜像（cache-writer 容器负责）；运行时拒绝拉取未缓存镜像。**代价**：部署流程多一步；但冷启动变快、失败可预测。

### 放弃方案：可写缓存 volume

详见 Design Pattern #4。**代价**：缓存更新需要独立 writer 容器；但对供应链安全的收益巨大。

### 放弃方案：shell 字符串 command

argv-only。调用方拆分命令。**代价**：管道/重定向需要 wrapper script 或多次调用；但消除注入面。

### 放弃方案：env 默认透传

白名单 + 黑名单双保险。**代价**：skill 脚本不能依赖 host 环境变量（比如 `$HOME` 实际指向容器内）；但这才是沙箱本意。

### 妥协：overflow log 48 小时 TTL

log 可能含 secrets。未来升级加密或缩短 TTL，但不是 v1 范围。

### 可演进性

- 未来 GPU 支持：ImageGuard 白名单扩 `nvidia/cuda@sha256:...`，ContainerRunner 加 `--gpus`
- 未来远程 docker：ContainerRunner 读 `DOCKER_HOST`
- 未来 skill 间共享工作区：独立 namespaced volume 类型，不影响 pip/npm cache
- 未来替换 docker：抽 `SandboxBackend` 协议，把当前实现拆成 `DockerBackend`
