"""TokenTracker — per-call token logging to SQLite."""

from __future__ import annotations

import aiosqlite

from taim.models.router import TokenUsage


class TokenTracker:
    """Logs every LLM call to the token_tracking table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def record(self, usage: TokenUsage) -> None:
        """Insert a token tracking row."""
        await self._db.execute(
            """INSERT INTO token_tracking
               (call_id, agent_run_id, task_id, session_id, model, provider,
                prompt_tokens, completion_tokens, cost_usd)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (usage.call_id, usage.agent_run_id, usage.task_id, usage.session_id,
             usage.model, usage.provider, usage.prompt_tokens,
             usage.completion_tokens, usage.cost_usd),
        )
        await self._db.commit()

    async def get_monthly_cost(self, provider: str) -> float:
        """Sum cost_usd for current calendar month for a provider."""
        async with self._db.execute(
            """SELECT COALESCE(SUM(cost_usd), 0.0) FROM token_tracking
               WHERE provider = ? AND created_at >= date('now', 'start of month')""",
            (provider,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0.0
