"""LearningLoop — orchestrates feedback → pattern extraction → storage."""

from __future__ import annotations

import structlog

from taim.brain.feedback import FeedbackCollector
from taim.brain.few_shot_store import FewShotStore
from taim.brain.learning_store import LearningStore
from taim.brain.pattern_extractor import PatternExtractor
from taim.models.agent import AgentRun
from taim.models.chat import IntentResult

logger = structlog.get_logger()


class LearningLoop:
    """Processes completed tasks to extract and store learnings."""

    def __init__(
        self,
        collector: FeedbackCollector,
        extractor: PatternExtractor,
        store: LearningStore,
        few_shot_store: FewShotStore | None = None,
    ) -> None:
        self._collector = collector
        self._extractor = extractor
        self._store = store
        self._few_shot = few_shot_store

    async def process_completed_task(
        self,
        run: AgentRun,
        intent: IntentResult,
        result_content: str,
    ) -> None:
        """Score, extract pattern, store learning. Fire-and-forget safe."""
        try:
            feedback = self._collector.score_from_run(run, intent)

            pattern = await self._extractor.extract(feedback, result_content)
            if pattern:
                await self._store.save_learning(feedback, pattern)
            else:
                logger.debug(
                    "learning.skipped",
                    task_id=run.task_id,
                    score=feedback.score,
                    reason="below_threshold" if feedback.score < 0.7 else "extraction_failed",
                )

            # Also save as few-shot example (higher threshold)
            if self._few_shot:
                await self._few_shot.save_example(feedback, result_content)
        except Exception:
            logger.exception("learning_loop.error", task_id=run.task_id)
