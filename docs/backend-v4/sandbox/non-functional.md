# sandbox 模块 non-functional.md

本文档说明 sandbox 模块在功能正确性之外必须满足的工程约束。设计基于 [goals-duty.md](goals-duty.md) 与 [architecture.md](architecture.md)。

sandbox 是 newbee 的**信任边界**：每次执行用户/skill 提交的命令都经它启容器、挂载、限资源、限网络。它的非功能约束首要服务于"安全边界不被绕过"，其次才是冷启动延迟与资源效率。

---

## 一、Quality Priorities（质量优先级）

按优先级从高到低：

1. **三条硬性安全前提零妥协**
   host 文件系统 `:ro`、网络隔离（不可达 compose sibling）、容器硬化（非 root + cap-drop=ALL + no-new-privileges + 不挂 docker socket）。任何"为方便临时放开"的请求都拒绝——这些约束在代码中固化，不暴露为参数。

2. **镜像供应链可控 > 启动速度**
   仅允许 `@sha256:<digest>` 形式的白名单镜像；可变 tag（`:latest` / `:*`）拒绝。冷启动慢一点可以接受；偷偷拉到带后门的 `python:latest` 不可接受。

3. **失败可预测 > 失败回收效率**
   超时/OOM/磁盘爆/镜像缺失一律转为结构化错误码，不抛原始 docker 异常。容器状态强制清理（`--rm`），即便清理慢也不能留僵尸。

4. **冷启动延迟 < 可观测性**
   单次冷启动目标 ≤ 500ms（缓存命中）/ ≤ 2s（首次拉镜像后），但**不为压缩延迟而省掉日志写盘**。每次 exec 必产 `exec.json`。

5. **A3 简单性 > 缓存复用极致**
   坚决不引入 A2 长连容器。共享依赖只走 named volume `:ro`，不通过保活进程。

---

## 二、Operational Constraints（运行约束）

### 调用频次

- 每个 skill 调用产生 1 个 sandbox 容器
- mellow 单 turn 通常调 0~3 次脚本（按 Anthropic skill 典型用法）
- backend 进程并发：默认上限同时跑 N 个 sandbox 容器（N 视 host 资源决定，建议 ≤ 4），超出排队

### 延迟目标

- **冷启动**（依赖缓存命中、镜像已 pull）：≤ 500ms p95
- **首次镜像 pull**：≤ 30s（网络快）/ 失败 ≤ 60s 超时
- **稳态执行**：以脚本本身时间为主，sandbox 自身开销 ≤ 100ms（启动 + 销毁）

### 资源限制（每容器硬上限，不可放宽）

| 维度 | 限制 |
|---|---|
| CPU | 1 core |
| 内存 | 512 MB（含 swap） |
| PID 数 | 128 |
| 超时 | 60 秒（调用方可收紧） |
| `/work` 大小 | 50 MB（软配额） |
| `/tmp` (tmpfs) | 64 MB |
| 单流 stdout/stderr 截断阈值 | 256 KB |
| overflow log 单文件 | 10 MB |

### 网络

- 默认走 `newbee_skill_net`（专用 bridge），可出外网，**不可达 compose sibling**（postgres / backend / minio / elasticsearch）
- `network=False` → `--network=none`
- **永远不暴露**接入 compose 默认网络的选项

### 外部依赖稳定性

- **docker daemon 不可达** → exec 立即返回 `SandboxUnavailable`，不阻塞、不重试
- **`newbee_skill_net` 不存在** → 立即返回 `NetworkError`（启动探针应保证存在）
- **镜像拉取失败/超时** → `ImageError`
- **缓存 volume 不存在** → 启动期 `CacheVolumeManager` 创建；运行期缺失视为致命错误

### 资源占用（backend 进程）

- 不持久 docker SDK 连接池：每次 exec 用瞬时 client；避免长连导致的句柄泄漏
- log 落盘 `tmp/skill-runs/<run_id>/`，48 小时由独立清理任务回收（不在本模块）
- 缓存 volume 增长无界，由"清缓存"按钮人工触发清理

---

## 三、Reliability & Observability（可靠性与可观测性）

### 失败语义

| 失败类型 | 行为 |
|---|---|
| 镜像非白名单/digest 不匹配 | `ImageError`，不启容器，无副作用 |
| 挂载校验失败（host :rw、缓存 :rw、symlink 逃逸、`..`） | `MountError`，不启容器 |
| 网络模式非法（`compose_default`） | `NetworkError`，不启容器 |
| `command` 非 list[str] / `env` 含黑名单键 | `ExecRequestError`，不启容器 |
| 容器超时 | `TimeoutError` + 强制 kill + 资源回收 |
| OOM | `OOMError` + 资源 peak |
| 容器异常退出（exit_code ≠ 0） | 仍返回 `ExecResult`，由调用方解读（不抛异常） |
| backend 进程 SIGTERM | 停止受理新 exec；已起容器限时等待结束（≤ 5s）后强杀 |
| docker daemon 中途消失 | 当前在跑的容器 rm 失败 → 记录孤儿 ID，下次启动尝试清理 |

### 不可接受的失败

- **逃出 sandbox 边界**：容器内进程读到 host fs 任意路径、写到 host、连到 compose sibling
- **僵尸容器**：exec 返回但容器仍在跑
- **缓存污染**：用户 skill 写入了 `/root/.cache/pip` 等共享 volume（设计上 `:ro` 挂载，应不可能；若发生需立即热修复）
- **静默截断丢失数据**：log 截断了但 `truncated=False`

### 结构化日志（每次 exec 必落）

`tmp/skill-runs/<run_id>/exec.json` 写入：
- `run_id` / `image` (含 digest) / `argv_hash` (sha256(argv) 截断)
- `mounts`：清单 + 每项 ro/rw 标记
- `network_mode`：`newbee_skill_net` / `none`
- `started_at` / `duration_ms` / `exit_code`
- `resource_peak`：cpu_seconds / memory_max_bytes
- `stdout_bytes` / `stderr_bytes` / `truncated`
- `error_class` (若失败)

stdout/stderr 全文落盘 `stdout.log` / `stderr.log`，权限 `600`，单文件 ≤ 10MB，48h TTL。

### 指标（v2 预留）

- `sandbox_exec_total{outcome}`
- `sandbox_exec_duration_ms`
- `sandbox_image_pull_failures_total`
- `sandbox_oom_total`
- 容器并发数（gauge）

### 安全测试要求

- CI 必须跑硬化验证用例（容器内尝试 `cat /etc/shadow` / `ping postgres` / `chmod` / `mount` → 全部失败）
- 镜像白名单测试：`python:latest` / `python:*` / 非白名单 → 拒绝
- argv 注入测试：command 含 `;` `&&` `|` → 仍按 argv 字面执行不解析

---

## 四、Trade-offs & Deferred Requirements（权衡与暂缓项）

### 当前阶段不做

1. **GPU 支持**
   `newbee-skill-runtime` 镜像不预装 cuda/torch；ImageGuard 白名单不含 nvidia。
   原因：当前 skill 用例不需要；GPU 接入会拉高镜像 ≥ 5GB 与运维复杂度。

2. **远程 docker host / k8s 后端**
   只支持本机 docker daemon。
   原因：YAGNI；抽象 `SandboxBackend` 协议无真需求驱动。

3. **A2 长连容器复用**
   每次启停 + named volume `:ro` 缓存。
   原因：状态污染、僵尸、安全边界弱化的代价远大于冷启动节省的 500ms。

4. **完整 audit 表**
   exec.json 落盘已足够；不入 DB。
   原因：sandbox 不需要可查询的历史；大体量场景再说。

5. **跨容器共享工作区**
   每次 exec 独立 `tmp/skill-runs/<run_id>/`，不复用。
   原因：避免上次脚本残留影响下次；mellow 想跨调用传数据通过 stdin/stdout 即可。

6. **加密 overflow log**
   stdout/stderr 全文落盘是明文，可能含 secrets。
   原因：v1 接受此风险（48h TTL + 文件权限 600 控制暴露面）；v2 视需要加密或缩短 TTL。

7. **细粒度 quota（用户级总配额）**
   每容器有硬上限，但不限"某用户/某 skill 一天总共能消耗多少 CPU/内存"。
   原因：单用户假设下不必要；多用户场景再做。

### 已接受的代价

- 冷启动 ~500ms → 用户偶尔感知"卡一下"，可接受
- 缓存 volume 写入需独立 cache-writer 容器 → 部署多一步，但供应链安全收益大
- 镜像 digest pin → 升级镜像需改 `images.lock` 并发版本，但消除供应链漂移
- argv-only → 调用方不能用 shell 特性（管道/重定向），需 wrapper script，但消除注入面
- 网络隔离 → skill 不能读 newbee 业务数据，必须由 mellow 中转，但维持信任边界
