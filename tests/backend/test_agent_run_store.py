"""Tests for AgentRunStore."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.agent_run_store import AgentRunStore
from taim.brain.database import init_database
from taim.models.agent import AgentState, AgentStateEnum, StateTransition


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    db = await init_database(tmp_path / "taim.db")
    s = AgentRunStore(db)
    yield s
    await db.close()


def _make_state(
    run_id: str = "r1",
    state: AgentStateEnum = AgentStateEnum.EXECUTING,
) -> AgentState:
    return AgentState(
        agent_name="researcher",
        run_id=run_id,
        current_state=state,
        iteration=1,
        cost_eur=0.05,
        state_history=[
            StateTransition(
                from_state=None,
                to_state=AgentStateEnum.PLANNING,
                timestamp=datetime.now(timezone.utc),
            ),
        ],
    )


@pytest.mark.asyncio
class TestUpsert:
    async def test_inserts(self, store: AgentRunStore) -> None:
        state = _make_state()
        await store.upsert(state, agent_name="researcher", task_id="task-1")
        async with store._db.execute("SELECT COUNT(*) FROM agent_runs") as cur:
            assert (await cur.fetchone())[0] == 1

    async def test_updates_on_conflict(self, store: AgentRunStore) -> None:
        state = _make_state()
        await store.upsert(state, agent_name="researcher", task_id="task-1")
        state.current_state = AgentStateEnum.DONE
        await store.upsert(state, agent_name="researcher", task_id="task-1")
        async with store._db.execute(
            "SELECT final_state FROM agent_runs WHERE run_id = ?", ("r1",)
        ) as cur:
            row = await cur.fetchone()
        assert row[0] == "DONE"

    async def test_sets_completed_at_on_terminal(self, store: AgentRunStore) -> None:
        state = _make_state()
        await store.upsert(state, agent_name="researcher", task_id="task-1")
        state.current_state = AgentStateEnum.DONE
        await store.upsert(state, agent_name="researcher", task_id="task-1")
        async with store._db.execute(
            "SELECT completed_at FROM agent_runs WHERE run_id = ?", ("r1",)
        ) as cur:
            row = await cur.fetchone()
        assert row[0] is not None


@pytest.mark.asyncio
class TestLoadActiveRuns:
    async def test_returns_non_terminal_only(self, store: AgentRunStore) -> None:
        await store.upsert(_make_state("r-run", AgentStateEnum.EXECUTING), "a", "t1")
        await store.upsert(_make_state("r-done", AgentStateEnum.DONE), "a", "t1")
        await store.upsert(_make_state("r-fail", AgentStateEnum.FAILED), "a", "t1")

        active = await store.load_active_runs()
        run_ids = {r["run_id"] for r in active}
        assert "r-run" in run_ids
        assert "r-done" not in run_ids
        assert "r-fail" not in run_ids

    async def test_includes_state_history(self, store: AgentRunStore) -> None:
        state = _make_state("r-active", AgentStateEnum.EXECUTING)
        await store.upsert(state, "researcher", "t1")
        active = await store.load_active_runs()
        assert len(active) == 1
        assert active[0]["state_history"][0]["to_state"] == "PLANNING"
