from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.skills.activation import ActivationContextBuilder
from newbee_notebook.core.skills.config_provider import ConfigSkillProvider
from newbee_notebook.core.skills.contracts import SkillContext
from newbee_notebook.core.skills.manifest_parser import SkillManifestMeta

pytestmark = pytest.mark.unit


def test_config_provider_builds_prompt_only_manifest(tmp_path: Path):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo\n"
        "description: Prepare a concise notebook brief.\n"
        "---\n"
        "\n"
        "The full body must be read later by the agent.\n",
        encoding="utf-8",
    )
    meta = SkillManifestMeta(
        name="demo",
        description="Prepare a concise notebook brief.",
    )
    provider = ConfigSkillProvider(
        meta=meta,
        skill_dir=skill_dir,
        content_hash="abc123",
        enabled=True,
        activation_builder=ActivationContextBuilder(),
    )

    manifest = provider.build_manifest(
        SkillContext(
            notebook_id="notebook-1",
            activated_command="/demo",
            request_message="make one",
        )
    )

    assert manifest.name == "demo"
    assert manifest.slash_command == "/demo"
    assert manifest.tools == []
    assert "Prepare a concise notebook brief." in manifest.system_prompt_addition
    assert "configs/skills/demo/SKILL.md" in manifest.system_prompt_addition
    assert "The full body must be read later" not in manifest.system_prompt_addition
