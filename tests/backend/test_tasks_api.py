"""Tests for /api/tasks endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taim.api.tasks import router as tasks_router
from taim.brain.database import init_database
from taim.models.orchestration import TaskPlan, TaskStatus, TeamAgentSlot
from taim.orchestrator.task_manager import TaskManager


@pytest_asyncio.fixture
async def client_and_mgr(tmp_path: Path):
    db = await init_database(tmp_path / "taim.db")
    mgr = TaskManager(db)

    app = FastAPI()
    app.include_router(tasks_router)
    app.state.task_manager = mgr

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, mgr
    await db.close()


@pytest.mark.asyncio
class TestListTasks:
    async def test_empty(self, client_and_mgr) -> None:
        client, _ = client_and_mgr
        resp = await client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"tasks": [], "count": 0}

    async def test_returns_created_tasks(self, client_and_mgr) -> None:
        client, mgr = client_and_mgr
        plan = TaskPlan(task_id="t1", objective="test obj", agents=[TeamAgentSlot(role="primary", agent_name="researcher")])
        await mgr.create(plan)
        await mgr.set_status("t1", TaskStatus.COMPLETED, tokens=100, cost_eur=0.01)

        resp = await client.get("/api/tasks")
        data = resp.json()
        assert data["count"] == 1
        assert data["tasks"][0]["task_id"] == "t1"
        assert data["tasks"][0]["status"] == "completed"
        assert data["tasks"][0]["objective"] == "test obj"
