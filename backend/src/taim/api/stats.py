"""Stats REST endpoints."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends

from taim.api.deps import get_db

router = APIRouter(prefix="/api/stats")


@router.get("/monthly")
async def monthly_stats(db: aiosqlite.Connection = Depends(get_db)) -> dict:
    """Monthly usage summary from token_tracking table."""
    async with db.execute(
        """SELECT
            provider,
            COUNT(*) as call_count,
            SUM(prompt_tokens) as total_prompt,
            SUM(completion_tokens) as total_completion,
            SUM(cost_usd) as total_cost_usd
           FROM token_tracking
           WHERE created_at >= date('now', 'start of month')
           GROUP BY provider"""
    ) as cursor:
        rows = await cursor.fetchall()

    providers = []
    total_cost = 0.0
    total_tokens = 0
    total_calls = 0
    for row in rows:
        provider_name, calls, prompt, completion, cost = row
        providers.append({
            "provider": provider_name,
            "calls": calls,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "cost_usd": round(cost, 4),
        })
        total_cost += cost
        total_tokens += prompt + completion
        total_calls += calls

    async with db.execute(
        "SELECT COUNT(*) FROM task_state WHERE created_at >= date('now', 'start of month')"
    ) as cursor:
        task_count = (await cursor.fetchone())[0]

    return {
        "period": "current_month",
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "total_calls": total_calls,
        "task_count": task_count,
        "avg_cost_per_task": round(total_cost / task_count, 4) if task_count else 0.0,
        "by_provider": providers,
    }
