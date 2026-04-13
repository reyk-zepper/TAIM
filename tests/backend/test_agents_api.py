"""Tests for /api/agents endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taim.api.agents import router as agents_router
from taim.brain.agent_registry import AgentRegistry
from taim.brain.vault import VaultOps


@pytest_asyncio.fixture
async def client(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    registry = AgentRegistry(ops.vault_config.agents_dir)
    registry.load()

    app = FastAPI()
    app.include_router(agents_router)
    app.state.agent_registry = registry

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
class TestListAgents:
    async def test_returns_all_agents(self, client) -> None:
        resp = await client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5
        names = {a["name"] for a in data["agents"]}
        assert names == {"researcher", "coder", "reviewer", "writer", "analyst"}


@pytest.mark.asyncio
class TestGetAgent:
    async def test_returns_specific_agent(self, client) -> None:
        resp = await client.get("/api/agents/researcher")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "researcher"
        assert "web_research" in data["skills"]

    async def test_404_for_unknown(self, client) -> None:
        resp = await client.get("/api/agents/nonexistent")
        assert resp.status_code == 404
