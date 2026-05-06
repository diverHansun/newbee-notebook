# Filesystem Tools Data Flow And Interface

## Context & Scope

`filesys-tools` 位于 Agent runtime 的工具层。它接收来自 `AgentLoop` 的工具调用参数，但只有在 `policy` 与 `permission` 允许后才执行。

外部交互模块：

- `core/tools/ToolRegistry`：发现并暴露工具定义。
- `core/policy`：根据工具元数据和参数生成 allow/ask/deny 决策。
- `core/permission`：处理 ask、session allow、permanent allow、reject。
- `core/shell`：提供 cwd、workspace roots、run_dir、env、timeout、路径策略和执行入口。
- `core/sandbox`：为 `bash` 和后续 sandbox-backed 文件操作提供隔离执行。
- `AgentLoop`：发送工具输入，接收 `ToolCallResult`，再交还给 LLM。

本文档只描述文件系统工具模块的数据流和接口，不描述前端展示、permission 存储格式、sandbox 容器参数或 skill 生命周期。

## Data Flow Description

### Read Flow

1. LLM 产生 `read_file` 工具调用，输入包含 path、line offset、line count。
2. `AgentLoop` 将工具名、参数、工具 metadata 交给 `policy`。
3. `policy` 对读工具默认返回 allow，或在策略收紧时返回 ask/deny。
4. 允许执行后，`read_file` 从 `core/shell` 获取当前环境。
5. 路径策略将 path 规范化，并判断是否位于允许读取范围内。
6. 工具检查目标是否存在、是否为普通文件、是否疑似敏感文件、是否为可读文本。
7. 工具按 offset 和 line count 读取内容，应用最大行数、最大行长、最大字节数限制。
8. 工具返回带行号的文本预览和读取统计。

### Glob Flow

1. LLM 产生 `glob_files` 工具调用，输入包含 pattern、directory、include_dirs。
2. 策略链允许后，工具从 `core/shell` 获取允许搜索目录。
3. directory 被规范化并验证是否位于 workspace、additional roots 或 skill roots 内。
4. 工具拒绝过宽的顶层 `**` 模式，避免默认递归全仓库。
5. 工具执行 glob，排序结果，按最大数量截断。
6. 工具返回相对路径列表和匹配统计。

### Grep Flow

1. LLM 产生 `grep_files` 工具调用，输入包含 pattern、path、glob filter、output mode、context options。
2. 策略链允许后，工具验证 path 范围、正则输入和输出模式。
3. 工具在允许范围内搜索文本文件。
4. 搜索结果按输出模式整理为匹配文件、匹配行或计数。
5. 工具过滤敏感文件路径，对超限输出进行截断并标记。
6. 工具返回搜索摘要和可继续缩小范围的提示。

### Edit Flow

1. LLM 产生 `edit_file` 工具调用，输入包含 path、old string、new string、replace_all。
2. `policy` 对 edit/write 类工具默认返回 ask。
3. `permission` 命中 allow 或用户确认后，工具执行。
4. 工具验证 path 可写、目标存在、目标是文本文件。
5. 工具读取原始内容，查找 old string。
6. 未命中时返回结构化错误；多重命中且 `replace_all=false` 时返回结构化错误。
7. 工具保留匹配区域的换行风格，生成新内容。
8. 工具生成 diff 预览并写回文件。
9. 工具返回替换次数、文件大小和 diff 摘要。

### Write Flow

1. LLM 产生 `write_file` 工具调用，输入包含 path、content、mode。
2. `policy` 对 write 类工具默认返回 ask。
3. `permission` 允许后，工具验证父目录、写入范围和 mode。
4. 若文件存在，工具读取旧内容用于 diff；若不存在，旧内容为空。
5. mode 为 overwrite 时写入 content；mode 为 append 时追加 content。
6. 工具返回写入结果、当前文件大小和 diff 摘要。

### Bash Flow

1. LLM 产生 `bash` 工具调用，输入包含 command、timeout、background mode、description。
2. `policy` 根据 tool class、risk level 和危险命令匹配返回 ask 或 deny。
3. `permission` 允许后，`bash` 工具将请求交给 `core/shell`。
4. `core/shell` 生成 sandbox 执行请求，包含 cwd、env、timeout、stdout/stderr 限制和 run_dir。
5. `core/sandbox` 执行命令，返回 exit code、stdout、stderr、timeout、truncated。
6. `bash` 工具将执行结果映射为 `ToolCallResult`。

## Interface Definition

### ToolDefinition Contracts

所有工具都以 `ToolDefinition` 暴露：

- `name`：稳定工具名，供 LLM 调用和 policy 签名使用。
- `description`：面向 LLM 的简短能力说明。
- `parameters`：JSON schema，约束参数类型、默认值和范围。
- `tool_class`：用于 policy 分类，读工具为 `read`，写入工具为 `write/edit`，bash 为 `bash`。
- `risk_level`：用于 policy 初始风险判断。
- `sandbox_required`：bash 为 true；文件工具可按后续 backend 策略演进。

### read_file

- 输入含义：目标文件路径、起始行、读取行数。
- 输出含义：带行号的文本片段、总行数、是否截断、错误信息。
- 同步特性：单次请求同步返回。

### glob_files

- 输入含义：glob pattern、搜索目录、是否包含目录。
- 输出含义：相对路径列表、匹配数量、是否截断。
- 同步特性：单次请求同步返回。

### grep_files

- 输入含义：正则模式、搜索路径、文件过滤、输出模式、上下文行与限制。
- 输出含义：匹配文件、匹配行或计数，附带截断与敏感文件过滤提示。
- 同步特性：单次请求同步返回；超时返回部分结果或结构化错误。

### edit_file

- 输入含义：目标路径、旧字符串、新字符串、是否替换全部匹配。
- 输出含义：替换次数、diff 摘要、错误信息。
- 同步特性：单次请求同步返回。

### write_file

- 输入含义：目标路径、写入内容、overwrite 或 append。
- 输出含义：写入状态、文件大小、diff 摘要、错误信息。
- 同步特性：单次请求同步返回。

### bash

- 输入含义：命令字符串、超时、是否后台运行、后台任务描述。
- 输出含义：stdout、stderr、exit code、timeout、truncated、错误信息。
- 同步特性：首版只要求前台同步返回；后台任务语义在单独批次设计。

## Data Ownership & Responsibility

- LLM 拥有工具调用意图，但不拥有路径授权或执行授权。
- `ToolDefinition` 的工具 schema 与 metadata 由 `core/tools` 拥有。
- 工具参数的风险分类由 `core/policy` 拥有。
- 用户授权、allow 记忆和拒绝原因由 `core/permission` 拥有。
- cwd、workspace roots、additional roots、skill roots、run_dir、env、timeout 由 `core/shell` 拥有。
- 容器执行结果、stdout/stderr 原始数据、exit code 和 timeout 状态由 `core/sandbox` 拥有。
- 文件内容本身仍归属于用户 workspace 或 skill run directory；工具只在授权范围内读取或修改。
- 工具返回给 LLM 的 `ToolCallResult` 由 `core/tools` 负责格式化，不能包含未经截断的大型内容或敏感文件内容。
