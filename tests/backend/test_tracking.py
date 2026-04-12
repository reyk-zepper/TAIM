"""Tests for TokenTracker."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.database import init_database
from taim.models.router import TokenUsage
from taim.router.tracking import TokenTracker


@pytest_asyncio.fixture
async def tracker(tmp_path: Path):
    db = await init_database(tmp_path / "taim.db")
    t = TokenTracker(db)
    yield t
    await db.close()


@pytest.mark.asyncio
class TestRecord:
    async def test_inserts_row(self, tracker: TokenTracker) -> None:
        await tracker.record(TokenUsage(
            call_id="call-1", model="m", provider="p",
            prompt_tokens=100, completion_tokens=50, cost_usd=0.01,
        ))
        async with tracker._db.execute("SELECT COUNT(*) FROM token_tracking") as cur:
            assert (await cur.fetchone())[0] == 1

    async def test_records_all_fields(self, tracker: TokenTracker) -> None:
        await tracker.record(TokenUsage(
            call_id="call-2", agent_run_id="run-1", task_id="task-1", session_id="sess-1",
            model="gpt-4o-mini", provider="openai",
            prompt_tokens=200, completion_tokens=100, cost_usd=0.05,
        ))
        async with tracker._db.execute(
            "SELECT model, provider, prompt_tokens, cost_usd FROM token_tracking WHERE call_id = ?",
            ("call-2",),
        ) as cur:
            assert await cur.fetchone() == ("gpt-4o-mini", "openai", 200, 0.05)


@pytest.mark.asyncio
class TestGetMonthlyCost:
    async def test_returns_zero_for_no_records(self, tracker: TokenTracker) -> None:
        assert await tracker.get_monthly_cost("anthropic") == 0.0

    async def test_sums_costs_for_provider(self, tracker: TokenTracker) -> None:
        for i in range(3):
            await tracker.record(TokenUsage(
                call_id=f"call-{i}", model="m", provider="anthropic",
                prompt_tokens=100, completion_tokens=50, cost_usd=0.10,
            ))
        assert abs(await tracker.get_monthly_cost("anthropic") - 0.30) < 0.001

    async def test_filters_by_provider(self, tracker: TokenTracker) -> None:
        await tracker.record(TokenUsage(call_id="a", model="m", provider="anthropic", prompt_tokens=10, completion_tokens=5, cost_usd=0.10))
        await tracker.record(TokenUsage(call_id="b", model="m", provider="openai", prompt_tokens=10, completion_tokens=5, cost_usd=0.20))
        assert abs(await tracker.get_monthly_cost("anthropic") - 0.10) < 0.001
        assert abs(await tracker.get_monthly_cost("openai") - 0.20) < 0.001
