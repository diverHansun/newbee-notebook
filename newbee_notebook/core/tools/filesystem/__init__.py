"""Agent-visible filesystem tools."""

from newbee_notebook.core.tools.filesystem.edit import build_edit_file_tool
from newbee_notebook.core.tools.filesystem.glob import build_glob_files_tool
from newbee_notebook.core.tools.filesystem.grep import build_grep_files_tool
from newbee_notebook.core.tools.filesystem.read import build_read_file_tool
from newbee_notebook.core.tools.filesystem.write import build_write_file_tool


def build_filesystem_tools(environment):
    return [
        build_read_file_tool(environment),
        build_glob_files_tool(environment),
        build_grep_files_tool(environment),
        build_edit_file_tool(environment),
        build_write_file_tool(environment),
    ]


__all__ = [
    "build_edit_file_tool",
    "build_filesystem_tools",
    "build_glob_files_tool",
    "build_grep_files_tool",
    "build_read_file_tool",
    "build_write_file_tool",
]
