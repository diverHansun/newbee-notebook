# Backend V4 Sandbox Contract And Bash Tool Implementation Notes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development. Keep this file in UTF-8.

## Goal

实现 `core/sandbox` 的首批执行契约，并新增 Agent 可见的 `core/tools/bash.py`。本批只提供安全的执行边界和工具适配，不提供直接 host shell 执行。

## Scope

- `core/sandbox` 提供 `SandboxRequest`、`SandboxResult`、`SandboxExecutor` protocol 和默认 fail-closed executor。
- `core/shell` 新增 `ShellExecutor` 和 `ShellExecutionResult`，负责把 bash 命令转换成 sandbox `argv` 请求。
- `core/tools/bash.py` 提供 `bash` 工具 schema、policy metadata、执行结果格式化和错误映射。
- `BuiltinToolProvider` 在 agent/chat 模式暴露 `bash`；ask/explain/conclude 不暴露。
- 默认未配置真实 sandbox runner 时，`bash` 执行返回 `sandbox_unavailable`，不会调用本机 shell。

## Task List

- [X] B501 Add failing unit tests for sandbox request/result contracts and unavailable executor.
- [X] B502 Add failing unit tests for `ShellExecutor` bash-to-sandbox request translation.
- [X] B503 Add failing unit tests for `bash` tool metadata, delegation, timeout/nonzero mapping, and background rejection.
- [X] B504 Implement `SandboxRequest`, `SandboxResult`, `SandboxExecutor`, `SandboxExecutionError`, and `SandboxUnavailableError`.
- [X] B505 Implement `UnavailableSandboxExecutor` as the default fail-closed backend.
- [X] B506 Implement `ShellExecutor.execute_bash()` using sandbox `argv=("bash", "-lc", command)` and environment limits.
- [X] B507 Implement `build_bash_tool()` with `ToolClass.BASH`, `RiskLevel.DANGEROUS`, and `sandbox_required=true`.
- [X] B508 Register `bash` for agent/chat mode through `BuiltinToolProvider`.
- [X] B509 Run targeted and broader verification; confirm no direct host shell implementation was introduced.

## Acceptance Criteria

- Sandbox requests use argv sequences, not raw host shell strings.
- Empty argv and string argv are rejected.
- Request cwd/run_dir are normalized and env values are stringified.
- Without a configured sandbox executor, command execution fails closed with `sandbox_unavailable`.
- `ShellExecutor` creates sandbox requests with cwd, env, timeout, output limits, `run_dir`, and `network_enabled=false`.
- Empty bash commands fail before reaching sandbox.
- `bash` tool rejects background mode for this first batch.
- Timeout results map to `ToolCallResult.error == "timeout"`.
- Nonzero exit results map to `ToolCallResult.error == "nonzero_exit"`.
- `bash` is visible in agent/chat only and uses global policy/permission metadata.
- The implementation does not import or invoke `subprocess`, PowerShell, cmd, or another host shell backend.

## Verification

Targeted gate:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\core\sandbox newbee_notebook\tests\unit\core\shell\test_executor.py newbee_notebook\tests\unit\core\tools\test_bash_tool.py -q
```

Registration gate:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\core\tools\test_filesystem_tool_contracts.py newbee_notebook\tests\unit\core\tools\test_tool_registry.py newbee_notebook\tests\unit\core\tools\test_runtime_web_tools.py -q
```

Broader safety gate:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\core\sandbox newbee_notebook\tests\unit\core\shell newbee_notebook\tests\unit\core\tools newbee_notebook\tests\unit\core\policy newbee_notebook\tests\unit\core\permission newbee_notebook\tests\unit\core\engine newbee_notebook\tests\unit\core\session newbee_notebook\tests\unit\application\services\test_chat_runtime_routing.py newbee_notebook\tests\unit\application\services\test_chat_service_guards.py -q
```

Current result: `187 passed, 3 warnings`; warnings are existing Pydantic V2 deprecation warnings in infrastructure config and third-party vector store code.

Safety scan:

```powershell
Select-String -Path newbee_notebook\core\tools\bash.py,newbee_notebook\core\shell\executor.py,newbee_notebook\core\sandbox\*.py -Pattern "subprocess|shell=True|powershell|cmd /c|bash -lc"
```

Current result: no matches.

## Next Batch Handoff

下一批可以实现一个真实 sandbox runner，例如 Docker-backed executor。建议先用 unit 测试验证容器请求构造、挂载策略、network=false 默认、资源限制和输出截断，再把需要 Docker 的真实执行场景放进 integration/smoke 测试。
