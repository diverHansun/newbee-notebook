"""Request-scoped skill contracts for runtime slash command activation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from newbee_notebook.core.tools.contracts import ToolDefinition


@dataclass(frozen=True)
class SkillContext:
    notebook_id: str
    activated_command: str
    selected_document_ids: list[str] = field(default_factory=list)
    request_message: str = ""
    skill_name: str | None = None
    content_hash: str = ""
    skill_dir: str = ""
    scripts_dir: str = ""
    work_dir_mount: str = "/work"


@dataclass(frozen=True)
class PermissionMeta:
    action_type: str = "confirm"   # create | update | delete | confirm
    target_type: str = "unknown"   # note | diagram | document


ConfirmationMeta = PermissionMeta


@dataclass(frozen=True)
class SkillManifest:
    name: str
    slash_command: str
    description: str
    tools: list[ToolDefinition]
    system_prompt_addition: str = ""
    permission_required: frozenset[str] = field(default_factory=frozenset)
    permission_meta: dict[str, PermissionMeta] = field(default_factory=dict)
    confirmation_required: frozenset[str] = field(default_factory=frozenset)
    confirmation_meta: dict[str, PermissionMeta] = field(default_factory=dict)
    force_first_tool_call: bool = False
    required_tool_call_before_response: str | frozenset[str] | None = None

    def __post_init__(self) -> None:
        permission_required = frozenset(self.permission_required or self.confirmation_required)
        permission_meta = dict(self.permission_meta or self.confirmation_meta)
        object.__setattr__(self, "permission_required", permission_required)
        object.__setattr__(self, "confirmation_required", permission_required)
        object.__setattr__(self, "permission_meta", permission_meta)
        object.__setattr__(self, "confirmation_meta", permission_meta)


class SkillProvider(Protocol):
    @property
    def skill_name(self) -> str: ...

    @property
    def slash_commands(self) -> list[str]: ...

    def build_manifest(self, context: SkillContext) -> SkillManifest: ...
