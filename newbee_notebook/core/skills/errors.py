"""Errors for runtime and configurable skills."""

from __future__ import annotations


class SkillError(Exception):
    """Base class for skill module errors."""


class InvalidManifestError(SkillError):
    """Raised when SKILL.md frontmatter violates the supported contract."""


class SkillNameConflictError(SkillError):
    """Raised when a skill name or slash command is already registered."""


class SkillNotFoundError(SkillError):
    """Raised when a requested skill cannot be found."""
