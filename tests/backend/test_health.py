"""Tests for the health check endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taim.api.health import router as health_router
from taim.brain.database import init_database
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.models.config import ServerConfig, SystemConfig
from taim.settings import TaimSettings


@pytest_asyncio.fixture
async def configured_app(tmp_vault: Path):
    """Create a FastAPI app with all state configured."""
    app = FastAPI()
    app.include_router(health_router)

    ops = VaultOps(tmp_vault)
    config = ops.load_product_config()
    taim_yaml = ops.load_raw_yaml("taim.yaml")

    app.state.config = SystemConfig(
        server=ServerConfig.from_yaml_and_env(taim_yaml.get("server", {})),
        vault=ops.vault_config,
        product=config,
        settings=TaimSettings(vault_path=tmp_vault),
    )
    app.state.db = await init_database(ops.vault_config.db_path)
    app.state.prompt_loader = PromptLoader(ops.vault_config.prompts_dir)

    yield app

    await app.state.db.close()


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_returns_ok(self, configured_app) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=configured_app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["vault_ok"] is True
        assert data["db_ok"] is True
        assert data["version"] == "0.1.0"

    async def test_lists_providers(self, configured_app) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=configured_app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        data = resp.json()
        assert isinstance(data["providers"], list)
