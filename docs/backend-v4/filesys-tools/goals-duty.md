# Filesystem Tools Goals And Duties

## Design Goals

- 为 Agent 提供可预测、可审计的内置文件系统工具能力，让 `read`、`grep`、`glob`、`edit`、`write`、`bash` 进入统一工具注册与 policy/permission 链路。
- 保持 Agent 可见工具与执行环境解耦：`core/tools` 定义工具契约，`core/shell` 提供环境，`core/sandbox` 提供隔离执行。
- 将文件读写能力控制在明确的 workspace、additional directories、skill run directory 范围内，避免工具绕过 sandbox 或 permission。
- 借鉴 Kimi CLI 的工具级参数校验、输出截断、diff 展示思路，同时借鉴 DeepAgents 的 backend/sandbox 抽象边界。
- 优先保证安全边界和结果稳定性，其次再优化搜索速度、后台任务和高级编辑体验。

## Duties

- 定义 Agent 可调用的文件系统工具集合：`read_file`、`glob_files`、`grep_files`、`edit_file`、`write_file`，以及通过 shell 环境执行的 `bash`。
- 为每个工具提供稳定的 `ToolDefinition` schema、描述、参数校验、结果格式、错误格式、policy metadata。
- 在工具执行前依赖全局 `policy -> permission` 决策门，不在工具内部私自弹确认或写 allow。
- 通过 `core/shell` 获取当前运行环境，包括 cwd、workspace roots、additional roots、skill roots、run_dir、env、timeout 与输出限制。
- 对路径输入做规范化、范围校验和敏感文件保护，并为不可读、不可写、越界、二进制、超限等情况返回结构化错误。
- 为写入类工具生成可理解的变更预览或 diff，使 permission UI 和日志可以展示具体风险。
- 为 `bash` 工具提供受控命令执行入口，并保证真实执行只能进入 `core/shell -> core/sandbox`。

## Non-Duties

- 不负责决定某个工具调用是 allow、ask 还是 deny；该职责属于 `core/policy`。
- 不负责保存永久授权、会话授权或确认结果；该职责属于 `core/permission`。
- 不负责容器创建、网络隔离、挂载硬化或资源限制；这些属于 `core/sandbox`。
- 不负责 skill 安装、启用、禁用、卸载或 content hash 计算；这些属于 `core/skills`。
- 不负责前端确认卡、diff UI 或 SSE 渲染；本模块只提供可供展示的数据。
- 不提供绕过 workspace 的任意 host 文件读写能力。
- 不在当前阶段实现长期后台 shell 任务管理；后台任务需要单独设计 task lifecycle、取消、输出分页和恢复语义。
