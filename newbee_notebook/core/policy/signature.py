"""Stable capability signature generation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from newbee_notebook.core.policy.contracts import SkillPolicyContext


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_json_value(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, set):
        normalized_items = [_normalize_json_value(item) for item in value]
        return sorted(
            normalized_items,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class SignatureBuilder:
    def build(
        self,
        *,
        tool_name: str,
        tool_args: dict[str, Any] | None,
        skill_context: SkillPolicyContext | Any | None = None,
    ) -> str:
        normalized_args = _normalize_json_value(tool_args or {})
        canonical = json.dumps(
            normalized_args,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        arg_hash8 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
        context = SkillPolicyContext.from_any(skill_context)
        scope = "global"
        if context is not None:
            scope = f"skill:{context.name}@{context.content_hash}"
        return f"{scope}:{str(tool_name)}:{arg_hash8}"
