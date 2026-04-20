"""PatternExtractor — extracts reusable patterns from successful runs."""

from __future__ import annotations

import structlog

from taim.brain.prompts import PromptLoader
from taim.models.feedback import TaskFeedback
from taim.models.router import ModelTierEnum

logger = structlog.get_logger()

SCORE_THRESHOLD = 0.7


class PatternExtractor:
    """Extracts patterns from high-scoring agent runs via Tier 3 LLM."""

    def __init__(self, router, prompt_loader: PromptLoader) -> None:
        self._router = router
        self._prompts = prompt_loader

    async def extract(
        self,
        feedback: TaskFeedback,
        result_content: str,
    ) -> str | None:
        """Extract a pattern from a successful task. Returns None if score too low."""
        if feedback.score < SCORE_THRESHOLD:
            return None

        try:
            prompt = self._prompts.load(
                "pattern-extractor",
                {
                    "task_type": feedback.task_type,
                    "objective": feedback.objective,
                    "agent_name": feedback.agent_name,
                    "result_snippet": result_content[:2000],
                },
            )
        except Exception:
            logger.warning("pattern_extractor.prompt_missing")
            return None

        try:
            response = await self._router.complete(
                messages=[{"role": "system", "content": prompt}],
                tier=ModelTierEnum.TIER3_ECONOMY,
            )
            return response.content.strip()
        except Exception:
            logger.exception("pattern_extractor.llm_error")
            return None
