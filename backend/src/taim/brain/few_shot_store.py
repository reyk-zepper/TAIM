"""FewShotStore — stores and retrieves task→result pairs for few-shot learning."""

from __future__ import annotations

from datetime import date

import structlog
from pydantic import BaseModel

from taim.brain.memory import MemoryManager
from taim.models.feedback import TaskFeedback
from taim.models.memory import MemoryEntry

logger = structlog.get_logger()

SCORE_THRESHOLD = 0.8  # Higher than pattern extraction — only the best examples


class FewShotExample(BaseModel):
    """A task→result pair used as a prompt example."""

    task_type: str
    objective: str
    agent_name: str
    result_snippet: str
    score: float


class FewShotStore:
    """Stores high-quality task→result pairs for few-shot learning."""

    def __init__(self, memory: MemoryManager) -> None:
        self._memory = memory

    async def save_example(
        self,
        feedback: TaskFeedback,
        result_content: str,
        user: str = "default",
    ) -> bool:
        """Save a task→result pair if score is high enough. Returns True if saved."""
        if feedback.score < SCORE_THRESHOLD:
            return False

        snippet = result_content[:1500]
        if len(result_content) > 1500:
            snippet += "\n[...]"

        today = date.today()
        entry = MemoryEntry(
            title=f"Example: {feedback.task_type} — {feedback.agent_name}",
            category="few-shot",
            tags=["few-shot", "example", feedback.task_type, feedback.agent_name],
            created=today,
            updated=today,
            content=f"Task: {feedback.objective}\n\nResult:\n{snippet}",
            source="few_shot",
            confidence=feedback.score,
        )
        filename = f"example-{feedback.task_id[:8]}.md"
        await self._memory.write_entry(entry, filename, user=user)
        logger.info(
            "few_shot.saved",
            task_type=feedback.task_type,
            agent=feedback.agent_name,
            score=feedback.score,
        )
        return True

    async def find_examples(
        self,
        task_type: str,
        agent_name: str,
        user: str = "default",
        max_examples: int = 3,
    ) -> list[str]:
        """Find relevant few-shot examples for a task+agent combo."""
        keywords = ["few-shot", "example", task_type, agent_name]
        relevant = await self._memory.find_relevant(
            keywords,
            user=user,
            max_entries=max_examples,
        )

        examples = []
        for ref in relevant:
            entry = await self._memory.read_entry(ref.filename, user=user)
            if entry and "few-shot" in entry.tags:
                examples.append(entry.content)

        return examples
