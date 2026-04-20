"""Tests for the Learning Loop pipeline."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from taim.brain.feedback import FeedbackCollector
from taim.brain.learning_loop import LearningLoop
from taim.brain.learning_store import LearningStore
from taim.brain.memory import MemoryManager
from taim.brain.pattern_extractor import PatternExtractor
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.models.agent import AgentRun, AgentStateEnum, StateTransition
from taim.models.chat import IntentResult, TaskConstraints
from taim.models.feedback import TaskFeedback

from conftest import MockRouter, make_response


def _make_run(
    final_state: AgentStateEnum = AgentStateEnum.DONE,
    iterations: int = 0,
    result: str = "Good research result with detailed findings.",
) -> AgentRun:
    history = [
        StateTransition(from_state=None, to_state=AgentStateEnum.PLANNING, timestamp=datetime.now(timezone.utc)),
        StateTransition(from_state=AgentStateEnum.PLANNING, to_state=AgentStateEnum.EXECUTING, timestamp=datetime.now(timezone.utc), reason="planning_complete"),
    ]
    for i in range(iterations):
        history.append(
            StateTransition(from_state=AgentStateEnum.REVIEWING, to_state=AgentStateEnum.ITERATING, timestamp=datetime.now(timezone.utc), reason=f"iteration_{i+1}")
        )
    history.append(
        StateTransition(from_state=AgentStateEnum.REVIEWING, to_state=final_state, timestamp=datetime.now(timezone.utc), reason="review_passed")
    )
    return AgentRun(
        run_id="run-1",
        agent_name="researcher",
        task_id="task-1",
        final_state=final_state,
        state_history=history,
        result_content=result,
    )


def _make_intent(task_type: str = "research", objective: str = "Find competitors") -> IntentResult:
    return IntentResult(
        task_type=task_type,
        objective=objective,
        constraints=TaskConstraints(),
    )


class TestFeedbackCollector:
    def test_successful_first_pass_high_score(self) -> None:
        collector = FeedbackCollector()
        run = _make_run(final_state=AgentStateEnum.DONE, iterations=0)
        feedback = collector.score_from_run(run, _make_intent())
        assert feedback.score >= 0.8
        assert feedback.signals["completed"] is True
        assert feedback.signals.get("first_pass") is True

    def test_failed_run_low_score(self) -> None:
        collector = FeedbackCollector()
        run = _make_run(final_state=AgentStateEnum.FAILED, result="")
        feedback = collector.score_from_run(run, _make_intent())
        assert feedback.score < 0.5

    def test_multiple_iterations_moderate_score(self) -> None:
        collector = FeedbackCollector()
        run = _make_run(iterations=3)
        feedback = collector.score_from_run(run, _make_intent())
        assert 0.5 <= feedback.score <= 0.9

    def test_user_positive_feedback(self) -> None:
        collector = FeedbackCollector()
        feedback = collector.score_from_user("task-1", "researcher", positive=True)
        assert feedback.score == 0.9
        assert feedback.source == "user_explicit"

    def test_user_negative_feedback(self) -> None:
        collector = FeedbackCollector()
        feedback = collector.score_from_user("task-1", "researcher", positive=False)
        assert feedback.score == 0.2


class TestPatternExtractor:
    @pytest.mark.asyncio
    async def test_extracts_for_high_score(self, tmp_vault: Path) -> None:
        ops = VaultOps(tmp_vault)
        ops.ensure_vault()
        loader = PromptLoader(ops.vault_config.prompts_dir)
        router = MockRouter([make_response("Pattern: used structured comparison approach")])
        extractor = PatternExtractor(router, loader)

        feedback = TaskFeedback(
            task_id="t1", agent_name="researcher", score=0.9,
            source="auto", task_type="research", objective="Compare X",
        )
        result = await extractor.extract(feedback, "detailed result...")
        assert result is not None
        assert "Pattern" in result or "comparison" in result

    @pytest.mark.asyncio
    async def test_returns_none_for_low_score(self, tmp_vault: Path) -> None:
        ops = VaultOps(tmp_vault)
        ops.ensure_vault()
        loader = PromptLoader(ops.vault_config.prompts_dir)
        router = MockRouter([])
        extractor = PatternExtractor(router, loader)

        feedback = TaskFeedback(
            task_id="t1", agent_name="researcher", score=0.3,
            source="auto", task_type="research", objective="X",
        )
        result = await extractor.extract(feedback, "bad result")
        assert result is None


class TestLearningStore:
    @pytest.mark.asyncio
    async def test_saves_learning(self, tmp_path: Path) -> None:
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        memory = MemoryManager(users_dir)
        store = LearningStore(memory)

        feedback = TaskFeedback(
            task_id="task-abc123", agent_name="researcher", score=0.9,
            source="auto", task_type="research", objective="X",
        )
        await store.save_learning(feedback, "Used structured comparison approach")

        # Verify entry exists
        entry = await memory.read_entry("learning-task-abc.md")
        assert entry is not None
        assert "learning" in entry.tags
        assert "research" in entry.tags
        assert "structured comparison" in entry.content


class TestLearningLoop:
    @pytest.mark.asyncio
    async def test_full_pipeline(self, tmp_vault: Path) -> None:
        ops = VaultOps(tmp_vault)
        ops.ensure_vault()
        loader = PromptLoader(ops.vault_config.prompts_dir)
        memory = MemoryManager(ops.vault_config.users_dir)

        router = MockRouter([make_response("Pattern: used systematic approach")])
        collector = FeedbackCollector()
        extractor = PatternExtractor(router, loader)
        store = LearningStore(memory)
        loop = LearningLoop(collector, extractor, store)

        run = _make_run()
        intent = _make_intent()
        await loop.process_completed_task(run, intent, "Great detailed result")

        # Verify a learning was stored
        index = await memory.scan_index()
        learning_entries = [e for e in index.entries if "learning" in e.tags]
        assert len(learning_entries) >= 1

    @pytest.mark.asyncio
    async def test_low_score_no_learning(self, tmp_vault: Path) -> None:
        ops = VaultOps(tmp_vault)
        ops.ensure_vault()
        loader = PromptLoader(ops.vault_config.prompts_dir)
        memory = MemoryManager(ops.vault_config.users_dir)

        router = MockRouter([])  # Should never be called
        collector = FeedbackCollector()
        extractor = PatternExtractor(router, loader)
        store = LearningStore(memory)
        loop = LearningLoop(collector, extractor, store)

        run = _make_run(final_state=AgentStateEnum.FAILED, result="")
        intent = _make_intent()
        await loop.process_completed_task(run, intent, "")

        index = await memory.scan_index()
        learning_entries = [e for e in index.entries if "learning" in e.tags]
        assert len(learning_entries) == 0
