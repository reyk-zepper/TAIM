"""Tests for HotMemory."""

from taim.brain.hot_memory import HotMemory
from taim.models.memory import ChatMessage, HotMemorySession


class TestAppendAndGet:
    def test_append_creates_session(self) -> None:
        hot = HotMemory()
        hot.append_message("s1", "user", "hello")
        messages = hot.get_messages("s1")
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "hello"

    def test_get_messages_empty_session(self) -> None:
        hot = HotMemory()
        assert hot.get_messages("s1") == []

    def test_last_n(self) -> None:
        hot = HotMemory()
        for i in range(5):
            hot.append_message("s1", "user", f"msg{i}")
        last2 = hot.get_messages("s1", last_n=2)
        assert len(last2) == 2
        assert last2[-1].content == "msg4"


class TestSummarization:
    def test_should_summarize_when_over_limit(self) -> None:
        hot = HotMemory()
        for i in range(HotMemorySession.MAX_MESSAGES + 1):
            hot.append_message("s1", "user", f"msg{i}")
        assert hot.should_summarize("s1") is True

    def test_should_not_summarize_when_under(self) -> None:
        hot = HotMemory()
        for i in range(5):
            hot.append_message("s1", "user", f"msg{i}")
        assert hot.should_summarize("s1") is False

    def test_trim_after_summary_keeps_last_n(self) -> None:
        hot = HotMemory()
        for i in range(25):
            hot.append_message("s1", "user", f"msg{i}")
        removed = hot.trim_after_summary("s1", keep_last_n=10)
        assert len(removed) == 15
        remaining = hot.get_messages("s1")
        assert len(remaining) == 10
        assert remaining[0].content == "msg15"
        assert remaining[-1].content == "msg24"


class TestRebuild:
    def test_rebuild_restores_session(self) -> None:
        hot = HotMemory()
        session = HotMemorySession(
            session_id="s1",
            messages=[ChatMessage(role="user", content="prior")],
        )
        hot.rebuild(session)
        assert hot.get_messages("s1")[0].content == "prior"


class TestClear:
    def test_clear_removes_session(self) -> None:
        hot = HotMemory()
        hot.append_message("s1", "user", "hi")
        hot.clear("s1")
        assert hot.get_messages("s1") == []
