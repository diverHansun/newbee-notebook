"""Build minimal activation prompts for configurable skills."""

from __future__ import annotations

from pathlib import Path

from newbee_notebook.core.skills.manifest_parser import SkillManifestMeta


class ActivationContextBuilder:
    def build_prompt(
        self,
        *,
        meta: SkillManifestMeta,
        skill_dir: str | Path,
        content_hash: str,
    ) -> str:
        del skill_dir
        return (
            "---\n"
            f"Active skill: /{meta.name}\n"
            f"Description: {meta.description}\n"
            f"Content hash: {content_hash}\n"
            f"Use the Read tool to open configs/skills/{meta.name}/SKILL.md before following this skill. "
            "Do not assume the skill body or references are already loaded.\n"
            "---"
        )
