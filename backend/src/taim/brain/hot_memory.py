"""HotMemory — in-memory per-session state."""

from __future__ import annotations

from taim.models.memory import ChatMessage, HotMemorySession


class HotMemory:
    """In-memory per-session state. Survives within one server process."""

    def __init__(self) -> None:
        self._sessions: dict[str, HotMemorySession] = {}

    def get_or_create(
        self, session_id: str, user_id: str = "default"
    ) -> HotMemorySession:
        if session_id not in self._sessions:
            self._sessions[session_id] = HotMemorySession(
                session_id=session_id, user_id=user_id
            )
        return self._sessions[session_id]

    def append_message(self, session_id: str, role: str, content: str) -> None:
        session = self.get_or_create(session_id)
        session.messages.append(ChatMessage(role=role, content=content))

    def get_messages(
        self, session_id: str, last_n: int | None = None
    ) -> list[ChatMessage]:
        session = self._sessions.get(session_id)
        if not session:
            return []
        msgs = session.messages
        if last_n:
            return msgs[-last_n:]
        return msgs

    def should_summarize(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        return len(session.messages) > HotMemorySession.MAX_MESSAGES

    def trim_after_summary(
        self, session_id: str, keep_last_n: int = 10
    ) -> list[ChatMessage]:
        """Remove oldest messages except the last N. Returns the removed messages."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        removed = session.messages[:-keep_last_n]
        session.messages = session.messages[-keep_last_n:]
        return removed

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def rebuild(self, session: HotMemorySession) -> None:
        """Restore a session from persistence."""
        self._sessions[session.session_id] = session
