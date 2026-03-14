"""Unit tests for batch-2 runtime mode policies."""

from unittest.mock import AsyncMock

from newbee_notebook.core.engine.mode_config import ModeConfigFactory
from newbee_notebook.core.tools.contracts import ToolDefinition
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.value_objects.mode_type import ModeType, normalize_runtime_mode


def _tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"{name} tool",
        parameters={"type": "object"},
        execute=AsyncMock(),
    )


def test_mode_type_includes_agent_runtime_and_chat_alias():
    assert ModeType.AGENT.value == "agent"
    assert normalize_runtime_mode(ModeType.CHAT) is ModeType.AGENT
    assert normalize_runtime_mode("chat") is ModeType.AGENT


def test_agent_policy_stays_open_loop_and_accepts_multiple_tools():
    config = ModeConfigFactory.build("agent", [_tool("knowledge_base"), _tool("time")])

    assert config.mode_name == "agent"
    assert config.loop_policy.execution_style == "open_loop"
    assert config.tool_policy.allowed_tool_names == ["knowledge_base", "time"]
    assert config.source_policy.grounded_required is False


def test_ask_policy_prefers_knowledge_base_without_forcing_every_iteration():
    config = ModeConfigFactory.build("ask", [_tool("knowledge_base"), _tool("time")])

    assert config.mode_name == "ask"
    assert config.loop_policy.execution_style == "open_loop"
    assert config.loop_policy.require_tool_every_iteration is False
    assert config.loop_policy.first_turn_tool_repair_name == "knowledge_base"
    assert config.loop_policy.first_turn_tool_repair_limit == 1
    assert config.loop_policy.first_turn_tool_repair_force_choice is True
    assert config.tool_policy.default_tool_name == "knowledge_base"
    assert config.tool_policy.default_tool_args_template == {"search_type": "hybrid", "max_results": 5}


def test_message_entity_defaults_to_agent_canonical_mode():
    assert Message().mode is ModeType.AGENT


def test_explain_policy_requires_grounded_document_first_retrievals():
    config = ModeConfigFactory.build("explain", [_tool("knowledge_base")])

    assert config.mode_name == "explain"
    assert config.loop_policy.execution_style == "retrieval_required_loop"
    assert config.loop_policy.max_retrieval_iterations == 3
    assert config.loop_policy.required_tool_name == "knowledge_base"
    assert config.tool_policy.initial_scope == "document"
    assert config.tool_policy.allow_scope_relaxation is True
    assert config.tool_policy.default_tool_args_template == {"search_type": "keyword", "max_results": 5}


def test_conclude_policy_prefers_hybrid_retrieval_with_larger_result_window():
    config = ModeConfigFactory.build("conclude", [_tool("knowledge_base")])

    assert config.mode_name == "conclude"
    assert config.loop_policy.execution_style == "retrieval_required_loop"
    assert config.loop_policy.max_retrieval_iterations == 3
    assert config.tool_policy.default_tool_args_template == {"search_type": "hybrid", "max_results": 8}
