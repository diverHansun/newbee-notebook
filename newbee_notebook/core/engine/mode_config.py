"""Mode policies for the batch-2 runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from newbee_notebook.core.tools.contracts import ToolDefinition
from newbee_notebook.domain.value_objects.mode_type import ModeType, normalize_runtime_mode


@dataclass(frozen=True)
class LoopPolicy:
    execution_style: str
    max_total_iterations: int
    max_retrieval_iterations: int = 0
    required_tool_name: str | None = None
    require_tool_every_iteration: bool = False
    synthesis_quality_bands: tuple[str, ...] = ()
    low_quality_tool_name: str | None = None
    low_quality_bands: tuple[str, ...] = ()
    max_low_quality_tool_streak: int = 0
    first_turn_tool_repair_name: str | None = None
    first_turn_tool_repair_limit: int = 0
    first_turn_tool_repair_force_choice: bool = False
    invalid_tool_repair_limit: int = 2
    allow_early_synthesis: bool = True
    force_synthesis_after_limit: bool = True
    emit_tool_events: bool = True


@dataclass(frozen=True)
class ToolPolicy:
    allowed_tool_names: list[str]
    default_tool_name: str | None
    default_tool_args_template: dict[str, Any] = field(default_factory=dict)
    llm_can_override_fields: list[str] = field(default_factory=list)
    initial_scope: str = "mixed"
    allow_scope_relaxation: bool = False
    scope_relaxation_rule: str | None = None


@dataclass(frozen=True)
class SourcePolicy:
    grounded_required: bool = False


@dataclass(frozen=True)
class ModeConfig:
    mode_name: str
    loop_policy: LoopPolicy
    tool_policy: ToolPolicy
    source_policy: SourcePolicy
    tools: list[ToolDefinition]


class ModeConfigFactory:
    @staticmethod
    def build(mode: str | ModeType, tools: list[ToolDefinition]) -> ModeConfig:
        runtime_mode = normalize_runtime_mode(mode)
        allowed_tool_names = [tool.name for tool in tools]

        if runtime_mode is ModeType.AGENT:
            return ModeConfig(
                mode_name="agent",
                loop_policy=LoopPolicy(
                    execution_style="open_loop",
                    max_total_iterations=50,
                    low_quality_tool_name="knowledge_base",
                    low_quality_bands=("low", "empty"),
                    max_low_quality_tool_streak=2,
                ),
                tool_policy=ToolPolicy(
                    allowed_tool_names=allowed_tool_names,
                    default_tool_name=(allowed_tool_names[0] if allowed_tool_names else None),
                    initial_scope="mixed",
                ),
                source_policy=SourcePolicy(grounded_required=False),
                tools=tools,
            )

        if runtime_mode is ModeType.ASK:
            return ModeConfig(
                mode_name="ask",
                loop_policy=LoopPolicy(
                    execution_style="open_loop",
                    max_total_iterations=50,
                    first_turn_tool_repair_name="knowledge_base",
                    first_turn_tool_repair_limit=1,
                    first_turn_tool_repair_force_choice=True,
                ),
                tool_policy=ToolPolicy(
                    allowed_tool_names=allowed_tool_names,
                    default_tool_name="knowledge_base" if "knowledge_base" in allowed_tool_names else None,
                    default_tool_args_template={"search_type": "hybrid", "max_results": 5},
                    llm_can_override_fields=["query", "search_type", "max_results", "filter_document_id"],
                    initial_scope="notebook",
                ),
                source_policy=SourcePolicy(grounded_required=True),
                tools=tools,
            )

        if runtime_mode is ModeType.EXPLAIN:
            return ModeConfig(
                mode_name="explain",
                loop_policy=LoopPolicy(
                    execution_style="retrieval_required_loop",
                    max_total_iterations=12,
                    max_retrieval_iterations=3,
                    required_tool_name="knowledge_base",
                    require_tool_every_iteration=True,
                    synthesis_quality_bands=("high",),
                ),
                tool_policy=ToolPolicy(
                    allowed_tool_names=allowed_tool_names,
                    default_tool_name="knowledge_base",
                    default_tool_args_template={"search_type": "keyword", "max_results": 5},
                    llm_can_override_fields=["query", "search_type", "max_results", "filter_document_id"],
                    initial_scope="document",
                    allow_scope_relaxation=True,
                    scope_relaxation_rule="document -> notebook",
                ),
                source_policy=SourcePolicy(grounded_required=True),
                tools=tools,
            )

        if runtime_mode is ModeType.CONCLUDE:
            return ModeConfig(
                mode_name="conclude",
                loop_policy=LoopPolicy(
                    execution_style="retrieval_required_loop",
                    max_total_iterations=12,
                    max_retrieval_iterations=3,
                    required_tool_name="knowledge_base",
                    require_tool_every_iteration=True,
                    synthesis_quality_bands=("high", "medium"),
                ),
                tool_policy=ToolPolicy(
                    allowed_tool_names=allowed_tool_names,
                    default_tool_name="knowledge_base",
                    default_tool_args_template={"search_type": "hybrid", "max_results": 8},
                    llm_can_override_fields=["query", "search_type", "max_results", "filter_document_id"],
                    initial_scope="document",
                    allow_scope_relaxation=True,
                    scope_relaxation_rule="document -> notebook",
                ),
                source_policy=SourcePolicy(grounded_required=True),
                tools=tools,
            )

        raise ValueError(f"unsupported mode: {mode}")
