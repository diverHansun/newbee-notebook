"""Pure policy decision engine for runtime tool calls."""

from __future__ import annotations

import re

from newbee_notebook.core.policy.contracts import (
    AgentPolicy,
    DecideRequest,
    Decision,
    PolicyVerdict,
    RiskLevel,
    ToolClass,
)
from newbee_notebook.core.policy.signature import SignatureBuilder


def _coerce_agent_policy(value: AgentPolicy | str | None) -> AgentPolicy:
    if value is None or str(value).strip() == "":
        return AgentPolicy.DEFAULT
    try:
        return AgentPolicy(str(value).strip().lower())
    except ValueError:
        return AgentPolicy.DEFAULT


def _coerce_tool_class(value: ToolClass | str) -> ToolClass:
    raw = str(value).strip().lower()
    if raw == "bash":
        return ToolClass.SHELL
    try:
        return ToolClass(raw)
    except ValueError:
        return ToolClass.CUSTOM


def _coerce_risk_level(value: RiskLevel | str) -> RiskLevel:
    try:
        return RiskLevel(str(value).strip().lower())
    except ValueError:
        return RiskLevel.MODERATE


def _canonical_tool_name(tool_name: str) -> str:
    raw = str(tool_name or "").strip()
    return "shell" if raw.lower() == "bash" else raw


class DangerousCommandMatcher:
    _PATTERNS = (
        re.compile(r"\brm\s+-[^\n]*r[^\n]*f\b", re.IGNORECASE),
        re.compile(r"\bsudo\b", re.IGNORECASE),
        re.compile(r"\bdd\s+if=", re.IGNORECASE),
        re.compile(r"\bmkfs(?:\.\w+)?\b", re.IGNORECASE),
        re.compile(r"\bchmod\s+-R\s+777\b", re.IGNORECASE),
        re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sh|bash)\b", re.IGNORECASE),
        re.compile(r"\bRemove-Item\b[^\n]*\b-Recurse\b", re.IGNORECASE),
    )

    def maybe_upgrade(
        self,
        *,
        command: str,
        current_risk: RiskLevel,
    ) -> RiskLevel:
        if current_risk == RiskLevel.DANGEROUS:
            return current_risk
        normalized = str(command or "")
        if any(pattern.search(normalized) for pattern in self._PATTERNS):
            return RiskLevel.DANGEROUS
        return current_risk


class DecisionMatrix:
    def lookup(
        self,
        *,
        agent_policy: AgentPolicy,
        tool_class: ToolClass,
        risk_level: RiskLevel,
    ) -> PolicyVerdict:
        if agent_policy == AgentPolicy.YOLO:
            return PolicyVerdict.ALLOW
        if tool_class == ToolClass.READ:
            return PolicyVerdict.ALLOW
        if tool_class == ToolClass.SHELL:
            return (
                PolicyVerdict.ASK
                if risk_level == RiskLevel.DANGEROUS
                else PolicyVerdict.ALLOW
            )
        if tool_class == ToolClass.MCP:
            return (
                PolicyVerdict.ALLOW
                if risk_level == RiskLevel.SAFE
                else PolicyVerdict.ASK
            )
        return PolicyVerdict.ASK


class PolicyDecider:
    def __init__(
        self,
        *,
        signature_builder: SignatureBuilder | None = None,
        dangerous_command_matcher: DangerousCommandMatcher | None = None,
        decision_matrix: DecisionMatrix | None = None,
    ) -> None:
        self._signature_builder = signature_builder or SignatureBuilder()
        self._dangerous_command_matcher = (
            dangerous_command_matcher or DangerousCommandMatcher()
        )
        self._decision_matrix = decision_matrix or DecisionMatrix()

    def decide(self, request: DecideRequest) -> Decision:
        agent_policy = _coerce_agent_policy(request.agent_policy)
        tool_class = _coerce_tool_class(request.tool_class)
        risk_level = _coerce_risk_level(request.risk_level)

        tool_name = _canonical_tool_name(request.tool_name)

        if agent_policy != AgentPolicy.YOLO and tool_class == ToolClass.SHELL:
            command = str(request.tool_args.get("command") or "")
            risk_level = self._dangerous_command_matcher.maybe_upgrade(
                command=command,
                current_risk=risk_level,
            )

        verdict = self._decision_matrix.lookup(
            agent_policy=agent_policy,
            tool_class=tool_class,
            risk_level=risk_level,
        )
        signature = self._signature_builder.build(
            tool_name=tool_name,
            tool_args=request.tool_args,
            skill_context=request.skill_context,
        )
        return Decision(
            verdict=verdict,
            capability_signature=signature,
            reason=self._reason(
                agent_policy=agent_policy,
                tool_class=tool_class,
                risk_level=risk_level,
                verdict=verdict,
            ),
            agent_policy=agent_policy,
            tool_class=tool_class,
            risk_level=risk_level,
        )

    @staticmethod
    def _reason(
        *,
        agent_policy: AgentPolicy,
        tool_class: ToolClass,
        risk_level: RiskLevel,
        verdict: PolicyVerdict,
    ) -> str:
        if agent_policy == AgentPolicy.YOLO:
            return "yolo policy allows tool execution"
        if tool_class == ToolClass.SHELL and risk_level == RiskLevel.DANGEROUS:
            return "default policy requires approval for dangerous shell tools"
        if verdict == PolicyVerdict.ALLOW:
            return f"default policy allows {tool_class.value} tools"
        return f"default policy requires approval for {tool_class.value} tools"
