# Backend V4 Skills-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 先实现用户可安装 skill 的最小闭环，再逐步接入 policy、permission、sandbox，让 agent 能以安全、可验证的方式消费 `SKILL.md` 与后续脚本能力。

**Architecture:** 采用纵向分批推进：第一批只完成 skills 注册、安装、激活与只读渐进披露，不执行 scripts；第二批补齐工具元数据与 policy 纯决策；第三批接 permission 确认与 allow 记忆；第四批实现 sandbox 与 Bash 脚本执行；第五批做端到端整合。每批都必须有独立测试和验收门，避免安全链条半成品被误用。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic/dataclass、SQLAlchemy `app_settings`、pytest、现有 `newbee_notebook/core/skills`、`core/tools`、`core/engine`、`application/services` 分层。

---

## 文档约定

- 本文档使用 UTF-8 编码。
- 测试设计遵循 `docs-plan/test-guide.md`。
- 测试代码组织遵循 `docs-test/README.md`、`docs-test/classification.md`、`docs-test/directory-convention.md`、`docs-test/writing-guide.md`、`docs-test/ci-strategy.md`。
- 具体执行任务应继续沉淀到本目录后续 `tasks.md`，并以 `docs-implement/task-guide.md` 的任务状态规则为准。

## 实施顺序

### Phase 1: Skills MVP

目标：先让 `/my-skill` 可以从 `configs/skills/<name>/SKILL.md` 激活，并让 mellow 通过只读提示进入 progressive disclosure。该阶段不执行 `scripts/`，不接 sandbox。

范围：
- 升级 `newbee_notebook/core/skills/registry.py` 为统一命令注册中心，继续兼容 note/diagram/video 内置 Python provider。
- 新增 `ManifestParser`，只解析 `SKILL.md` frontmatter 的 `name` 与 `description`。
- 新增 `ContentHasher`，对 skill 目录计算稳定 tree hash。
- 新增 `ConfigSkillProvider` 与 `ActivationContextBuilder`，激活时只注入 description 与读取 `SKILL.md` 的指令。
- 新增 skills 生命周期服务的最小集合：list、enable/disable、uninstall 的后端核心能力；安装通道先以本地目录 copy-only 为主，GitHub/zip 进入 Phase 1 后半。
- 新增 `/api/skills` 基础 API，供前端后续动态 slash hint 与控制面板使用。

验收标准：
- `/note`、`/diagram`、`/video` 现有内置 skill 的命令匹配和确认流程不回归。
- 合法 `configs/skills/demo/SKILL.md` 可被发现、列出、启用，并通过 `/demo ...` 激活。
- 激活 prompt 不包含 `SKILL.md` 正文，只包含描述与读取指令。
- `ContentHasher` 对同一目录重复计算结果一致，任一文件内容变化后 hash 变化。
- 禁用或卸载后的 skill 不再被 slash 命令命中。
- 单元测试放在 `newbee_notebook/tests/unit/core/skills/`，API 契约测试放在 `newbee_notebook/tests/contract/api/`。
- 本阶段最小验证命令：`pytest newbee_notebook/tests/unit/core/skills/ -v` 与 `pytest newbee_notebook/tests/unit/application/services/test_chat_runtime_routing.py -v`。

### Phase 2: Policy Foundation

目标：让 agent 模式下的工具调用具备纯决策入口，但不在 policy 内做 IO、不查 DB、不弹卡。

范围：
- 为 `ToolDefinition` 增加或伴随提供 `tool_class`、`risk_level`、`sandbox_required` 等 policy 所需元数据。
- 新增 `newbee_notebook/core/policy/`：`PolicyDecider`、`DecisionMatrix`、`DangerousCommandMatcher`、`SignatureBuilder`、`SessionPolicyState`。
- `AgentLoop` 在工具执行前调用 policy；`ALLOW` 继续执行，`ASK` 暂时走兼容提示或直接转入 Phase 3 的 permission。
- skill 激活后把 `skill_name + content_hash` 传给 policy，用于生成 `skill:<name>@<hash>:<tool>:<arg_hash8>` 签名。

验收标准：
- `PolicyDecider.decide()` 是同步纯函数，无数据库、无网络、无 SSE、无 permission 调用。
- default/yolo 两档矩阵结果符合 `docs/backend-v4/policy/dfd-interface.md`。
- 相同工具参数生成相同 signature，dict 键顺序不影响 signature。
- skill content_hash 变化导致 signature 变化。
- 测试放在 `newbee_notebook/tests/unit/core/policy/`。
- 本阶段最小验证命令：`pytest newbee_notebook/tests/unit/core/policy/ -v`。

### Phase 3: Permission Gateway

目标：让 `ASK` 决策进入统一 permission 门面，完成一次允许、本会话允许、永久允许、拒绝的闭环。

范围：
- 新增 `newbee_notebook/core/permission/`：`PermissionGateway`、`AllowStore`、`SessionAllowCache`、`ConfirmationDispatcher`、`QueueManager`、`DecisionRecorder`。
- `AllowStore` 作为 `permissions.*` app_settings key 的唯一读写者。
- 复用现有 `ConfirmationGateway` 与 `ConfirmationRequestEvent`，以向后兼容方式增加 capability signature、risk、response options 等字段。
- skill 卸载时调用 `clear_skill_permissions(name)`，清 DB 与 session 内存许可。

验收标准：
- permission 命中 session allow 或 permanent allow 时不弹确认卡。
- DB 读失败按未命中处理并进入 ASK；DB 写失败 fail-closed，不执行工具。
- 同 session 多个 ASK 串行，不同 session 互不阻塞。
- `clear_skill_permissions(name)` 删除 `skill:<name>@...` 相关许可。
- 内置 skill 旧 confirmation 路径不回归，用户 config skill 的新 permission 路径可用。
- 测试放在 `newbee_notebook/tests/unit/core/permission/`，关键 DB 协作放在 `newbee_notebook/tests/integration/core/permission/`。
- 本阶段最小验证命令：`pytest newbee_notebook/tests/unit/core/permission/ -v`。

### Phase 4: Sandbox And Bash

目标：给 skill scripts 提供唯一执行通道，保证 host 只读、网络隔离、容器硬化与结构化日志。

范围：
- 新增 `newbee_notebook/core/sandbox/`：`SandboxExecutor`、mount/image/network guard、container runner、output collector、cache volume manager。
- 新增或扩展 `core/tools` 中的 Bash 工具，所有脚本执行必须经 sandbox。
- Read/Glob/Grep 工具限定在当前 active skill 目录与当前 run_dir 可见范围内。
- `tmp/skill-runs/<run_id>/exec.json` 记录每次执行。

验收标准：
- sandbox 请求只能使用 argv list，不接受 shell 字符串。
- host skill 目录只读挂载，run_dir 可写挂载。
- `network=False` 使用 none；`network=True` 使用专用 `newbee_skill_net`，不可接 compose 默认网络。
- 非 root、cap-drop、no-new-privileges、read-only rootfs、资源限制等硬化参数不可被调用方放宽。
- 单元测试放在 `newbee_notebook/tests/unit/core/sandbox/`，docker 参数契约或真实执行放在 `newbee_notebook/tests/integration/core/sandbox/`，需要 Docker 的测试标记 `integration`，超过 10 秒叠加 `slow`。
- 本阶段最小验证命令：`pytest newbee_notebook/tests/unit/core/sandbox/ -v`；有 Docker 环境时再跑 `pytest newbee_notebook/tests/integration/core/sandbox/ -v`。

### Phase 5: End-to-End Integration

目标：打通用户安装 skill、slash 激活、读取说明、执行脚本、policy/permission 裁定、sandbox 返回结果、mellow 调业务工具落地的完整链路。

范围：
- `ChatService`、`SessionManager`、`AgentLoop` 整合 SkillContext、policy decision、permission request、sandbox-backed tools。
- `/api/skills` 补齐 GitHub URL、zip 上传、preview、toggle、delete 的契约。
- 前端动态 slash hint 与 Skills 控制面板可以后续单独开 frontend 批次；后端先保证 API 稳定。
- 补充端到端 fixture：一个只读 skill、一个带脚本 skill、一个会触发 permission 的 skill。

验收标准：
- 只读 skill：`/demo` 激活后模型被要求读取 `SKILL.md`，不预加载全文。
- 脚本 skill：脚本只能经 Bash → sandbox 执行，输出可回流给模型。
- 写入类工具：default policy 下触发 permission；用户拒绝时工具不执行；用户永久允许后同内容 hash 命中 allow。
- 更新 skill 内容后 content_hash 变化，旧永久允许不再命中。
- 端到端集成测试放在 `newbee_notebook/tests/integration/core/skills/` 或现有 `newbee_notebook/tests/integration/test_chat_engine_integration.py` 的新增用例中。
- PR 级验证至少通过 `pytest -m "unit or contract"`；合并前通过相关 integration 测试。

## 第一批任务清单

- [ ] T001 Define Phase 1 source file layout under `newbee_notebook/core/skills/`.
- [ ] T002 Implement `ManifestParser` with Anthropic-compatible `name` and `description` validation.
- [ ] T003 Implement `ContentHasher` with deterministic path sorting and SHA-256 tree hashing.
- [ ] T004 Extend skill contracts with config skill metadata while preserving existing provider protocol.
- [ ] T005 Upgrade `SkillRegistry` to support built-in providers and enabled config providers without command conflicts.
- [ ] T006 Implement `ConfigSkillProvider` and `ActivationContextBuilder` with prompt-only progressive disclosure.
- [ ] T007 Implement local copy-only install preview and lifecycle list/enable/disable/uninstall services.
- [ ] T008 Add `/api/skills` list and lifecycle contract endpoints.
- [ ] T009 Integrate config skill activation into `ChatService._resolve_skill_runtime`.
- [ ] T010 Add unit and contract tests according to `docs-test/` directory rules.
- [ ] T011 Run targeted Phase 1 tests and update this plan with any discovered scope corrections before moving to Phase 2.

## Testing Gates

- Unit gate: every new pure logic or service orchestration component has focused tests with direct dependencies mocked.
- Contract gate: every new HTTP route has TestClient-based contract tests with service layer mocked.
- Integration gate: cross-module behavior is verified only after the relevant modules exist; do not fake integration by mocking both sides.
- Marker gate: each test file is marked or collected as exactly one base marker: `unit`, `contract`, `integration`, or `smoke`.
- Directory gate: unit tests mirror source paths; contract tests live under `newbee_notebook/tests/contract/api/`; integration tests are grouped by scenario.

## Stop Conditions

- Stop if a Phase 1 change requires script execution before sandbox exists.
- Stop if policy needs to read DB or call permission directly.
- Stop if permission would allow on DB, SSE, timeout, or gateway failure.
- Stop if sandbox requires writable host mounts or compose default network access.
- Stop if a task needs to modify frontend behavior beyond stabilizing backend API contracts.

## Handoff

Phase 1 is the next executable batch. Before coding, create or update `docs/backend-v4/implement-1/tasks.md` with concrete task status, then execute T001 through T011 in order.
