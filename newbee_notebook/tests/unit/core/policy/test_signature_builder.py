from __future__ import annotations

import pytest

from newbee_notebook.core.policy import SignatureBuilder, SkillPolicyContext

pytestmark = pytest.mark.unit


def test_signature_uses_stable_canonical_json_for_argument_hash():
    builder = SignatureBuilder()

    sig_a = builder.build(
        tool_name="write_file",
        tool_args={"b": 2, "a": {"y": True, "x": [1, 2]}},
    )
    sig_b = builder.build(
        tool_name="write_file",
        tool_args={"a": {"x": [1, 2], "y": True}, "b": 2},
    )

    assert sig_a == sig_b
    assert sig_a.startswith("global:write_file:")
    assert len(sig_a.rsplit(":", 1)[-1]) == 8


def test_signature_scope_includes_active_skill_name_and_content_hash():
    builder = SignatureBuilder()

    sig_a = builder.build(
        tool_name="write_file",
        tool_args={"path": "out.md"},
        skill_context=SkillPolicyContext(name="demo", content_hash="hash-a"),
    )
    sig_b = builder.build(
        tool_name="write_file",
        tool_args={"path": "out.md"},
        skill_context=SkillPolicyContext(name="demo", content_hash="hash-b"),
    )

    assert sig_a.startswith("skill:demo@hash-a:write_file:")
    assert sig_b.startswith("skill:demo@hash-b:write_file:")
    assert sig_a != sig_b
