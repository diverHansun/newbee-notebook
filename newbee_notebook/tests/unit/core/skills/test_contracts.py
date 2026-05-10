from __future__ import annotations

import pytest

from newbee_notebook.core.skills.contracts import PermissionMeta, SkillContext, SkillManifest

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


def test_skill_manifest_mirrors_legacy_confirmation_fields_to_permission_fields():
    manifest = SkillManifest(
        name="demo",
        slash_command="/demo",
        description="demo",
        tools=[],
        confirmation_required=frozenset({"update_demo"}),
        confirmation_meta={
            "update_demo": PermissionMeta(action_type="update", target_type="demo")
        },
    )

    assert manifest.permission_required == frozenset({"update_demo"})
    assert manifest.permission_meta["update_demo"].target_type == "demo"
    assert manifest.confirmation_required == manifest.permission_required


def test_skill_manifest_prefers_canonical_permission_fields_when_legacy_differs():
    manifest = SkillManifest(
        name="demo",
        slash_command="/demo",
        description="demo",
        tools=[],
        permission_required=frozenset({"update_demo"}),
        permission_meta={
            "update_demo": PermissionMeta(action_type="update", target_type="demo")
        },
        confirmation_required=frozenset({"delete_demo"}),
        confirmation_meta={
            "delete_demo": PermissionMeta(action_type="delete", target_type="demo")
        },
    )

    assert manifest.permission_required == frozenset({"update_demo"})
    assert manifest.confirmation_required == manifest.permission_required
    assert manifest.confirmation_meta == manifest.permission_meta
