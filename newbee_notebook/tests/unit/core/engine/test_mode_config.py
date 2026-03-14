from __future__ import annotations

from newbee_notebook.core.engine.mode_config import ModeConfigFactory
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition
from newbee_notebook.domain.value_objects.mode_type import ModeType, normalize_runtime_mode


async def _noop(_: dict) -> ToolCallResult:
    return ToolCallResult(content="ok")


def _tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"{name} tool",
        parameters={"type": "object", "properties": {}},
        execute=_noop,
    )


def test_mode_type_adds_agent_and_maps_chat_alias_to_agent_runtime():
    assert ModeType.AGENT.value == "agent"
    assert normalize_runtime_mode("chat") is ModeType.AGENT
    assert normalize_runtime_mode(ModeType.CHAT) is ModeType.AGENT
    assert normalize_runtime_mode("ask") is ModeType.ASK


def test_mode_config_factory_builds_open_loop_agent_policy():
    config = ModeConfigFactory.build(mode="agent", tools=[_tool("knowledge_base"), _tool("time")])

    assert config.mode_name == "agent"
    assert config.loop_policy.execution_style == "open_loop"
    assert config.loop_policy.require_tool_every_iteration is False
    assert config.loop_policy.max_low_quality_tool_streak == 3
    assert config.loop_policy.low_quality_tool_name == "knowledge_base"
    assert config.loop_policy.low_quality_bands == ("low", "empty")
    assert config.tool_policy.allowed_tool_names == ["knowledge_base", "time"]
    assert config.tool_policy.initial_scope == "mixed"


def test_mode_config_factory_builds_explain_policy_with_document_scope_and_grounded_sources():
    config = ModeConfigFactory.build(mode="explain", tools=[_tool("knowledge_base")])

    assert config.mode_name == "explain"
    assert config.loop_policy.execution_style == "retrieval_required_loop"
    assert config.loop_policy.required_tool_name == "knowledge_base"
    assert config.loop_policy.require_tool_every_iteration is True
    assert config.loop_policy.max_retrieval_iterations == 3
    assert config.tool_policy.allowed_tool_names == ["knowledge_base"]
    assert config.tool_policy.default_tool_name == "knowledge_base"
    assert config.tool_policy.default_tool_args_template["search_type"] == "keyword"
    assert config.tool_policy.initial_scope == "document"
    assert config.source_policy.grounded_required is True


def test_mode_config_factory_builds_conclude_policy_with_hybrid_defaults():
    config = ModeConfigFactory.build(mode="conclude", tools=[_tool("knowledge_base")])

    assert config.loop_policy.execution_style == "retrieval_required_loop"
    assert config.loop_policy.max_retrieval_iterations == 3
    assert config.tool_policy.default_tool_args_template["search_type"] == "hybrid"
    assert config.tool_policy.default_tool_args_template["max_results"] == 8
    assert config.tool_policy.initial_scope == "document"
