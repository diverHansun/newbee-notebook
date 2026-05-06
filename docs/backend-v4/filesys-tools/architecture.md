# Filesystem Tools Architecture

## Architecture Overview

`filesys-tools` 采用“工具外壳 + 环境服务 + 执行后端”的分层结构。

- Tool Facade：位于 `newbee_notebook/core/tools/`，向 Agent 暴露 `read_file`、`glob_files`、`grep_files`、`edit_file`、`write_file`、`bash` 等工具定义。它负责参数 schema、工具描述、policy metadata、结果格式和用户可理解的错误信息。
- Filesystem Operation Layer：位于 `core/tools/filesystem/` 内部，承载文本读取、glob、grep、字符串替换、写入预览、diff 生成、输出截断等工具内逻辑。
- Shell Environment：位于未来的 `newbee_notebook/core/shell/`，负责提供 cwd、workspace roots、additional roots、skill roots、run_dir、env、timeout、输出限制和路径访问策略。
- Sandbox Bridge：位于 `newbee_notebook/core/sandbox/`，负责真实命令执行、容器隔离、挂载和网络控制。`bash` 必须通过该层执行。
- Policy/Permission Gate：位于工具执行之前。工具只声明自身风险元数据，不直接调用或绕过全局决策门。

核心依赖方向为：

```text
AgentLoop
  -> policy
  -> permission
  -> ToolDefinition in core/tools
  -> core/shell environment
  -> core/sandbox execution backend
```

## Design Pattern & Rationale

本模块使用 Facade + Adapter + Strategy 的组合，但保持实现克制。

- Facade：每个 Agent 可见工具提供稳定、简洁的工具契约，让 `ToolRegistry` 和 LLM 不需要理解底层环境差异。
- Adapter：`core/shell` 将当前 session、skill run、workspace、sandbox runner 等运行期差异适配成统一环境输入。
- Strategy：文件操作可以先使用受控本地实现，后续在 sandbox 可用时切换为 sandbox-backed backend；工具 schema 不因此变化。

不采用 Kimi CLI 的“工具内部审批”模式，因为 newbee-notebook 已经有全局 `policy -> permission` 链路。
不采用 DeepAgents 的 unrestricted local shell backend，因为该模式对 Web 后端和多用户场景风险过高。

## Module Structure & File Layout

建议文件布局如下：

```text
newbee_notebook/core/tools/
  filesystem/
    __init__.py
    common.py
    read.py
    glob.py
    grep.py
    edit.py
    write.py
  bash.py

newbee_notebook/core/shell/
  __init__.py
  environment.py
  path_policy.py
  executor.py
  result.py
```

职责说明：

- `core/tools/filesystem/common.py`：共享参数校验、路径结果、输出截断、敏感文件判断、文本/二进制判断、错误格式。
- `core/tools/filesystem/read.py`：读取文本文件，支持 line offset、line count、最大字节限制和行号输出。
- `core/tools/filesystem/glob.py`：在允许目录内匹配文件，限制过宽递归模式和最大返回数量。
- `core/tools/filesystem/grep.py`：搜索文件内容，支持输出模式、glob filter、上下文行、大小写选项和敏感文件过滤。
- `core/tools/filesystem/edit.py`：基于旧字符串替换生成 diff，处理未命中、多重命中、CRLF 保留和文本文件限制。
- `core/tools/filesystem/write.py`：写入或追加文本内容，生成新旧内容 diff，并限制写入范围。
- `core/tools/bash.py`：Agent 可见的 bash 工具定义，负责参数 schema 和结果映射，真实执行委托给 `core/shell`。
- `core/shell/environment.py`：描述一次工具调用可见的运行环境。
- `core/shell/path_policy.py`：集中处理路径解析、范围判断、可读写能力和敏感路径规则。
- `core/shell/executor.py`：将 bash 执行请求转换为 sandbox 执行请求。
- `core/shell/result.py`：统一 stdout、stderr、exit code、timeout、truncated 等执行结果。

稳定对外接口是 `ToolDefinition` 与工具返回的 `ToolCallResult`。其余内部文件可以随实现演进调整。

## Architectural Constraints & Trade-offs

- 当前方案把 `read/grep/glob/edit/write` 放在 `core/tools`，而不是放在 `core/shell`。代价是工具目录会增加一个子包；收益是 Agent 可见能力、环境能力和 sandbox 能力边界清晰。
- 当前方案不把 permission 逻辑写入工具内部。代价是单个工具不能独立完成审批；收益是所有工具共享同一审计、allow、拒绝和 UI 语义。
- 当前方案不直接提供 host shell 执行。代价是 `bash` 需要等待 sandbox 与 shell 环境完成；收益是不会因为早期实现而引入不可控的本机命令执行风险。
- `grep` 可以优先使用 Python 实现保证可移植性，后续在环境允许时接入 ripgrep 优化性能。代价是首版大型仓库搜索速度有限；收益是减少二进制依赖和跨平台差异。
- `edit` 首版采用字符串替换而非 AST 或 patch 语言。代价是复杂重构体验有限；收益是行为可解释、diff 可审计、测试边界清楚。
