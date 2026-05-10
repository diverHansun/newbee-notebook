from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from newbee_notebook.core.skills.errors import SkillNotFoundError
from newbee_notebook.core.skills.lifecycle import (
    SkillLifecycle,
    register_installed_config_skills,
)
from newbee_notebook.core.skills.registry import SkillRegistry

pytestmark = pytest.mark.unit


class _FakeSettingsService:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str) -> None:
        self.store[key] = value

    async def delete_prefix(self, prefix: str) -> None:
        for key in [key for key in self.store if key.startswith(prefix)]:
            self.store.pop(key, None)


class _FakePermissionGateway:
    def __init__(self) -> None:
        self.cleared: list[str] = []

    async def clear_skill_permissions(self, skill_name: str) -> None:
        self.cleared.append(skill_name)


def _make_skill(source_dir: Path, name: str = "demo") -> None:
    (source_dir / "scripts").mkdir(parents=True)
    (source_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "description: Prepare a concise notebook brief.\n"
        "---\n"
        "\n"
        "# Body\n",
        encoding="utf-8",
    )
    (source_dir / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")


def test_preview_local_returns_manifest_without_installing(tmp_path: Path):
    source_dir = tmp_path / "source"
    _make_skill(source_dir)
    skills_root = tmp_path / "skills"
    lifecycle = SkillLifecycle(
        skills_root=skills_root,
        settings_service=_FakeSettingsService(),
        registry=SkillRegistry(),
    )

    preview = lifecycle.preview_local(source_dir)

    assert preview.manifest.name == "demo"
    assert preview.scopes == ["/demo"]
    assert "scripts/run.py" in preview.scripts
    assert preview.content_hash
    assert not (skills_root / "demo").exists()


def test_install_from_local_copies_skill_and_writes_settings(tmp_path: Path):
    source_dir = tmp_path / "source"
    _make_skill(source_dir)
    skills_root = tmp_path / "skills"
    settings = _FakeSettingsService()
    registry = SkillRegistry()
    lifecycle = SkillLifecycle(
        skills_root=skills_root,
        settings_service=settings,
        registry=registry,
    )

    record = asyncio.run(lifecycle.install_from_local(source_dir))

    assert record.name == "demo"
    assert record.enabled is True
    assert (skills_root / "demo" / "SKILL.md").exists()
    assert settings.store["skills.demo.enabled"] == "true"
    assert settings.store["skills.demo.source"] == "local"
    assert settings.store["skills.demo.content_hash"] == record.content_hash
    assert registry.match_command("/demo run") is not None


def test_set_enabled_updates_settings_and_registry_match(tmp_path: Path):
    source_dir = tmp_path / "source"
    _make_skill(source_dir)
    settings = _FakeSettingsService()
    registry = SkillRegistry()
    lifecycle = SkillLifecycle(
        skills_root=tmp_path / "skills",
        settings_service=settings,
        registry=registry,
    )
    asyncio.run(lifecycle.install_from_local(source_dir))

    asyncio.run(lifecycle.set_enabled("demo", False))

    assert settings.store["skills.demo.enabled"] == "false"
    assert registry.match_command("/demo run") is None


def test_uninstall_removes_files_settings_registry_and_permissions(tmp_path: Path):
    source_dir = tmp_path / "source"
    _make_skill(source_dir)
    settings = _FakeSettingsService()
    registry = SkillRegistry()
    permission = _FakePermissionGateway()
    lifecycle = SkillLifecycle(
        skills_root=tmp_path / "skills",
        settings_service=settings,
        registry=registry,
        permission_gateway=permission,
    )
    asyncio.run(lifecycle.install_from_local(source_dir))

    asyncio.run(lifecycle.uninstall("demo"))

    assert not (tmp_path / "skills" / "demo").exists()
    assert not settings.store
    assert registry.match_command("/demo run") is None
    assert permission.cleared == ["demo"]


def test_uninstall_missing_skill_raises(tmp_path: Path):
    lifecycle = SkillLifecycle(
        skills_root=tmp_path / "skills",
        settings_service=_FakeSettingsService(),
        registry=SkillRegistry(),
    )

    with pytest.raises(SkillNotFoundError):
        asyncio.run(lifecycle.uninstall("missing"))


def test_uninstall_rejects_path_traversal_without_deleting_parent(tmp_path: Path):
    configs_root = tmp_path / "configs"
    skills_root = configs_root / "skills"
    skills_root.mkdir(parents=True)
    (configs_root / "SKILL.md").write_text(
        "---\n"
        "name: configs\n"
        "description: Parent manifest should never be treated as a skill.\n"
        "---\n",
        encoding="utf-8",
    )
    lifecycle = SkillLifecycle(
        skills_root=skills_root,
        settings_service=_FakeSettingsService(),
        registry=SkillRegistry(),
    )

    with pytest.raises(SkillNotFoundError):
        asyncio.run(lifecycle.uninstall(".."))

    assert configs_root.exists()
    assert (configs_root / "SKILL.md").exists()


def test_list_skills_skips_directory_when_manifest_name_does_not_match(tmp_path: Path):
    skills_root = tmp_path / "skills"
    _make_skill(skills_root / "folder-name", name="brief")
    lifecycle = SkillLifecycle(
        skills_root=skills_root,
        settings_service=_FakeSettingsService(),
        registry=SkillRegistry(),
    )

    records = asyncio.run(lifecycle.list_skills())

    assert records == []


def test_register_installed_config_skills_adds_enabled_provider(tmp_path: Path):
    skills_root = tmp_path / "skills"
    _make_skill(skills_root / "demo")
    settings = _FakeSettingsService()
    settings.store["skills.demo.enabled"] = "true"
    settings.store["skills.demo.content_hash"] = "hash123"
    registry = SkillRegistry()

    asyncio.run(
        register_installed_config_skills(
            skills_root=skills_root,
            settings_service=settings,
            registry=registry,
        )
    )

    matched = registry.match_command("/demo run")
    assert matched is not None
    provider, _command, _message = matched
    assert provider.skill_name == "demo"


def test_register_installed_config_skills_skips_disabled_match(tmp_path: Path):
    skills_root = tmp_path / "skills"
    _make_skill(skills_root / "demo")
    settings = _FakeSettingsService()
    settings.store["skills.demo.enabled"] = "false"
    registry = SkillRegistry()

    asyncio.run(
        register_installed_config_skills(
            skills_root=skills_root,
            settings_service=settings,
            registry=registry,
        )
    )

    assert registry.match_command("/demo run") is None
