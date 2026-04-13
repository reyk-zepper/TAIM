"""Tests for MemoryManager."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from taim.brain.memory import MemoryManager
from taim.models.memory import MemoryEntry


@pytest.fixture
def manager(tmp_path: Path) -> MemoryManager:
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    return MemoryManager(users_dir)


def _make_entry(
    title: str = "T",
    tags: list[str] | None = None,
    content: str = "body",
) -> MemoryEntry:
    today = date.today()
    return MemoryEntry(
        title=title, category="preferences",
        tags=tags or ["preferences"],
        created=today, updated=today,
        content=content,
    )


@pytest.mark.asyncio
class TestWriteAndRead:
    async def test_write_creates_file(self, manager: MemoryManager) -> None:
        entry = _make_entry("User Preferences", ["preferences", "user-profile"])
        path = await manager.write_entry(entry, "preferences.md")
        assert path.exists()
        text = path.read_text()
        assert "title: User Preferences" in text
        assert "body" in text

    async def test_read_roundtrip(self, manager: MemoryManager) -> None:
        entry = _make_entry("Test", ["preferences"], "User prefers concise outputs")
        await manager.write_entry(entry, "test.md")
        loaded = await manager.read_entry("test.md")
        assert loaded is not None
        assert loaded.title == "Test"
        assert "preferences" in loaded.tags
        assert "concise outputs" in loaded.content

    async def test_read_missing_returns_none(self, manager: MemoryManager) -> None:
        result = await manager.read_entry("nonexistent.md")
        assert result is None


@pytest.mark.asyncio
class TestIndex:
    async def test_write_updates_index(self, manager: MemoryManager) -> None:
        await manager.write_entry(_make_entry("First", ["preferences"], "first body"), "a.md")
        await manager.write_entry(_make_entry("Second", ["research"], "second body"), "b.md")
        index = await manager.scan_index()
        assert len(index.entries) == 2
        filenames = {e.filename for e in index.entries}
        assert "a.md" in filenames
        assert "b.md" in filenames

    async def test_scan_empty_index(self, manager: MemoryManager) -> None:
        index = await manager.scan_index()
        assert index.entries == []


@pytest.mark.asyncio
class TestFindRelevant:
    async def test_matches_by_tag(self, manager: MemoryManager) -> None:
        await manager.write_entry(_make_entry("A", ["preferences"], "a"), "a.md")
        await manager.write_entry(_make_entry("B", ["research"], "b"), "b.md")
        results = await manager.find_relevant(["preferences"])
        assert len(results) == 1
        assert results[0].filename == "a.md"

    async def test_matches_by_summary_keyword(self, manager: MemoryManager) -> None:
        await manager.write_entry(_make_entry("X", ["misc"], "User prefers TypeScript"), "ts.md")
        results = await manager.find_relevant(["typescript"])
        assert any(r.filename == "ts.md" for r in results)

    async def test_no_match_returns_empty(self, manager: MemoryManager) -> None:
        await manager.write_entry(_make_entry("A", ["preferences"], "a"), "a.md")
        results = await manager.find_relevant(["completely_unrelated_xyz"])
        assert results == []


@pytest.mark.asyncio
class TestMemoryReaderProtocol:
    async def test_get_preferences_text_missing(self, manager: MemoryManager) -> None:
        assert await manager.get_preferences_text() == ""

    async def test_get_preferences_text_returns_content(self, manager: MemoryManager) -> None:
        await manager.write_entry(
            _make_entry("Prefs", ["preferences"], "The user prefers concise outputs."),
            "preferences.md",
        )
        text = await manager.get_preferences_text()
        assert "concise outputs" in text
