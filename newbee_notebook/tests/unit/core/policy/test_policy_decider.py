from __future__ import annotations

import pytest

from newbee_notebook.core.policy import (
    AgentPolicy,
    DecideRequest,
    PolicyDecider,
    PolicyVerdict,
    RiskLevel,
    ToolClass,
)

pytestmark = pytest.mark.unit


def test_default_policy_allows_read_tools_and_asks_for_write_tools():
    decider = PolicyDecider()

    read_decision = decider.decide(
        DecideRequest(
            session_id="s1",
            tool_name="knowledge_base",
            tool_args={"query": "paper title"},
            tool_class=ToolClass.READ,
            risk_level=RiskLevel.SAFE,
        )
    )
    write_decision = decider.decide(
        DecideRequest(
            session_id="s1",
            tool_name="create_note",
            tool_args={"title": "Plan"},
            tool_class=ToolClass.WRITE,
            risk_level=RiskLevel.MODERATE,
        )
    )

    assert read_decision.verdict == PolicyVerdict.ALLOW
    assert write_decision.verdict == PolicyVerdict.ASK
    assert write_decision.reason == "default policy requires approval for write tools"


def test_yolo_policy_allows_write_tools_but_still_builds_signature():
    decider = PolicyDecider()

    decision = decider.decide(
        DecideRequest(
            session_id="s1",
            agent_policy=AgentPolicy.YOLO,
            tool_name="delete_note",
            tool_args={"note_id": "n1"},
            tool_class=ToolClass.WRITE,
            risk_level=RiskLevel.DANGEROUS,
        )
    )

    assert decision.verdict == PolicyVerdict.ALLOW
    assert decision.capability_signature.startswith("global:delete_note:")
    assert decision.reason == "yolo policy allows tool execution"


def test_default_policy_upgrades_dangerous_bash_commands_to_ask():
    decider = PolicyDecider()

    decision = decider.decide(
        DecideRequest(
            session_id="s1",
            tool_name="bash",
            tool_args={"command": "rm -rf /tmp/demo"},
            tool_class=ToolClass.BASH,
            risk_level=RiskLevel.SAFE,
        )
    )

    assert decision.verdict == PolicyVerdict.ASK
    assert decision.risk_level == RiskLevel.DANGEROUS
    assert "dangerous bash" in decision.reason
