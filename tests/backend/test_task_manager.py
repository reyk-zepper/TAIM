"""Tests for TaskManager."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.database import init_database
from taim.models.orchestration import TaskPlan, TaskStatus, TeamAgentSlot
from taim.orchestrator.task_manager import TaskManager


@pytest_asyncio.fixture
async def mgr(tmp_path: Path):
    db = await init_database(tmp_path / "taim.db")
    m = TaskManager(db)
    yield m
    await db.close()


@pytest.mark.asyncio
class TestCreate:
    async def test_inserts_row_with_pending(self, mgr: TaskManager) -> None:
        plan = TaskPlan(task_id="t1", objective="test", agents=[TeamAgentSlot(role="primary", agent_name="researcher")])
        await mgr.create(plan)
        async with mgr._db.execute("SELECT status, objective FROM task_state WHERE task_id = ?", ("t1",)) as cur:
            row = await cur.fetchone()
        assert row == ("pending", "test")


@pytest.mark.asyncio
class TestSetStatus:
    async def test_updates_status(self, mgr: TaskManager) -> None:
        plan = TaskPlan(task_id="t1", objective="test", agents=[TeamAgentSlot(role="primary", agent_name="researcher")])
        await mgr.create(plan)
        await mgr.set_status("t1", TaskStatus.RUNNING)
        async with mgr._db.execute("SELECT status FROM task_state WHERE task_id = ?", ("t1",)) as cur:
            row = await cur.fetchone()
        assert row[0] == "running"

    async def test_completed_at_set_for_terminal(self, mgr: TaskManager) -> None:
        plan = TaskPlan(task_id="t1", objective="test", agents=[TeamAgentSlot(role="primary", agent_name="researcher")])
        await mgr.create(plan)
        await mgr.set_status("t1", TaskStatus.COMPLETED, tokens=100, cost_eur=0.05)
        async with mgr._db.execute(
            "SELECT status, token_total, cost_total_eur, completed_at FROM task_state WHERE task_id = ?",
            ("t1",),
        ) as cur:
            row = await cur.fetchone()
        assert row[0] == "completed"
        assert row[1] == 100
        assert abs(row[2] - 0.05) < 0.001
        assert row[3] is not None

    async def test_running_no_completed_at(self, mgr: TaskManager) -> None:
        plan = TaskPlan(task_id="t1", objective="test", agents=[TeamAgentSlot(role="primary", agent_name="researcher")])
        await mgr.create(plan)
        await mgr.set_status("t1", TaskStatus.RUNNING)
        async with mgr._db.execute(
            "SELECT completed_at FROM task_state WHERE task_id = ?",
            ("t1",),
        ) as cur:
            row = await cur.fetchone()
        assert row[0] is None


@pytest.mark.asyncio
class TestUpdateAgentStates:
    async def test_writes_json(self, mgr: TaskManager) -> None:
        plan = TaskPlan(task_id="t1", objective="test", agents=[TeamAgentSlot(role="primary", agent_name="a")])
        await mgr.create(plan)
        await mgr.update_agent_states("t1", {"a": "running", "b": "done"})
        import json
        async with mgr._db.execute("SELECT agent_states FROM task_state WHERE task_id = ?", ("t1",)) as cur:
            row = await cur.fetchone()
        data = json.loads(row[0])
        assert data == {"a": "running", "b": "done"}


@pytest.mark.asyncio
class TestListRecent:
    async def test_empty(self, mgr: TaskManager) -> None:
        assert await mgr.list_recent() == []

    async def test_returns_tasks_newest_first(self, mgr: TaskManager) -> None:
        import asyncio
        for i in range(3):
            plan = TaskPlan(task_id=f"t{i}", objective=f"obj{i}", agents=[TeamAgentSlot(role="primary", agent_name="a")])
            await mgr.create(plan)
            await asyncio.sleep(0.01)  # ensure different created_at
        tasks = await mgr.list_recent(limit=10)
        assert len(tasks) == 3
        # Newest first
        task_ids = [t["task_id"] for t in tasks]
        assert task_ids[0] == "t2"

    async def test_limit_respected(self, mgr: TaskManager) -> None:
        for i in range(5):
            plan = TaskPlan(task_id=f"t{i}", objective=f"obj{i}", agents=[TeamAgentSlot(role="primary", agent_name="a")])
            await mgr.create(plan)
        tasks = await mgr.list_recent(limit=2)
        assert len(tasks) == 2
