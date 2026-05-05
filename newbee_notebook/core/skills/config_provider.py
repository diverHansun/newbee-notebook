"""Provider adapter for user-installed config skills."""

from __future__ import annotations

from pathlib import Path

from newbee_notebook.core.skills.activation import ActivationContextBuilder
from newbee_notebook.core.skills.contracts import SkillContext, SkillManifest
from newbee_notebook.core.skills.manifest_parser import SkillManifestMeta


class ConfigSkillProvider:
    def __init__(
        self,
        *,
        meta: SkillManifestMeta,
        skill_dir: str | Path,
        content_hash: str,
        enabled: bool = True,
        activation_builder: ActivationContextBuilder | None = None,
    ) -> None:
        self._meta = meta
        self._skill_dir = Path(skill_dir)
        self._content_hash = str(content_hash or "")
        self.enabled = bool(enabled)
        self._activation_builder = activation_builder or ActivationContextBuilder()

    @property
    def skill_name(self) -> str:
        return self._meta.name

    @property
    def content_hash(self) -> str:
        return self._content_hash

    @property
    def skill_dir(self) -> str:
        return str(self._skill_dir)

    @property
    def scripts_dir(self) -> str:
        return str(self._skill_dir / "scripts")

    @property
    def work_dir_mount(self) -> str:
        return "/work"

    @property
    def slash_commands(self) -> list[str]:
        return [f"/{self._meta.name}"]

    def build_manifest(self, context: SkillContext) -> SkillManifest:
        return SkillManifest(
            name=self._meta.name,
            slash_command=context.activated_command,
            description=self._meta.description,
            tools=[],
            system_prompt_addition=self._activation_builder.build_prompt(
                meta=self._meta,
                skill_dir=self._skill_dir,
                content_hash=self._content_hash,
            ),
        )
