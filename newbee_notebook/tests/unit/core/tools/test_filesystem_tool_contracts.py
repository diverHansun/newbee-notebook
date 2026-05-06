from __future__ import annotations

import pytest

from newbee_notebook.core.policy import RiskLevel, ToolClass
from newbee_notebook.core.shell import ShellEnvironment
from newbee_notebook.core.tools.builtin_provider import BuiltinToolProvider
from newbee_notebook.core.tools.filesystem import build_filesystem_tools

pytestmark = pytest.mark.unit


def test_filesystem_tools_expose_policy_metadata(tmp_path):
    tools = {tool.name: tool for tool in build_filesystem_tools(ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,)))}

    assert tools["read_file"].tool_class == ToolClass.READ
    assert tools["glob_files"].tool_class == ToolClass.READ
    assert tools["grep_files"].tool_class == ToolClass.READ
    assert tools["edit_file"].tool_class == ToolClass.EDIT
    assert tools["write_file"].tool_class == ToolClass.WRITE
    assert tools["read_file"].risk_level == RiskLevel.SAFE
    assert tools["write_file"].risk_level == RiskLevel.MODERATE


def test_builtin_provider_adds_filesystem_tools_to_agent_only(tmp_path, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    provider = BuiltinToolProvider(
        filesystem_environment=ShellEnvironment(cwd=tmp_path, workspace_roots=(tmp_path,))
    )

    agent_names = [tool.name for tool in provider.get_tools("agent")]
    ask_names = [tool.name for tool in provider.get_tools("ask")]

    assert agent_names == [
        "knowledge_base",
        "time",
        "read_file",
        "glob_files",
        "grep_files",
        "edit_file",
        "write_file",
    ]
    assert ask_names == ["knowledge_base", "time"]
