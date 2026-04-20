"""LearningStore — persists extracted patterns as warm memory entries."""

from __future__ import annotations

from datetime import date

import structlog

from taim.brain.memory import MemoryManager
from taim.models.feedback import TaskFeedback
from taim.models.memory import MemoryEntry

logger = structlog.get_logger()


class LearningStore:
    """Saves learning patterns to warm memory."""

    def __init__(self, memory: MemoryManager) -> None:
        self._memory = memory

    async def save_learning(
        self,
        feedback: TaskFeedback,
        pattern: str,
        user: str = "default",
    ) -> None:
        """Save an extracted pattern as a warm memory entry."""
        today = date.today()
        entry = MemoryEntry(
            title=f"Learning: {feedback.task_type} — {feedback.agent_name}",
            category="learning",
            tags=[
                "learning",
                feedback.task_type,
                feedback.agent_name,
                f"score:{feedback.score:.1f}",
            ],
            created=today,
            updated=today,
            content=pattern,
            source="learning_loop",
            confidence=feedback.score,
        )
        filename = f"learning-{feedback.task_id[:8]}.md"
        await self._memory.write_entry(entry, filename, user=user)
        logger.info(
            "learning.saved",
            task_type=feedback.task_type,
            agent=feedback.agent_name,
            score=feedback.score,
        )
