"""Tests for SessionStore."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.database import init_database
from taim.brain.session_store import SessionStore
from taim.models.memory import ChatMessage, HotMemorySession


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    db = await init_database(tmp_path / "taim.db")
    s = SessionStore(db)
    yield s
    await db.close()


@pytest.mark.asyncio
class TestPersistAndLoad:
    async def test_persist_and_load_roundtrip(self, store: SessionStore) -> None:
        session = HotMemorySession(
            session_id="s1",
            messages=[
                ChatMessage(role="user", content="hello"),
                ChatMessage(role="assistant", content="hi there"),
            ],
        )
        await store.persist(session)
        loaded = await store.load("s1")
        assert loaded is not None
        assert loaded.session_id == "s1"
        assert len(loaded.messages) == 2
        assert loaded.messages[0].content == "hello"

    async def test_load_missing_returns_none(self, store: SessionStore) -> None:
        assert await store.load("nonexistent") is None

    async def test_persist_upsert(self, store: SessionStore) -> None:
        session = HotMemorySession(session_id="s1", messages=[ChatMessage(role="user", content="a")])
        await store.persist(session)
        session.messages.append(ChatMessage(role="user", content="b"))
        await store.persist(session)
        loaded = await store.load("s1")
        assert len(loaded.messages) == 2


@pytest.mark.asyncio
class TestSummary:
    async def test_update_summary(self, store: SessionStore) -> None:
        session = HotMemorySession(session_id="s1")
        await store.persist(session)
        await store.update_summary("s1", "Brief summary.")
        async with store._db.execute(
            "SELECT session_summary, has_summary FROM session_state WHERE session_id = ?",
            ("s1",),
        ) as cur:
            row = await cur.fetchone()
        assert row[0] == "Brief summary."
        assert row[1] == 1


@pytest.mark.asyncio
class TestMaxMessages:
    async def test_persists_only_last_20(self, store: SessionStore) -> None:
        session = HotMemorySession(
            session_id="s1",
            messages=[ChatMessage(role="user", content=f"msg{i}") for i in range(25)],
        )
        await store.persist(session)
        loaded = await store.load("s1")
        assert len(loaded.messages) == 20
        assert loaded.messages[0].content == "msg5"
        assert loaded.messages[-1].content == "msg24"
