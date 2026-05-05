from __future__ import annotations

import pytest

from newbee_notebook.core.skills.contracts import SkillContext

pytestmark = pytest.mark.unit


def test_skill_context_preserves_existing_minimal_constructor():
    context = SkillContext(notebook_id="nb-1", activated_command="/note")

    assert context.notebook_id == "nb-1"
    assert context.activated_command == "/note"
    assert context.skill_name is None
    assert context.content_hash == ""


def test_skill_context_accepts_config_skill_metadata():
    context = SkillContext(
        notebook_id="nb-1",
        activated_command="/demo",
        skill_name="demo",
        content_hash="hash123",
        skill_dir="configs/skills/demo",
        scripts_dir="configs/skills/demo/scripts",
        work_dir_mount="/work",
    )

    assert context.skill_name == "demo"
    assert context.content_hash == "hash123"
    assert context.skill_dir == "configs/skills/demo"
    assert context.scripts_dir == "configs/skills/demo/scripts"
    assert context.work_dir_mount == "/work"
