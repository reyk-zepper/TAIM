"""Tests for /api/stats endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taim.api.stats import router as stats_router
from taim.brain.database import init_database
from taim.models.router import TokenUsage
from taim.router.tracking import TokenTracker


@pytest_asyncio.fixture
async def client(tmp_path: Path):
    db = await init_database(tmp_path / "taim.db")

    app = FastAPI()
    app.include_router(stats_router)
    app.state.db = db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, db
    await db.close()


@pytest.mark.asyncio
class TestMonthlyStats:
    async def test_empty(self, client) -> None:
        c, _ = client
        resp = await c.get("/api/stats/monthly")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost_usd"] == 0.0
        assert data["total_tokens"] == 0
        assert data["by_provider"] == []

    async def test_with_tracking_data(self, client) -> None:
        c, db = client
        tracker = TokenTracker(db)
        await tracker.record(TokenUsage(
            call_id="c1", model="m1", provider="anthropic",
            prompt_tokens=100, completion_tokens=50, cost_usd=0.01,
        ))
        await tracker.record(TokenUsage(
            call_id="c2", model="m2", provider="openai",
            prompt_tokens=200, completion_tokens=100, cost_usd=0.05,
        ))

        resp = await c.get("/api/stats/monthly")
        data = resp.json()
        assert data["total_calls"] == 2
        assert data["total_tokens"] == 450
        assert abs(data["total_cost_usd"] - 0.06) < 0.001
        assert len(data["by_provider"]) == 2
