"""Shell environment and path policy helpers for agent tools."""

from newbee_notebook.core.shell.environment import (
    ShellEnvironment,
    build_default_shell_environment,
)
from newbee_notebook.core.shell.executor import ShellExecutor
from newbee_notebook.core.shell.path_policy import PathAccessError, PathPolicy
from newbee_notebook.core.shell.result import ShellExecutionResult
from newbee_notebook.core.shell.background_tasks import (
    BackgroundShellTaskManager,
    BackgroundShellTaskOutput,
    BackgroundShellTaskRecord,
)

__all__ = [
    "BackgroundShellTaskManager",
    "BackgroundShellTaskOutput",
    "BackgroundShellTaskRecord",
    "PathAccessError",
    "PathPolicy",
    "ShellExecutionResult",
    "ShellEnvironment",
    "ShellExecutor",
    "build_default_shell_environment",
]
