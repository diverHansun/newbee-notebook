# policy 模块 architecture.md

本文档描述 `newbee_notebook/core/policy/` 模块的内部结构与设计选择。设计严格服从 [goals-duty.md](goals-duty.md)：仅服务 agent 模式、纯决策、不读 DB、不调 permission、独占 capability_signature 生成、两档 policy（default / yolo）。

---

## 一、Architecture Overview（总体架构）

policy 模块由五个子组件协作完成"agent 模式下的纯决策裁定 + capability_signature 生成"：

1. **PolicyDecider（对外门面）** — 暴露 `decide()` 接口；编排其余子组件，最终输出 `Decision`（含 verdict 与 signature）。
2. **SessionPolicyState（会话档位状态）** — 每个 session_id 维护当前 agent policy 档位（`default` / `yolo`），提供 `get_policy / set_policy`。
3. **DecisionMatrix（决策矩阵）** — 静态查表：`(agent_policy, tool_class, risk_level) → verdict ∈ {ALLOW, ASK}`。纯函数，可单测。矩阵中**不产出 DENY**——DENY 只由 agent_loop 在用户拒绝时构造。
4. **DangerousCommandMatcher（危险命令识别器）** — 仅对 tool_class=bash 的调用走一次字面量模式匹配，命中则把 risk_level 升级为 `dangerous`。作为 UX 风险标签，不做安全栅栏。
5. **SignatureBuilder（签名构造器）** — 按固定格式 `{scope}:{tool}:{arg_hash8}` 生成 capability_signature；scope 在 skill 上下文时为 `skill:<name>@<content_hash>`，否则为 `global`。

### 职责划分与调用栈

```
PolicyDecider.decide(request)
├── SessionPolicyState.get(session_id)               → agent_policy
├── DangerousCommandMatcher.maybe_upgrade(tool_name, args)  → risk_level
├── DecisionMatrix.lookup(agent_policy, tool_class, risk_level)
│                                                    → verdict ∈ {ALLOW, ASK}
└── SignatureBuilder.build(tool_name, args, skill_context)
                                                     → capability_signature
  ▼
Decision(verdict, capability_signature, reason)
```

### 决策路径（高层）

1. PolicyDecider 接收 `DecideRequest`（含 agent_policy 来源于 SessionPolicyState 或入参、tool_class、risk_level、tool_name、tool_args、skill_context）
2. 若 yolo → 直接 `ALLOW`，仍构造 signature（permission 后续会用）
3. 若 default 且 tool_class==bash → DangerousCommandMatcher 升级 risk_level
4. 查 DecisionMatrix 得 verdict（ALLOW or ASK）
5. SignatureBuilder 构造 signature
6. 返回 `Decision(verdict, signature, reason)`

**不做的事**：不调 permission、不读 DB、不查已批准缓存（那是 permission 的事）。

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. Pure Function Core — PolicyDecider.decide

决策纯函数化，无 IO。理由：
- 便于单测覆盖矩阵（2 档 × 6 tool_class × 3 risk_level ≈ 36 个 cell）
- 便于回放调试——拿到 DecideRequest 就能复现
- 消除 codex 指出的"decide 又返 ASK 又调 permission 又读 DB"的边界模糊

服务于 goals-duty 的 **G1（决策纯净）**。

### 2. Strategy — 两档 agent policy 分文件矩阵

default 与 yolo 两档矩阵分别放 `matrix/default.py` 与 `matrix/yolo.py`。服务于 goals-duty 的 **G2**。

### 3. Static Dispatch Table（查表决策）

DecisionMatrix 以 `dict[(tool_class, risk_level), verdict]` 形式固化每档矩阵。查表的好处：
- 增删 cell 仅改表
- 修改不改代码路径
- 覆盖测试就是枚举所有 key

### 4. Extension Point — DangerousCommandMatcher

不在 ToolDefinition 里声明"哪些 Bash 命令危险"——Bash 是通用工具，不知道具体命令。危险识别由 policy 内部模式表完成。**明确定位为 UX 标签**，不是安全栅栏（安全由 sandbox 保证）。服务于 goals-duty 的 **G4** 与 **D4**。

### 5. Ownership — SignatureBuilder 独占

signature 生成的归属问题是 codex 明确指出的 P1。这里的设计决定：**policy 独占**。
- skills 模块只提供 `(skill_name, content_hash)`，不拼字符串
- sandbox 模块根本不看 signature
- permission 模块只用 signature 做字典 key，不解析、不重写

格式 `{scope}:{tool}:{arg_hash8}`，稳定可复现。服务于 goals-duty 的 **G5 / D5**。

### 6. 未使用 Observer 模式

policy 档位切换发 SSE 是**出站单向事件**，不等待订阅者反馈。permission 写入 DB 对 policy 无影响（policy 不读 DB）。

### 7. 未使用 Chain of Responsibility

决策链条短（档位 → 危险命令匹配 → 矩阵查表 → signature 构造），一趟过完。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

```
newbee_notebook/core/policy/
├── __init__.py                     # 对外导出 PolicyDecider、AgentPolicy 枚举、ToolClass 枚举
├── decider.py                      # PolicyDecider（对外门面，纯函数 decide）
├── session_state.py                # SessionPolicyState（档位 dict + SSE 事件发出）
├── matrix/
│   ├── __init__.py                 # 导出 lookup(agent_policy, tool_class, risk_level)
│   ├── default.py                  # default 档决策矩阵
│   └── yolo.py                     # yolo 档决策矩阵
├── dangerous_commands.py           # DangerousCommandMatcher + 模式表
├── signature_builder.py            # SignatureBuilder
└── contracts.py                    # DecideRequest / Decision / SkillContext / AgentPolicy / ToolClass / RiskLevel
```

### 稳定接口 vs 内部实现

- **对外稳定**：`PolicyDecider.decide(DecideRequest) -> Decision`、`SessionPolicyState.get/set`、`contracts.py` 中数据类与枚举
- **内部可演化**：矩阵表内容、危险命令模式表、signature arg_hash 的规范化细节

### matrix/ 分文件说明

每档一个文件。阅读时聚焦"这一档长什么样"；新增档位（如未来 `paranoid`）= 新增文件。

### 不包含的子组件

- **永久允许记录查询**：在 permission 模块
- **confirmation gateway / SSE 卡片**：在 permission 模块
- **tool_class 与 risk_level 的声明**：在 ToolDefinition（core/tools）
- **skill content_hash 计算**：在 skills 模块

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 放弃方案：policy 读 DB

之前的设计让 policy 每次 decide 查 DB 白名单。codex 指出这与 permission 职责重叠。**改为 policy 完全不读 DB**，由 permission 独占。
**代价**：agent_loop 多一次"ASK 路径上先调 permission 看是否已允许"的跳转；但 permission 本就要承担这次查询，无新增开销。

### 放弃方案：policy 调 permission.request()

之前 decide 内部会直接 `await permission.request(...)`，这让 decide 变成 async、阻塞、UI 感知。codex 明确反对。**改为 decide 只返 ASK，由 agent_loop 调 permission**。
**代价**：agent_loop 逻辑多一步；但逻辑更清晰、可测。

### 放弃方案：policy 产出 DENY

DENY 只由 agent_loop 在用户拒绝时产出。policy 矩阵只有 ALLOW/ASK 两种 cell。
**代价**：DENY 的来源单一化；但调试路径更清晰。

### 放弃方案：ToolDefinition 直接声明"危险命令"

Bash 工具不知道命令字符串内容。危险命令表集中在 policy。
**代价**：policy 模块多一张表；但这是决策维度的合理归属。

### 妥协：档位不跨会话

每个新 session 默认 `default`。yolo 有风险，需用户显式选择。未来可加"记住我的选择"写 DB，但不是当前范围。

### 可演进性

- 新增档位 `paranoid`：加 `matrix/paranoid.py`，其余不动
- 新增 tool_class `mcp`：加入枚举 + 各档矩阵补一行
- 引入用户自定义危险命令：`dangerous_commands.py` 多查一次 DB（但 policy 仍不持连接，从入参接 session）
