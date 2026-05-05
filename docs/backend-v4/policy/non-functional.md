# policy 模块 non-functional.md

本文档说明 policy 模块在功能正确性之外必须满足的工程约束。设计基于 [goals-duty.md](goals-duty.md) 与 [architecture.md](architecture.md)。

policy 处于 agent_loop 工具调用链的**决策节点**，每次工具执行前被调用。它是纯函数模块——唯一的非功能约束就是**保持纯函数性质不被侵蚀**。

---

## 一、Quality Priorities（质量优先级）

按优先级从高到低：

1. **纯函数保证 > 一切**
   `decide()` 必须保持无 IO、无副作用、无异步。任何"为了方便"引入 DB 查询、SSE 推送、permission 调用都会破坏其可测试性与可回放性。这是 architecture.md 中明确的设计决策（见 Design Pattern #1），必须在工程层面被强制遵守。

2. **决策确定性 > 灵活性**
   同一输入永远产生同一输出。不引入时间戳、随机数、计数器等非确定性因素进入决策路径。

3. **内存占用 < 决策速度**
   单次 `decide()` 调用应在微秒级完成（纯内存查表 + 字符串拼接），不作为 agent_loop 的工具调用延迟瓶颈。

4. **可测试性 > 代码复用性**
   宁可 matrix 表以简单 dict 形式存在，也不引入需要 mock 的抽象层。纯函数天然可并发测试，不因重构而引入锁或共享状态。

---

## 二、Operational Constraints（运行约束）

### 调用频次

- agent_loop 每个 turn 可能调数十次 `decide()`（每次工具调用前）
- 与工具调用频率 1:1 对应，不构成独立瓶颈

### 延迟

- 单次 `decide()` 调用：纯内存操作，目标 < 100us p99
- 包含 signature 构造（SHA-256 计算）在内仍应在纯 CPU 范围内，不依赖外部服务

### 资源占用

- 进程内存：决策矩阵（两档 dict，约 36 个 cell）+ 危险命令模式表（约 20 条正则/字符串）+ SessionPolicyState（每 session 一个字节）
- 不存在内存泄漏风险（SessionPolicyState 在 session 结束时由 agent_loop 或 SessionManager 触发生命周期清理）

### 外部依赖

- 无。policy 不调 DB、不调 permission、不调 sandbox、不调任何外部 API。
- 依赖模块（ToolRegistry、skills）仅通过 agent_loop 在入参中提供所需数据，不形成运行期调用依赖。

---

## 三、Reliability & Observability（可靠性与可观测性）

### 失败容忍

- `decide()` 逻辑上不应失败（纯函数，无效输入应通过入参校验在调用前被拦截）
- 若收到无效 tool_class / risk_level 枚举值：防御性抛 `PolicyError`，不放行（fail-closed）
- 若被 ask 模式误调用：防御性断言抛 `PolicyError`（见 goals-duty N7）

### 结构化日志

- 每次 `decide()` 调用记录一条 DEBUG 级别日志：
  - `session_id`、`agent_policy`、`tool_class`、`risk_level`、`verdict`、`signature`（脱敏：仅 scope + tool 名）
- 档位切换记录 INFO 级别日志：
  - `session_id`、`old_policy`、`new_policy`

### 纯函数性质回归测试

- CI 中应有专用测试：对同一 `DecideRequest` 并发 100 次 `decide()`，断言所有结果完全一致
- 引入任何 IO/async 依赖应在 code review 阶段被 CI lint 规则拦截

---

## 四、Trade-offs & Deferred Requirements（权衡与暂缓项）

### 当前阶段不做

1. **policy 档位持久化**
   档位不跨会话保持（新 session 默认 "default"）。用户每次需显式切 yolo。
   原因：yolo 是高风险模式；跨会话记忆可能让用户忘记当前处于 yolo 而误执行危险操作。

2. **自定义决策矩阵**
   用户不能自定义"哪些工具/风险等级要 ASK"。
   原因：两档矩阵覆盖当前所有场景；用户自定义矩阵的 UX 复杂度与安全风险远大于收益。

3. **dangerous_commands 用户扩展**
   危险命令模式表仅内置，用户不能添加自定义模式。
   原因：危险命令模式表的安全边界需要审核；用户自定义可能引入误报或漏报。

4. **决策审计**
   `decide()` 的每次调用不写审计表（日志足够）。
   原因：纯函数无副作用，决策轨迹可通过入参 + 日志完全回放。

### 已接受的代价

- 两个 policy 档位的离散选择无法表达"有条件 yolo"（如"仅在当前 turn yolo")——保持简单
- signature 对 Bash command 仅取前 3 个 token 做 hash，不同命令但相同前缀会碰撞到同一签名——permission 的许可因此可能比预期更宽松，但 decision 层面不受影响（决策基于 tool_class + risk_level，signature 只影响 permission 的 "always allow" 粒度）
