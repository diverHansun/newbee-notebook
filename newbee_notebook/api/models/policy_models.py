"""API models for frontend agent policy preferences."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

AgentPolicyValue = Literal["default", "yolo"]
PolicyScopeValue = Literal["session", "notebook"]
PolicySourceValue = Literal["default", "session", "notebook"]


class PolicyPreferenceUpdateRequest(BaseModel):
    scope: PolicyScopeValue
    policy: AgentPolicyValue
    session_id: str | None = None

    @model_validator(mode="after")
    def _validate_session_scope(self) -> "PolicyPreferenceUpdateRequest":
        if self.scope == "session" and not str(self.session_id or "").strip():
            raise ValueError("session_id is required for session scope")
        return self


class EffectivePolicyResponse(BaseModel):
    notebook_id: str
    session_id: str | None = None
    policy: AgentPolicyValue
    source: PolicySourceValue
