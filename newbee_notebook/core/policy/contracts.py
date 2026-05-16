"""Policy decision contracts for runtime tool execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AgentPolicy(StrEnum):
    DEFAULT = "default"
    YOLO = "yolo"


class ToolClass(StrEnum):
    READ = "read"
    WRITE = "write"
    EDIT = "edit"
    SHELL = "shell"
    MCP = "mcp"
    CUSTOM = "custom"


class RiskLevel(StrEnum):
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"


class PolicyVerdict(StrEnum):
    ALLOW = "ALLOW"
    ASK = "ASK"


class PolicyError(Exception):
    """Raised when policy receives an invalid request."""


@dataclass(frozen=True)
class SkillPolicyContext:
    name: str
    content_hash: str = ""

    @classmethod
    def from_any(cls, value: Any) -> "SkillPolicyContext | None":
        if value is None:
            return None
        if isinstance(value, SkillPolicyContext):
            return value
        name = str(
            getattr(value, "name", None)
            or getattr(value, "skill_name", None)
            or ""
        ).strip()
        if not name:
            return None
        return cls(
            name=name,
            content_hash=str(getattr(value, "content_hash", "") or ""),
        )


@dataclass(frozen=True)
class DecideRequest:
    session_id: str
    tool_name: str
    tool_args: dict[str, Any]
    tool_class: ToolClass | str = ToolClass.READ
    risk_level: RiskLevel | str = RiskLevel.SAFE
    agent_policy: AgentPolicy | str | None = None
    skill_context: SkillPolicyContext | Any | None = None


@dataclass(frozen=True)
class Decision:
    verdict: PolicyVerdict
    capability_signature: str
    reason: str
    agent_policy: AgentPolicy
    tool_class: ToolClass
    risk_level: RiskLevel
