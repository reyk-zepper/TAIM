"""Summarizer — compresses aging hot memory into warm memory entries."""

from __future__ import annotations

from datetime import date

import structlog

from taim.brain.memory import MemoryManager
from taim.brain.prompts import PromptLoader
from taim.models.memory import ChatMessage, MemoryEntry
from taim.models.router import ModelTierEnum

logger = structlog.get_logger()


class Summarizer:
    """Summarizes aging hot memory into warm memory entries."""

    def __init__(
        self,
        router,
        prompt_loader: PromptLoader,
        memory_manager: MemoryManager,
    ) -> None:
        self._router = router
        self._prompts = prompt_loader
        self._memory = memory_manager

    async def summarize_and_store(
        self,
        session_id: str,
        messages: list[ChatMessage],
        user: str = "default",
    ) -> str:
        """Generate a summary of messages, store as warm memory, return summary text."""
        transcript = "\n".join(f"{m.role}: {m.content}" for m in messages)
        prompt = self._prompts.load(
            "session-summarizer",
            {"transcript": transcript},
        )

        response = await self._router.complete(
            messages=[{"role": "system", "content": prompt}],
            tier=ModelTierEnum.TIER3_ECONOMY,
            session_id=session_id,
        )
        summary = response.content.strip()

        today = date.today()
        entry = MemoryEntry(
            title=f"Session Summary {today.isoformat()}",
            category="session-summary",
            tags=["session", "summary", session_id],
            created=today,
            updated=today,
            content=summary,
            source="session",
        )
        filename = f"session-{session_id}-summary.md"
        await self._memory.write_entry(entry, filename, user=user)

        logger.info(
            "memory.summarized",
            session_id=session_id,
            message_count=len(messages),
            summary_len=len(summary),
        )
        return summary
