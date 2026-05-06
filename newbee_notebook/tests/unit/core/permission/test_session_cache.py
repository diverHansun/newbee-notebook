from __future__ import annotations

from newbee_notebook.core.permission import SessionAllowCache


def test_session_allow_cache_is_scoped_by_session_id():
    cache = SessionAllowCache()

    cache.add("session-a", "global:write_file:abc12345")

    assert cache.contains("session-a", "global:write_file:abc12345")
    assert not cache.contains("session-b", "global:write_file:abc12345")


def test_session_allow_cache_removes_skill_scoped_signatures_by_skill_name():
    cache = SessionAllowCache()
    cache.add("session-a", "skill:demo@hash1:write_file:abc12345")
    cache.add("session-a", "skill:other@hash1:write_file:def67890")
    cache.add("session-b", "skill:demo@hash2:bash:feedbeef")
    cache.add("session-b", "global:write_file:99999999")

    removed = cache.remove_by_skill("demo")

    assert removed == 2
    assert not cache.contains("session-a", "skill:demo@hash1:write_file:abc12345")
    assert cache.contains("session-a", "skill:other@hash1:write_file:def67890")
    assert not cache.contains("session-b", "skill:demo@hash2:bash:feedbeef")
    assert cache.contains("session-b", "global:write_file:99999999")


def test_session_allow_cache_clear_and_reset_are_fail_closed_cleanup_hooks():
    cache = SessionAllowCache()
    cache.add("session-a", "global:write_file:abc12345")
    cache.add("session-b", "global:write_file:def67890")

    cache.clear_session("session-a")

    assert not cache.contains("session-a", "global:write_file:abc12345")
    assert cache.contains("session-b", "global:write_file:def67890")

    cache.reset_all()

    assert not cache.contains("session-b", "global:write_file:def67890")
