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


@dataclass(frozen=True)
class ConfirmationMeta:
    action_type: str   # create | update | delete | confirm
    target_type: str   # note | diagram | document


@dataclass(frozen=True)
class SkillManifest:
    name: str
    slash_command: str
    description: str
    tools: list[ToolDefinition]
    system_prompt_addition: str = ""
    confirmation_required: frozenset[str] = field(default_factory=frozenset)
    confirmation_meta: dict[str, ConfirmationMeta] = field(default_factory=dict)
    force_first_tool_call: bool = False
    required_tool_call_before_response: str | None = None


class SkillProvider(Protocol):
    @property
    def skill_name(self) -> str: ...

    @property
    def slash_commands(self) -> list[str]: ...

    def build_manifest(self, context: SkillContext) -> SkillManifest: ...
