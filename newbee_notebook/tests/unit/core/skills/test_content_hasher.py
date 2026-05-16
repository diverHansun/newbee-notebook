from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.skills.content_hasher import ContentHasher

pytestmark = pytest.mark.unit


def test_calculate_returns_stable_hash_for_same_tree(tmp_path: Path):
    skill_dir = tmp_path / "demo"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")
    (skill_dir / "references" / "guide.md").write_text("hello", encoding="utf-8")

    hasher = ContentHasher()

    assert hasher.calculate(skill_dir) == hasher.calculate(skill_dir)


def test_calculate_changes_when_file_content_changes(tmp_path: Path):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("one", encoding="utf-8")
    hasher = ContentHasher()
    before = hasher.calculate(skill_dir)

    skill_file.write_text("two", encoding="utf-8")

    assert hasher.calculate(skill_dir) != before


def test_calculate_ignores_file_mtime_changes(tmp_path: Path):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("same", encoding="utf-8")
    hasher = ContentHasher()
    before = hasher.calculate(skill_dir)
    skill_file.touch()

    assert hasher.calculate(skill_dir) == before
