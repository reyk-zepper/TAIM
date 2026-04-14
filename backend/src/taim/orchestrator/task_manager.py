"""TaskManager — task_state SQLite lifecycle."""

from __future__ import annotations

import json

import aiosqlite

from taim.models.orchestration import TaskPlan, TaskStatus


class TaskManager:
    """Lifecycle management for task_state SQLite rows."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(self, plan: TaskPlan, team_id: str = "") -> None:
        agent_states_json = json.dumps({slot.agent_name: "pending" for slot in plan.agents})
        await self._db.execute(
            """INSERT INTO task_state
               (task_id, team_id, status, objective, agent_states, token_total, cost_total_eur)
               VALUES (?, ?, 'pending', ?, ?, 0, 0.0)""",
            (plan.task_id, team_id, plan.objective, agent_states_json),
        )
        await self._db.commit()

    async def set_status(
        self,
        task_id: str,
        status: TaskStatus,
        tokens: int | None = None,
        cost_eur: float | None = None,
    ) -> None:
        fields = ["status = ?", "updated_at = datetime('now')"]
        params: list = [status.value]

        if tokens is not None:
            fields.append("token_total = ?")
            params.append(tokens)
        if cost_eur is not None:
            fields.append("cost_total_eur = ?")
            params.append(cost_eur)
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED):
            fields.append("completed_at = datetime('now')")

        params.append(task_id)
        await self._db.execute(
            f"UPDATE task_state SET {', '.join(fields)} WHERE task_id = ?",  # noqa: S608
            params,
        )
        await self._db.commit()

    async def update_agent_states(
        self,
        task_id: str,
        agent_states: dict[str, str],
    ) -> None:
        await self._db.execute(
            "UPDATE task_state SET agent_states = ?, updated_at = datetime('now')"
            " WHERE task_id = ?",
            (json.dumps(agent_states), task_id),
        )
        await self._db.commit()

    async def list_recent(self, limit: int = 20) -> list[dict]:
        async with self._db.execute(
            """SELECT task_id, team_id, status, objective, token_total, cost_total_eur,
                      created_at, completed_at
               FROM task_state
               ORDER BY created_at DESC, rowid DESC
               LIMIT ?""",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {
                "task_id": r[0],
                "team_id": r[1],
                "status": r[2],
                "objective": r[3],
                "token_total": r[4],
                "cost_total_eur": r[5],
                "created_at": r[6],
                "completed_at": r[7],
            }
            for r in rows
        ]
