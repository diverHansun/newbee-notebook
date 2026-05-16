# Filesystem Tools Test Plan

## Module Test Profile

- 模块原型：混合模块。`core/tools/filesystem` 是工具适配模块加少量纯逻辑；`core/tools/bash.py` 是工具适配模块；`core/shell` 是基础设施模块。
- 主要测试类型：unit + contract；与 sandbox 真实执行相关的场景使用 integration 或 smoke。
- Mock 边界：unit 测试 mock `core/shell`、`core/sandbox`、permission 结果和外部进程；contract 测试验证 `ToolDefinition` schema 与 metadata；integration 测试使用临时目录或测试 sandbox，不 mock 被集成的两个真实组件。
- 测试归属目录：
  - `newbee_notebook/tests/unit/core/tools/filesystem/`
  - `newbee_notebook/tests/unit/core/tools/test_bash_tool.py`
  - `newbee_notebook/tests/unit/core/shell/`
  - `newbee_notebook/tests/unit/core/tools/test_filesystem_tool_contracts.py`
  - `newbee_notebook/tests/integration/core/shell/` for sandbox-backed execution.

## Test Scope

覆盖：

- 文件工具参数校验、路径范围校验、敏感文件保护、文本/二进制判断。
- `read_file` 的行号输出、offset、tail-style negative offset、行数和字节截断。
- `glob_files` 的目录范围、过宽 pattern 拒绝、排序、数量截断。
- `grep_files` 的输出模式、context options、glob filter、大小写、超时、敏感文件过滤。
- `edit_file` 的单次替换、全部替换、未命中、多重命中、CRLF 保留、diff 生成。
- `write_file` 的 overwrite、append、父目录缺失、目标越界、diff 生成。
- `bash` 的空命令、超时、非零退出、输出截断、sandbox executor 调用契约。
- 工具 metadata 是否能被 Phase 2 policy 正确分类。

不覆盖：

- `core/policy` 的矩阵决策逻辑；它属于 `newbee_notebook/tests/unit/core/policy/`。
- `core/permission` 的 allow 存储、确认队列和拒绝语义；它属于 `newbee_notebook/tests/unit/core/permission/`。
- Docker 参数硬化细节；它属于 `newbee_notebook/tests/unit/core/sandbox/` 与 integration/smoke。
- 前端 diff 展示和确认卡渲染。
- skill 安装、卸载和 content hash 计算。

## Critical Scenarios

### read_file

- 读取允许范围内的文本文件时，返回带行号内容、读取行数和总行数。
- `line_offset=0` 时参数校验失败。
- negative offset 超过最大允许行数时参数校验失败。
- 文件不存在时返回 `file_not_found` 类错误，不抛未处理异常。
- 目标为目录时返回 `not_a_file` 类错误。
- 目标为二进制、图片或视频时返回 `not_text` 或 `unsupported_file_type` 类错误。
- 命中敏感文件模式时返回 `sensitive_file` 类错误，结果不包含文件内容。
- 内容超过最大字节数时返回截断标记，并提示继续分页读取。

### glob_files

- 在允许目录内匹配文件时，返回排序后的相对路径。
- directory 越出 workspace/additional roots/skill roots 时拒绝。
- pattern 从 `**` 开始且会递归全局搜索时拒绝，并给出缩小范围建议。
- 匹配数量超过上限时只返回前 N 条并标记截断。
- `include_dirs=false` 时只返回文件。

### grep_files

- `files_with_matches` 返回匹配文件路径。
- `content` 返回匹配行和行号，并支持 before/after/context。
- `count_matches` 返回每个文件匹配数量。
- pattern 以 `-` 开头时仍被当作搜索模式，而不是命令参数。
- include ignored 文件时仍过滤敏感文件。
- 搜索超时时，若已有结果则返回 partial；无结果则返回 timeout 错误。
- 输出超过限制时丢弃不完整尾行并标记 truncated。

### edit_file

- 单个 old string 命中时写回新内容并返回 diff。
- old string 未命中时不写文件并返回 `string_not_found`。
- old string 多次出现且 `replace_all=false` 时不写文件并返回 `multiple_occurrences`。
- `replace_all=true` 时替换全部匹配并返回替换数量。
- CRLF 文件中使用 LF old string 匹配时，写回内容保持匹配区域原换行风格。
- 目标为二进制或敏感文件时拒绝写入。

### write_file

- overwrite 已有文件时返回旧内容到新内容的 diff。
- append 已有文件时保留旧内容并追加新内容。
- 写入新文件时父目录必须存在。
- mode 不是 overwrite 或 append 时参数校验失败。
- 目标越界或敏感路径时拒绝写入。

### bash

- 空 command 返回参数错误。
- 前台 timeout 超过上限时参数校验失败。
- 命令超时后返回 timeout 错误，sandbox 进程被终止。
- 非零 exit code 返回失败结果并保留截断后的 stdout/stderr。
- 输出超过限制时返回 truncated 标记。
- 工具只调用 `core/shell` executor，不直接调用 `subprocess` 或 host shell。

## Contract Specification

### Tool Schema

- 每个工具必须暴露稳定 `name`、`description`、`parameters`。
- 每个工具必须设置 `tool_class` 与 `risk_level`。
- `bash` 必须设置 `sandbox_required=true`。
- 读工具默认 metadata 应使 default policy 允许执行。
- 写入和 bash 工具默认 metadata 应使 default policy 进入 ASK 或更严格路径。

### Tool Result

- 成功结果使用 `ToolCallResult(content=..., error=None)`。
- 失败结果使用 `ToolCallResult(content="", error="...")` 或等价结构化错误映射。
- 大型输出必须截断后再进入 `content`。
- 写入类工具的结果必须包含可供日志和确认卡使用的 diff 或 diff 摘要。

## Integration Points

- `ToolRegistry` 能发现所有内置文件工具。
- `AgentLoop` 在调用工具前已经执行 policy/permission，因此工具测试不重复验证 allow 存储。
- `core/shell` 为所有文件工具提供相同路径策略，避免每个工具重复实现不同的范围判断。
- `bash` 与 `core/sandbox` 的集成测试验证命令请求、cwd、env、timeout 和输出限制被正确传递。

## Verification Strategy

首批文件工具实现的最小验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/tools/filesystem/ -q
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/tools/test_bash_tool.py newbee_notebook/tests/unit/core/shell/ -q
```

与 policy/permission 的回归验证：

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/core/policy/ newbee_notebook/tests/unit/core/permission/ newbee_notebook/tests/unit/core/engine/ -q
```

有 sandbox 环境时的集成验证：

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/integration/core/shell/ -q
```

Marker 要求：

- 文件工具纯逻辑测试使用 `@pytest.mark.unit`。
- 工具 schema 契约测试使用 `@pytest.mark.contract`，或在现有 unit 目录中明确只断言内部 schema 生成。
- sandbox 真实执行测试使用 `@pytest.mark.integration`。
- 超过 10 秒的测试叠加 `@pytest.mark.slow`。
