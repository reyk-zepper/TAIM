"""Tests for Few-Shot Learning."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from taim.brain.few_shot_store import SCORE_THRESHOLD, FewShotStore
from taim.brain.memory import MemoryManager
from taim.models.feedback import TaskFeedback


@pytest.fixture
def memory(tmp_path: Path) -> MemoryManager:
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    return MemoryManager(users_dir)


def _feedback(
    score: float = 0.9,
    task_type: str = "research",
    task_id: str = "t1abcdef",
) -> TaskFeedback:
    return TaskFeedback(
        task_id=task_id,
        agent_name="researcher",
        score=score,
        source="auto",
        task_type=task_type,
        objective="Find competitors",
    )


@pytest.mark.asyncio
class TestSaveExample:
    async def test_saves_high_score(self, memory: MemoryManager) -> None:
        store = FewShotStore(memory)
        saved = await store.save_example(_feedback(score=0.9), "Detailed research result")
        assert saved is True

        # Verify it was written (task_id[:8] = "t1abcdef")
        entry = await memory.read_entry("example-t1abcdef.md")
        assert entry is not None
        assert "few-shot" in entry.tags
        assert "research" in entry.tags

    async def test_skips_low_score(self, memory: MemoryManager) -> None:
        store = FewShotStore(memory)
        saved = await store.save_example(_feedback(score=0.5), "Mediocre result")
        assert saved is False

    async def test_truncates_long_results(self, memory: MemoryManager) -> None:
        store = FewShotStore(memory)
        long_result = "x" * 5000
        await store.save_example(_feedback(), long_result)
        entry = await memory.read_entry("example-t1abcdef.md")
        assert entry is not None
        assert len(entry.content) < 2000
        assert "[...]" in entry.content

    async def test_threshold_constant(self) -> None:
        assert SCORE_THRESHOLD == 0.8

    async def test_at_threshold_saves(self, memory: MemoryManager) -> None:
        store = FewShotStore(memory)
        saved = await store.save_example(_feedback(score=0.8), "Result at threshold")
        assert saved is True

    async def test_just_below_threshold_skips(self, memory: MemoryManager) -> None:
        store = FewShotStore(memory)
        saved = await store.save_example(_feedback(score=0.79), "Result just below")
        assert saved is False


@pytest.mark.asyncio
class TestFindExamples:
    async def test_finds_matching_examples(self, memory: MemoryManager) -> None:
        store = FewShotStore(memory)
        await store.save_example(
            _feedback(task_id="aaa11111"), "Result A for research"
        )
        await store.save_example(
            _feedback(task_id="bbb22222", task_type="code"), "Result B for code"
        )

        examples = await store.find_examples("research", "researcher")
        # Should find the research example
        assert len(examples) >= 1
        assert any("Result A" in e for e in examples)

    async def test_empty_when_no_examples(self, memory: MemoryManager) -> None:
        store = FewShotStore(memory)
        examples = await store.find_examples("nonexistent", "nobody")
        assert examples == []

    async def test_max_examples_respected(self, memory: MemoryManager) -> None:
        store = FewShotStore(memory)
        for i in range(5):
            tid = f"id{i}00000"
            await store.save_example(
                _feedback(task_id=tid), f"Result {i}"
            )

        examples = await store.find_examples("research", "researcher", max_examples=2)
        assert len(examples) <= 2

    async def test_result_content_in_example(self, memory: MemoryManager) -> None:
        store = FewShotStore(memory)
        await store.save_example(
            _feedback(task_id="xyz99999"), "Specific content marker"
        )
        examples = await store.find_examples("research", "researcher")
        assert len(examples) >= 1
        assert any("Specific content marker" in e for e in examples)

    async def test_only_few_shot_entries_returned(self, memory: MemoryManager) -> None:
        """Entries without 'few-shot' tag should not appear in results."""
        from taim.models.memory import MemoryEntry

        store = FewShotStore(memory)
        # Write a non-few-shot entry that also matches keywords
        non_fs_entry = MemoryEntry(
            title="Research Note",
            category="learning",
            tags=["research", "researcher"],
            created=date.today(),
            updated=date.today(),
            content="Task: Research\n\nResult: Non-few-shot content",
            source="learning",
            confidence=0.9,
        )
        await memory.write_entry(non_fs_entry, "not-few-shot.md")

        examples = await store.find_examples("research", "researcher")
        # The non-few-shot entry should not be included
        assert not any("Non-few-shot content" in e for e in examples)
