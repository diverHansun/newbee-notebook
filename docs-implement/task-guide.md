# task-guide.md

**Implement 阶段任务文档编写与使用指南**

本文档用于指导 LLM 和人类开发者如何编写、维护和执行 `tasks.md` 文件。

---

## 1. 文档定位（Purpose）

`tasks.md` 是 **Implement 阶段唯一的任务真相源（Single Source of Execution Truth）**。

它的职责不是解释系统设计，也不是描述实现方法，而是：

- 明确 **要做什么（What）**
- 明确 **执行顺序与依赖（Order and Dependencies）**
- 明确 **当前进度状态（Status）**
- 为 **人类开发者与 Coding Agent** 提供同一份、可执行、可追踪的任务清单

> 所有实现行为，必须以 `tasks.md` 为准；  
> 不在 `tasks.md` 中的工作，视为**未计划、不可执行或需要补充规划**。

---

## 2. tasks.md 在整体文档体系中的位置

在完整的软件生命周期中，`tasks.md` 位于 **Plan - Implement - Test** 的中间层，承担"设计到代码"的桥梁作用。

```
Plan 文档（architecture / data-model / dfd-interface / goals-duty）
    |
    v
tasks.md  <-- 本文档约束对象
    |
    v
Implement 执行（由 implement.md 规定 HOW）
    |
    v
Test / 验收 / Changelog
```

**各层职责分工**：

| 文档层级 | 职责 |
|----------|------|
| Plan 文档 | 定义"系统应该是什么样" |
| tasks.md | 定义"为了实现它，需要完成哪些具体工作" |
| implement.md | 定义"执行 tasks.md 时应遵循的流程与规则" |

---

## 3. 核心设计原则（Design Principles）

### 3.1 单一职责原则

`tasks.md` **只做一件事**：

> 以任务清单的形式，描述"需要完成的实现工作"。

它 **不应该包含**：

- 架构设计解释（属于 plan）
- 执行流程与策略（属于 implement.md）
- 测试报告或结论（属于 test 阶段）
- 变更历史（属于 changelog）

---

### 3.2 任务必须"可独立执行"

每一条任务都应满足以下条件：

- 目标清晰、动作明确
- 不依赖隐含上下文
- 一个熟悉项目的开发者或 Agent **只读此任务即可开始执行**
- 完成与否可以被明确判断

如果一个任务无法独立执行，应拆分为多个更小的任务。

---

### 3.3 tasks.md 是"状态文件"，不是"说明书"

- 勾选框（`[ ]` / `[X]`）代表 **真实执行状态**
- 勾选行为本身是项目状态的一部分
- 修改任务状态，等同于推进或回滚实现进度

> 禁止在未实际完成工作时提前勾选任务。

---

### 3.4 MECE 原则（Mutually Exclusive, Collectively Exhaustive）

任务拆分应遵循 MECE 原则：

- **互斥（Mutually Exclusive）**：任务之间不应存在功能重叠
- **完备（Collectively Exhaustive）**：所有任务加起来应覆盖完整的实现目标

---

## 4. tasks.md 的标准结构

### 4.1 总体结构模板

```markdown
# Tasks - <Module / Feature Name>

## Metadata
- Created: YYYY-MM-DD
- Last Updated: YYYY-MM-DD
- Source Plan: <对应的 Plan 文档路径>

## Phase 1: Setup
- [ ] T001 初始化项目结构
- [ ] T002 配置基础依赖与环境

## Phase 2: Foundational
- [ ] T003 定义核心目录与模块边界
- [ ] T004 建立基础错误处理机制

## Phase 3: User Story / Feature A
- [ ] T005 实现 A 的数据模型
- [ ] T006 实现 A 的核心业务逻辑
- [ ] T007 实现 A 的接口或命令

## Phase 4: Integration
- [ ] T008 集成外部服务或中间件

## Phase 5: Polish and Cleanup
- [ ] T009 补充必要的校验与日志
```

Phase 的划分是推荐而非强制，但应体现 **从基础 - 核心 - 集成 - 收尾** 的顺序。

---

### 4.2 单条任务的书写规范

每一条任务必须遵循统一格式：

```
- [ ] <TaskID> <Task Description with concrete action and target>
```

**必要要素**：

| 要素 | 说明 |
|------|------|
| Checkbox | `[ ]` 未完成，`[X]` 已完成 |
| TaskID | 全局唯一，建议顺序编号：T001, T002, ... |
| 任务描述 | 使用动词开头，明确作用对象 |

**动词选择指南**：

| 动词 | 适用场景 |
|------|----------|
| Create | 创建新文件、新模块 |
| Implement | 实现具体功能或逻辑 |
| Define | 定义类型、接口、协议 |
| Add | 添加功能、字段、配置 |
| Refactor | 重构现有代码结构 |
| Remove | 删除废弃代码或功能 |
| Update | 更新现有实现 |
| Integrate | 集成外部依赖或服务 |
| Verify | 验证功能正确性 |

**示例**：

```markdown
- [ ] T012 Implement user authentication service in backend/auth/service.ts
- [ ] T013 Add token refresh logic to backend/auth/refresh.ts
- [ ] T014 Define AuthResult interface in backend/auth/types.ts
```

---

### 4.3 禁止使用的描述方式

| 反例 | 问题 | 正例 |
|------|------|------|
| 优化一下代码 | 目标模糊 | Refactor UserService to extract validation logic |
| 处理相关逻辑 | 作用对象不明 | Implement error handling in PaymentProcessor |
| 完善功能 | 无法判断完成标准 | Add input validation for CreateUserRequest |
| 看情况调整 | 不可执行 | Update rate limit config based on load test results |

---

## 5. 任务粒度指南（Granularity）

### 5.1 粒度判断标准

一个任务的合理粒度应满足：

| 维度 | 标准 |
|------|------|
| 时间 | 可在 0.5 - 4 小时内完成 |
| 范围 | 影响 1-3 个文件 |
| 验证 | 有明确的完成判定条件 |
| 独立性 | 可单独提交并通过 CI |

### 5.2 粒度过大的信号

- 任务描述中出现"和"、"以及"、"同时"等连接词
- 无法一句话说清楚完成标准
- 预计需要超过 4 小时
- 涉及超过 5 个文件的修改

### 5.3 粒度过小的信号

- 多个任务实际上是同一个功能的碎片
- 单独执行没有意义
- 完成一个任务需要立即执行另一个任务

### 5.4 拆分示例

**过大任务**：

```markdown
- [ ] T001 Implement user management feature
```

**合理拆分**：

```markdown
- [ ] T001 Define User entity and UserRepository interface
- [ ] T002 Implement UserRepository with database adapter
- [ ] T003 Implement CreateUserUseCase
- [ ] T004 Implement GetUserByIdUseCase
- [ ] T005 Add user-related API endpoints to router
```

---

## 6. 依赖与顺序表达规则

### 6.1 顺序即语义

- tasks.md 默认自上而下执行
- 后面的任务可以假设前面的任务已经完成
- 不应在任务描述中反复声明"依赖 T00X"

### 6.2 显式依赖标注（可选）

当任务之间存在非顺序依赖时，可使用以下标注：

```markdown
- [ ] T010 Implement caching layer (blocks: T012, T013)
- [ ] T011 Add logging middleware
- [ ] T012 Integrate cache with UserService (blocked-by: T010)
- [ ] T013 Integrate cache with ProductService (blocked-by: T010)
```

### 6.3 并行任务标注

如确有需要，可在任务中标注并行属性 `[P]`，但应满足：

- 不修改同一文件或同一模块核心逻辑
- 不存在隐式数据或状态依赖

**示例**：

```markdown
- [ ] T020 [P] Add unit tests for auth service
- [ ] T021 [P] Add documentation comments for auth module
```

---

## 7. 任务验收标准（Definition of Done）

### 7.1 通用验收条件

每个任务在被标记为 `[X]` 前，必须满足：

| 条件 | 说明 |
|------|------|
| 代码已提交 | 相关代码已 commit 到版本控制 |
| 编译通过 | 代码可正常编译，无语法错误 |
| 基本测试 | 相关单元测试已通过（如适用） |
| 无回归 | 未破坏现有功能 |

### 7.2 任务级验收标准（可选）

对于复杂任务，可在任务描述中附加验收条件：

```markdown
- [ ] T015 Implement rate limiter
  - AC1: Limits requests to 100/minute per user
  - AC2: Returns 429 status when limit exceeded
  - AC3: Limit count resets after 1 minute window
```

---

## 8. Agent 执行任务的标准流程

当 LLM Agent 执行 tasks.md 中的任务时，必须遵循以下流程：

### 8.1 执行前检查

1. **读取任务**：获取当前待执行任务的完整描述
2. **理解上下文**：确认前置任务已完成，理解任务在整体中的位置
3. **明确范围**：确定任务涉及的文件和模块边界
4. **回顾设计**：如需要，查阅相关 Plan 文档

### 8.2 执行中行为

1. **单任务聚焦**：一次只执行一个任务，不跨任务实现
2. **范围控制**：只修改任务明确涉及的代码，不做额外"顺手"修改
3. **持续验证**：实现过程中持续验证代码正确性
4. **记录决策**：对于实现中的重要决策，可添加代码注释

### 8.3 执行后确认

1. **自检**：确认实现符合任务描述和验收标准
2. **更新状态**：将任务状态从 `[ ]` 更新为 `[X]`
3. **报告完成**：简要说明完成情况和任何需注意的事项

### 8.4 异常处理

当执行过程中发现问题时：

| 情况 | 处理方式 |
|------|----------|
| 任务描述不清 | 暂停执行，请求澄清 |
| 发现前置依赖缺失 | 暂停执行，报告依赖问题 |
| 任务需要拆分 | 暂停执行，建议任务拆分方案 |
| 发现设计缺陷 | 暂停执行，建议回到 Plan 阶段 |
| 实现过程中发现新需求 | 记录为新任务，不在当前任务中实现 |

---

## 9. 与 implement.md 的协作关系

### 9.1 职责划分

| 文档 | 回答的问题 |
|------|------------|
| tasks.md | What to do（做什么） |
| implement.md | How to do（怎么做） |

- tasks.md 不包含执行策略
- implement.md 不重复任务内容

### 9.2 执行流程

在 Implement 阶段：

1. 执行者首先阅读 implement.md，了解执行规则
2. 再以 tasks.md 为唯一依据推进实现
3. 每完成一项任务，立即更新勾选状态

### 9.3 冲突处理

如发现任务不合理，应：

1. 暂停执行
2. 回到 Plan 或 tasks.md 进行修订
3. 不得私自绕过任务清单

---

## 10. 任务变更规则

### 10.1 允许变更，但必须显式

在 Implement 阶段，允许：

- 拆分任务
- 合并任务
- 新增遗漏任务
- 调整顺序
- 取消不再需要的任务

但必须遵循：

1. **先修改 tasks.md**
2. **再执行新的任务**
3. **不允许"先写代码，事后补任务"**

### 10.2 变更标注

对于变更的任务，可使用以下标注：

```markdown
- [ ] T015 [NEW] Add input sanitization for user input
- [ ] T016 [SPLIT from T010] Extract validation logic to separate module
- [C] T017 [CANCELLED] Remove legacy API endpoint (no longer needed)
```

### 10.3 已完成任务原则上不可修改

- 已勾选（`[X]`）的任务，视为历史事实
- 若发现设计错误，应新增修正任务，而不是回溯修改旧任务
- 这确保了任务历史的可追溯性

---

## 11. 进度追踪与状态管理

### 11.1 任务状态定义

| 标记 | 状态 | 说明 |
|------|------|------|
| `[ ]` | 待执行 | 尚未开始 |
| `[>]` | 进行中 | 正在执行（可选） |
| `[X]` | 已完成 | 已完成并验证 |
| `[C]` | 已取消 | 不再需要执行 |
| `[B]` | 阻塞中 | 因外部原因无法继续（可选） |

### 11.2 进度可视化

可在 tasks.md 头部添加进度摘要：

```markdown
## Progress Summary
- Total: 20 tasks
- Completed: 12 (60%)
- In Progress: 2
- Remaining: 6
```

---

## 12. 错误处理与回滚

### 12.1 实现错误的处理

当发现已完成任务的实现存在错误时：

1. **不要**修改已完成任务的状态
2. 新增修复任务：

```markdown
- [X] T010 Implement user authentication
- [ ] T010-fix Fix authentication token expiry calculation
```

### 12.2 设计错误的处理

当发现任务本身的设计存在问题时：

1. 暂停当前 Implement 阶段
2. 回到 Plan 阶段进行修正
3. 更新 tasks.md 以反映设计变更
4. 记录变更原因

### 12.3 回滚原则

- 任务状态的回滚应伴随代码的回滚
- 回滚操作本身应记录为新任务
- 避免频繁回滚，这通常是 Plan 阶段不充分的信号

---

## 13. 最佳实践

### 13.1 文档风格

- tasks.md 应保持 **短句、列表化、无叙事**
- 复杂背景请放入 plan / devlog / ADR
- tasks.md 是最适合被 Agent 高频读取的文档之一，应保持格式稳定

### 13.2 任务编写

- 使用一致的命名约定
- 保持任务描述的精确性
- 避免使用缩写（除非是项目约定的术语）

### 13.3 执行纪律

- 按顺序执行，不跳跃
- 一次只关注一个任务
- 完成即标记，不积压

### 13.4 沟通原则

- 当你不知道下一步做什么时，tasks.md 本身就是答案
- 任何对任务的疑问，应在执行前澄清
- 实现中的重要决策，应记录在代码或相关文档中

---

## 14. 与 Plan 文档的映射关系

### 14.1 任务来源追溯

每个任务应可追溯到 Plan 阶段的某个设计决策：

| Plan 文档 | 产生的任务类型 |
|-----------|----------------|
| goals-duty.md | 核心功能任务（实现 Duties） |
| architecture.md | 结构搭建任务（创建模块、定义边界） |
| data-model.md | 类型定义任务（实现 interfaces/types） |
| dfd-interface.md | 接口实现任务（实现 API/方法） |

### 14.2 追溯标注（可选）

对于关键任务，可标注其设计来源：

```markdown
- [ ] T005 Implement CommandRegistry (ref: architecture.md Section 2)
- [ ] T006 Define CommandResult type (ref: data-model.md)
```

---

## 15. 文档自检清单

在提交或使用 tasks.md 前，确认以下事项：

- [ ] 每个任务都有唯一的 TaskID
- [ ] 每个任务都使用动词开头
- [ ] 每个任务的完成标准可被明确判断
- [ ] 任务顺序反映了依赖关系
- [ ] 没有职责重叠的任务
- [ ] 所有任务加起来覆盖完整的实现目标
- [ ] 任务粒度适中（0.5-4小时可完成）
- [ ] 无模糊或歧义的描述

---

## 16. 附录：常见问题

### Q1: 任务太大怎么办？

拆分为多个子任务，确保每个子任务独立可执行。

### Q2: 执行中发现需要额外工作怎么办？

暂停当前任务，将额外工作添加为新任务，然后继续。

### Q3: 任务之间有循环依赖怎么办？

这通常是设计问题的信号。回到 Plan 阶段重新审视模块划分。

### Q4: Agent 可以同时执行多个任务吗？

仅当任务明确标注为 `[P]`（可并行）时。默认应顺序执行。

### Q5: 如何处理紧急修复？

紧急修复应作为新任务添加，并标注优先级。不应绕过 tasks.md 直接实现。
