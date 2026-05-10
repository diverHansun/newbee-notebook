"""Permission gateway contracts for policy ASK decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class PermissionChoice(StrEnum):
    ONCE = "once"
    ALWAYS_SESSION = "always_session"
    ALWAYS_PERSIST = "always_persist"
    REJECT = "reject"
    REJECT_WITH_SUGGESTION = "reject_with_suggestion"


class PermissionResponseKind(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_PERMISSION = "needs_permission"
    REJECT_WITH_SUGGESTION = "reject_with_suggestion"


@dataclass(frozen=True)
class RejectionWithSuggestion:
    capability_signature: str
    suggestion: str


@dataclass(frozen=True)
class PermissionRequest:
    session_id: str
    assistant_turn_id: str
    tool_call_id: str
    capability_signature: str
    tool_name: str
    args_summary: dict[str, Any]
    risk_level: str
    skill_name: str | None = None
    content_hash: str = ""


@dataclass(frozen=True)
class PermissionResponse:
    kind: PermissionResponseKind
    reason: str
    rejection: RejectionWithSuggestion | None = None

    @property
    def allowed(self) -> bool:
        return self.kind is PermissionResponseKind.ALLOW

    @property
    def requires_permission(self) -> bool:
        return self.kind is PermissionResponseKind.NEEDS_PERMISSION

    @property
    def requires_confirmation(self) -> bool:
        return self.requires_permission

    @classmethod
    def allow(cls, *, reason: str) -> "PermissionResponse":
        return cls(kind=PermissionResponseKind.ALLOW, reason=reason)

    @classmethod
    def deny(cls, *, reason: str) -> "PermissionResponse":
        return cls(kind=PermissionResponseKind.DENY, reason=reason)

    @classmethod
    def needs_permission_response(
        cls,
        *,
        reason: str = "allow_not_found",
    ) -> "PermissionResponse":
        return cls(kind=PermissionResponseKind.NEEDS_PERMISSION, reason=reason)

    @classmethod
    def needs_permission(cls, *, reason: str = "allow_not_found") -> "PermissionResponse":
        return cls.needs_permission_response(reason=reason)

    @classmethod
    def needs_confirmation(cls, *, reason: str = "allow_not_found") -> "PermissionResponse":
        return cls.needs_permission_response(reason=reason)

    @classmethod
    def needs_confirmation_response(
        cls,
        *,
        reason: str = "allow_not_found",
    ) -> "PermissionResponse":
        return cls.needs_permission_response(reason=reason)

    @classmethod
    def reject_with_suggestion(
        cls,
        *,
        capability_signature: str,
        suggestion: str,
        reason: str = "user_rejected_with_suggestion",
    ) -> "PermissionResponse":
        return cls(
            kind=PermissionResponseKind.REJECT_WITH_SUGGESTION,
            reason=reason,
            rejection=RejectionWithSuggestion(
                capability_signature=capability_signature,
                suggestion=suggestion,
            ),
        )


def normalize_permission_choice(value: Any) -> tuple[PermissionChoice, str]:
    """Normalize legacy bools, rich strings, or rich response payloads."""
    suggestion = ""
    raw: Any = value
    if isinstance(value, dict):
        suggestion = str(value.get("suggestion") or "").strip()
        if "approved" in value and value.get("response") is None and value.get("choice") is None:
            raw = bool(value.get("approved"))
        else:
            raw = value.get("response") or value.get("choice")

    if isinstance(raw, bool):
        return (PermissionChoice.ONCE if raw else PermissionChoice.REJECT), suggestion

    try:
        choice = PermissionChoice(str(raw or "").strip().lower())
    except ValueError:
        choice = PermissionChoice.REJECT

    if choice is PermissionChoice.REJECT and suggestion:
        return PermissionChoice.REJECT_WITH_SUGGESTION, suggestion
    return choice, suggestion
