"""Parser for Anthropic-compatible SKILL.md frontmatter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from newbee_notebook.core.skills.errors import InvalidManifestError

_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_XML_PATTERN = re.compile(r"<[A-Za-z][^>]*>")
_SUPPORTED_FIELDS = {"name", "description"}
_RESERVED_NAME_PARTS = ("anthropic", "claude")


@dataclass(frozen=True)
class SkillManifestMeta:
    name: str
    description: str


class ManifestParser:
    def parse_file(self, path: str | Path) -> SkillManifestMeta:
        skill_path = Path(path)
        return self.parse(skill_path.read_text(encoding="utf-8"))

    def parse(self, content: str) -> SkillManifestMeta:
        frontmatter = self._extract_frontmatter(content)
        try:
            payload = yaml.safe_load(frontmatter) or {}
        except yaml.YAMLError as exc:
            raise InvalidManifestError(f"invalid YAML frontmatter: {exc}") from exc
        if not isinstance(payload, dict):
            raise InvalidManifestError("frontmatter must be a mapping")

        unsupported = sorted(set(str(key) for key in payload) - _SUPPORTED_FIELDS)
        if unsupported:
            raise InvalidManifestError(
                f"Unsupported frontmatter fields: {', '.join(unsupported)}"
            )

        name = str(payload.get("name") or "").strip()
        description = str(payload.get("description") or "").strip()
        self._validate_name(name)
        self._validate_description(description)
        return SkillManifestMeta(name=name, description=description)

    @staticmethod
    def _extract_frontmatter(content: str) -> str:
        normalized = str(content or "")
        if not normalized.startswith("---\n"):
            raise InvalidManifestError("SKILL.md must start with YAML frontmatter")
        end_index = normalized.find("\n---", 4)
        if end_index < 0:
            raise InvalidManifestError("SKILL.md frontmatter must be closed")
        return normalized[4:end_index]

    @staticmethod
    def _validate_name(name: str) -> None:
        if not name:
            raise InvalidManifestError("name is required")
        if not _NAME_PATTERN.fullmatch(name):
            raise InvalidManifestError(
                "name must use lowercase letters, numbers, and hyphens"
            )
        if any(part in name for part in _RESERVED_NAME_PARTS):
            raise InvalidManifestError("name contains a reserved word")
        if _XML_PATTERN.search(name):
            raise InvalidManifestError("name must not contain XML tags")

    @staticmethod
    def _validate_description(description: str) -> None:
        if not description:
            raise InvalidManifestError("description is required")
        if len(description) > 1024:
            raise InvalidManifestError("description must be 1024 characters or fewer")
        if _XML_PATTERN.search(description):
            raise InvalidManifestError("description must not contain XML tags")
