from __future__ import annotations

from pathlib import Path

import pytest

from newbee_notebook.core.skills.errors import InvalidManifestError
from newbee_notebook.core.skills.manifest_parser import ManifestParser

pytestmark = pytest.mark.unit


def test_parse_reads_only_name_and_description_frontmatter(tmp_path: Path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(
        "---\n"
        "name: demo-skill\n"
        "description: Use notebook context to prepare a compact brief.\n"
        "---\n"
        "\n"
        "# Body should not be part of manifest metadata\n",
        encoding="utf-8",
    )

    meta = ManifestParser().parse_file(skill_file)

    assert meta.name == "demo-skill"
    assert meta.description == "Use notebook context to prepare a compact brief."


def test_parse_rejects_missing_frontmatter(tmp_path: Path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("# Missing frontmatter\n", encoding="utf-8")

    with pytest.raises(InvalidManifestError, match="frontmatter"):
        ManifestParser().parse_file(skill_file)


@pytest.mark.parametrize(
    "name",
    ["Demo", "-demo", "demo_", "claude-helper", "anthropic-tool"],
)
def test_parse_rejects_invalid_or_reserved_names(tmp_path: Path, name: str):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(
        "---\n"
        f"name: {name}\n"
        "description: Valid description.\n"
        "---\n",
        encoding="utf-8",
    )

    with pytest.raises(InvalidManifestError):
        ManifestParser().parse_file(skill_file)


def test_parse_rejects_xml_like_description(tmp_path: Path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(
        "---\n"
        "name: demo\n"
        "description: Use <tag>markup</tag> here.\n"
        "---\n",
        encoding="utf-8",
    )

    with pytest.raises(InvalidManifestError, match="XML"):
        ManifestParser().parse_file(skill_file)


def test_parse_rejects_extra_frontmatter_fields(tmp_path: Path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(
        "---\n"
        "name: demo\n"
        "description: Valid description.\n"
        "version: 1\n"
        "---\n",
        encoding="utf-8",
    )

    with pytest.raises(InvalidManifestError, match="Unsupported"):
        ManifestParser().parse_file(skill_file)
