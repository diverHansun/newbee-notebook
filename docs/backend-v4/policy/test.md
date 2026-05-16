# policy 模块 test.md

本文档说明如何验证 `newbee_notebook/core/policy/` 模块在真实协作环境中的正确性。设计基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md)、[dfd-interface.md](dfd-interface.md)。

---

## 一、Module Test Profile（模块测试档案）

- **模块原型**：纯逻辑模块
- **主要测试类型**：unit
- **Mock 边界**：无外部依赖（`decide()` 是纯函数）；SessionPolicyState 的 SSE 事件发出使用 mock event emitter 验证
- **测试归属目录**：`tests/unit/core/policy/`

---

## 二、Test Scope（测试范围）

### 覆盖

- `PolicyDecider.decide()` 的决策矩阵覆盖（2 档 x 7 条 default 规则 + yolo 通配规则，含所有已定义 cell 与未定义 cell 的兜底行为）
- `SignatureBuilder.build()` 的签名格式稳定性与规范性
- `DangerousCommandMatcher` 的危险命令模式匹配规则
- `DecisionMatrix` 查表的静态正确性（default 与 yolo 两档分别验证）
- `SessionPolicyState.get/set` 的读写与默认值行为
- yolo 档位的快速路径（短路逻辑，不调危险匹配也不查矩阵）

### 不覆盖

- agent_loop 收到 Decision 后的调度行为（属于 agent_loop 的测试范围）
- permission 如何消费 capability_signature（属于 permission 的测试范围）
- SkillContext 的构造正确性（属于 skills 的测试范围）
- ToolDefinition 中 tool_class / risk_level 字段的正确性（属于 core/tools 的测试范围）
- SSE 事件在前端的接收与渲染（属于前端测试范围）
- ask 模式下的工具过滤逻辑（属于 ChatService 的测试范围）

---

## 三、Critical Scenarios（关键场景）

### 正常路径

| # | 场景 | 输入 | 预期结果 |
|---|------|------|---------|
| 1 | default 档位 + read 工具 → ALLOW | `(default, read, safe, tool="Read")` | verdict=ALLOW, signature 格式 `global:Read:{hash8}` |
| 2 | default 档位 + bash 安全命令 → ALLOW | `(default, bash, safe, command=["echo","hello"])` | verdict=ALLOW |
| 3 | default 档位 + edit 工具 → ASK | `(default, edit, safe, tool="Edit")` | verdict=ASK, signature 含 `global:Edit:{hash8}` |
| 4 | yolo 档位 + 任意工具 → ALLOW | `(yolo, write, dangerous, ...)` | verdict=ALLOW（短路，不调危险匹配） |
| 5 | 带 skill_context 的签名生成 | `skill_context=SkillContext(name="my-skill", content_hash="a1b2")` | signature 格式 `skill:my-skill@a1b2:tool:{hash8}` |
| 6 | 无 skill_context 的签名（全局） | `skill_context=None` | signature 格式 `global:tool:{hash8}` |

### 签名算法稳定性

| # | 场景 | 输入 | 预期结果 |
|---|------|------|---------|
| 7 | 相同参数多次调用 → 相同签名 | 同一 DecideRequest 调用两次 | 两次 signature 完全一致 |
| 8 | 参数 dict 键顺序不影响签名 | `{"b":1,"a":2}` vs `{"a":2,"b":1}` | signature 一致（canonical JSON 排序） |
| 9 | Bash command 取前 3 个 token | `command="pip install requests --upgrade"` | arg_hash8 基于 `["pip","install","requests"]` 计算 |
| 10 | skill name 或 content_hash 变化 → 签名不同 | 同一 skill 不同 content_hash | signature 不同 |

### 危险命令匹配

| # | 场景 | 输入 | 预期结果 |
|---|------|------|---------|
| 11 | Bash 命令命中危险模式 → risk_level 升级 | `command="rm -rf /tmp"` 原始 risk_level=safe | 升级为 dangerous → 查矩阵得 ASK |
| 12 | Bash 命令匹配 `curl ... | sh` | `command="curl url | sh"` | 升级为 dangerous |
| 13 | Bash 命令匹配 `chmod` | `command="chmod 777 /work/out"` | 升级为 dangerous |
| 14 | Bash 命令匹配 `dd of=` | `command="dd if=/dev/zero of=/dev/sda"` | 升级为 dangerous |
| 15 | Bash 命令匹配 `mkfs` | `command="mkfs.ext4 /dev/sdb"` | 升级为 dangerous |
| 16 | Bash 安全命令不升级 | `command="echo hello"` 原始 risk_level=safe | risk_level 保持 safe |

### yolo 档位行为

| # | 场景 | 预期结果 |
|---|------|---------|
| 17 | yolo 档位不调 DangerousCommandMatcher | 即使 command="rm -rf /"，也应该直接 ALLOW（仅构造 signature） |
| 18 | yolo 档位不调 DecisionMatrix.lookup() | 决策路径跳过矩阵查表 |
| 19 | yolo 档位仍生成 signature | 返回的 signature 非空、格式正确 |

### 边界与错误

| # | 场景 | 预期结果 |
|---|------|---------|
| 20 | SessionPolicyState 未设置 → 默认 "default" | `get(session_id)` 返回 "default" |
| 21 | agent_policy 在 DecideRequest 中显式传入时优先 | 即使 SessionPolicyState 存 "default"，入参传 "yolo" 也按 yolo 决策 |
| 22 | skill_context.content_hash 为空字符串 | 仍可正常生成 `skill:<name>@:` 前缀的签名 |
| 23 | tool_args 为空 dict | arg_hash8 为 SHA-256("{}")[:8] |
| 24 | 非 agent 模式调用 → 防御性断言 | 抛 PolicyError（但 v1 此行为为防御性断言，ask 模式应在调用链上游被过滤） |

---

## 四、Contract Specification（契约规约）

纯逻辑模块，不适用此章节（见 test-guide.md 第七节速查表）。

---

## 五、Integration Points（集成点测试）

| 集成点 | 验证重点 |
|--------|---------|
| SessionPolicyState → SSE 事件 | `set_policy()` 切换档位后，验证 event emitter 被调用且 payload 含 `session_id` + `policy` 字段 |
| session 生命周期 | 新 session 首次 `get_policy()` 返回 "default"（不依赖外部初始化） |

---

## 六、Verification Strategy（验证策略）

### 执行环境

- 无需 docker、无需 DB、无需外部服务
- 纯 Python 单元测试，在任何环境可运行
- 推荐使用 pytest + parametrize 覆盖矩阵所有 cell

### 测试组织

```
tests/unit/core/policy/
├── test_decider.py                  # PolicyDecider.decide() 的矩阵覆盖与路径测试
├── test_decision_matrix.py          # DecisionMatrix 两档独立验证
├── test_signature_builder.py        # SignatureBuilder 的格式稳定性、规范化、去重
├── test_dangerous_commands.py       # DangerousCommandMatcher 模式表完整性与边界
└── test_session_state.py            # SessionPolicyState 读写、默认值、SSE 事件
```

### 关键测试模式

- **矩阵覆盖**：pytest.mark.parametrize 枚举 `(agent_policy, tool_class, risk_level)` 全组合，每项断言 verdict
- **签名稳定性**：固定种子输入，断言输出字符串精确匹配
- **危险命令**：正向（命中）与反向（不命中）用例各半，覆盖模式表中全部条目
- **决策函数纯净性**：并发调用 `decide()` 不互相影响，无共享可变状态
