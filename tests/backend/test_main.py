"""Integration tests for the TAIM application."""

from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taim.main import create_app


@pytest_asyncio.fixture
async def app_with_vault(
    tmp_vault: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[FastAPI, None]:
    """Create a TAIM app pointing at a temporary vault, with lifespan running."""
    monkeypatch.setenv("TAIM_VAULT_PATH", str(tmp_vault))
    app = create_app()
    async with app.router.lifespan_context(app):
        yield app


@pytest.mark.asyncio
class TestAppStartup:
    async def test_health_via_lifespan(self, app_with_vault: FastAPI) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_with_vault), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["vault_ok"] is True
        assert data["db_ok"] is True

    async def test_openapi_docs_available(self, app_with_vault: FastAPI) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_with_vault), base_url="http://test"
        ) as client:
            resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        assert resp.json()["info"]["title"] == "TAIM"


@pytest.mark.asyncio
class TestCORS:
    async def test_cors_headers_for_allowed_origin(self, app_with_vault: FastAPI) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_with_vault), base_url="http://test"
        ) as client:
            resp = await client.options(
                "/health",
                headers={
                    "origin": "http://localhost:5173",
                    "access-control-request-method": "GET",
                },
            )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"

    async def test_cors_env_override(
        self, tmp_vault: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TAIM_VAULT_PATH", str(tmp_vault))
        monkeypatch.setenv("TAIM_CORS_ORIGINS", "http://custom.com")
        app = create_app()
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.options(
                    "/health",
                    headers={
                        "origin": "http://custom.com",
                        "access-control-request-method": "GET",
                    },
                )
        assert resp.headers.get("access-control-allow-origin") == "http://custom.com"
