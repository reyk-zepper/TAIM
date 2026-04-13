"""Tests for memory data models."""

from datetime import date, datetime

from taim.models.memory import (
    ChatMessage,
    HotMemorySession,
    MemoryEntry,
    MemoryIndex,
    MemoryIndexEntry,
)


class TestMemoryEntry:
    def test_minimal(self) -> None:
        today = date.today()
        e = MemoryEntry(
            title="Test",
            category="user-profile",
            created=today,
            updated=today,
            content="body",
        )
        assert e.tags == []
        assert e.confidence == 1.0
        assert e.source == "session"


class TestMemoryIndexEntry:
    def test_minimal(self) -> None:
        e = MemoryIndexEntry(
            filename="prefs.md",
            summary="User prefs",
            tags=["preferences"],
            updated=date.today(),
        )
        assert e.filename == "prefs.md"


class TestMemoryIndex:
    def test_empty(self) -> None:
        idx = MemoryIndex()
        assert idx.entries == []


class TestChatMessage:
    def test_has_timestamp(self) -> None:
        m = ChatMessage(role="user", content="hello")
        assert isinstance(m.timestamp, datetime)


class TestHotMemorySession:
    def test_defaults(self) -> None:
        s = HotMemorySession(session_id="s1")
        assert s.user_id == "default"
        assert s.messages == []
        assert s.task_context == {}

    def test_max_messages_constant(self) -> None:
        assert HotMemorySession.MAX_MESSAGES == 20
