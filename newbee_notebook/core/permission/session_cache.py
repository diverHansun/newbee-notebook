"""In-memory session-scoped permission allow cache."""

from __future__ import annotations

from collections import defaultdict

ALLOW_ALL = "*"


class SessionAllowCache:
    def __init__(self) -> None:
        self._allows: dict[str, set[str]] = defaultdict(set)

    def contains(self, session_id: str, capability_signature: str) -> bool:
        signatures = self._allows.get(str(session_id or ""), set())
        return ALLOW_ALL in signatures or str(capability_signature or "") in signatures

    def add(self, session_id: str, capability_signature: str) -> None:
        normalized_session = str(session_id or "").strip()
        normalized_signature = str(capability_signature or "").strip()
        if not normalized_session or not normalized_signature:
            return
        self._allows[normalized_session].add(normalized_signature)

    def add_all(self, session_id: str) -> None:
        normalized_session = str(session_id or "").strip()
        if not normalized_session:
            return
        self._allows[normalized_session].add(ALLOW_ALL)

    def clear_session(self, session_id: str) -> None:
        self._allows.pop(str(session_id or ""), None)

    def reset_all(self) -> None:
        self._allows.clear()

    def remove_by_skill(self, skill_name: str) -> int:
        marker = f"skill:{str(skill_name or '').strip()}@"
        if marker == "skill:@":
            return 0
        removed = 0
        for session_id in list(self._allows):
            signatures = self._allows[session_id]
            matching = {signature for signature in signatures if signature.startswith(marker)}
            removed += len(matching)
            signatures.difference_update(matching)
            if not signatures:
                self._allows.pop(session_id, None)
        return removed
