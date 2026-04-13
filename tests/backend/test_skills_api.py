"""Tests for /api/skills endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taim.api.skills import router as skills_router
from taim.brain.skill_registry import SkillRegistry
from taim.brain.vault import VaultOps


@pytest_asyncio.fixture
async def client(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    skill_reg = SkillRegistry(ops.vault_config.vault_root / "system" / "skills")
    skill_reg.load()

    app = FastAPI()
    app.include_router(skills_router)
    app.state.skill_registry = skill_reg

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestListSkills:
    async def test_returns_five_built_in(self, client) -> None:
        resp = await client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5
        names = {s["name"] for s in data["skills"]}
        expected = {"web_research", "code_generation", "code_review", "content_writing", "data_analysis"}
        assert names == expected

    async def test_includes_required_tools(self, client) -> None:
        resp = await client.get("/api/skills")
        data = resp.json()
        web = next(s for s in data["skills"] if s["name"] == "web_research")
        assert "web_search" in web["required_tools"]
