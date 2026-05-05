from __future__ import annotations

from dataclasses import dataclass

import pytest

from newbee_notebook.core.skills.errors import SkillNameConflictError
from newbee_notebook.core.skills.registry import SkillRegistry

pytestmark = pytest.mark.unit


@dataclass
class _FakeProvider:
    skill_name: str
    slash_commands: list[str]
    enabled: bool = True


def test_match_command_returns_provider_and_cleaned_message():
    registry = SkillRegistry()
    provider = _FakeProvider(skill_name="note", slash_commands=["/note"])
    registry.register(provider)

    matched = registry.match_command("/note do something")

    assert matched is not None
    matched_provider, activated_command, cleaned_message = matched
    assert matched_provider is provider
    assert activated_command == "/note"
    assert cleaned_message == "do something"


def test_match_command_returns_none_for_non_slash_message():
    registry = SkillRegistry()
    registry.register(_FakeProvider(skill_name="note", slash_commands=["/note"]))

    assert registry.match_command("regular message") is None


def test_match_command_is_case_sensitive():
    registry = SkillRegistry()
    registry.register(_FakeProvider(skill_name="note", slash_commands=["/note"]))

    assert registry.match_command("/NOTE do something") is None


def test_match_command_returns_empty_cleaned_message_for_exact_command():
    registry = SkillRegistry()
    provider = _FakeProvider(skill_name="note", slash_commands=["/note"])
    registry.register(provider)

    matched = registry.match_command("/note")

    assert matched == (provider, "/note", "")


def test_match_command_supports_diagram_single_entry():
    registry = SkillRegistry()
    provider = _FakeProvider(skill_name="diagram", slash_commands=["/diagram"])
    registry.register(provider)

    matched = registry.match_command("/diagram build a hierarchy map")

    assert matched is not None
    _, activated_command, cleaned_message = matched
    assert activated_command == "/diagram"
    assert cleaned_message == "build a hierarchy map"


def test_register_rejects_duplicate_slash_command():
    registry = SkillRegistry()
    registry.register(_FakeProvider(skill_name="note", slash_commands=["/note"]))

    with pytest.raises(SkillNameConflictError, match="/note"):
        registry.register(_FakeProvider(skill_name="note2", slash_commands=["/note"]))


def test_match_command_skips_disabled_provider():
    registry = SkillRegistry()
    registry.register(_FakeProvider(skill_name="demo", slash_commands=["/demo"], enabled=False))

    assert registry.match_command("/demo run") is None


def test_unregister_removes_provider_by_skill_name():
    registry = SkillRegistry()
    registry.register(_FakeProvider(skill_name="demo", slash_commands=["/demo"]))

    registry.unregister("demo")

    assert registry.match_command("/demo run") is None
