"""AgentRunStore — SQLite persistence for agent runs."""

from __future__ import annotations

import json

import aiosqlite

from taim.models.agent import AgentState


class AgentRunStore:
    """SQLite persistence for agent runs (table: agent_runs)."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def upsert(
        self,
        state: AgentState,
        agent_name: str,
        task_id: str,
        team_id: str = "",
        session_id: str | None = None,
    ) -> None:
        """Persist current state. Called after every transition."""
        history_json = json.dumps(
            [t.model_dump(mode="json") for t in state.state_history]
        )
        await self._db.execute(
            """INSERT INTO agent_runs
               (run_id, agent_name, task_id, team_id, session_id,
                state_history, final_state, prompt_tokens, completion_tokens,
                cost_eur, failover_occurred, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, 0, datetime('now'))
               ON CONFLICT(run_id) DO UPDATE SET
                   state_history = excluded.state_history,
                   final_state = excluded.final_state,
                   cost_eur = excluded.cost_eur,
                   completed_at = CASE WHEN excluded.final_state IN ('DONE', 'FAILED')
                                       THEN datetime('now') ELSE completed_at END""",
            (state.run_id, agent_name, task_id, team_id, session_id,
             history_json, state.current_state.value, state.cost_eur),
        )
        await self._db.commit()

    async def load_active_runs(self) -> list[dict]:
        """Return runs where final_state is not terminal — for resume logic in Step 8."""
        async with self._db.execute(
            """SELECT run_id, agent_name, task_id, team_id, session_id, state_history, final_state
               FROM agent_runs
               WHERE final_state NOT IN ('DONE', 'FAILED')"""
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {
                "run_id": r[0],
                "agent_name": r[1],
                "task_id": r[2],
                "team_id": r[3],
                "session_id": r[4],
                "state_history": json.loads(r[5]) if r[5] else [],
                "final_state": r[6],
            }
            for r in rows
        ]
