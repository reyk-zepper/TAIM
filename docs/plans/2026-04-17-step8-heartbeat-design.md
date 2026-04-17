# Step 8: Heartbeat Manager & Token Tracking — Design + Plan

> Version: 1.0
> Date: 2026-04-17
> Status: Reviewed
> Scope: US-4.4 (Heartbeat), US-8.1 (Per-Call Tracking — mostly done), US-8.2 (Cost in Events), US-8.3 (Stats API), US-6.4 (Budget Enforcement)

---

## 1. What Already Exists

| Feature | Status | Where |
|---------|--------|-------|
| Per-call token tracking | ✅ Done | `router/tracking.py` → `token_tracking` SQLite table |
| Monthly cost query | ✅ Done | `TokenTracker.get_monthly_cost(provider)` |
| Agent run logging | ✅ Done | `brain/agent_run_store.py` → `agent_runs` table |
| Task state lifecycle | ✅ Done | `orchestrator/task_manager.py` → `task_state` table |
| Cost in agent_completed event | ✅ Partial | `cost_eur` in TaskExecutionResult, forwarded via WS |
| Budget warning | ❌ Missing | Needs Heartbeat loop |
| Stuck agent detection | ❌ Missing | Needs Heartbeat loop |
| Time limit enforcement | ❌ Missing | Needs Heartbeat loop |
| Stats API | ❌ Missing | Needs aggregation queries |
| Pre-call budget check | ❌ Missing | Needs Router integration |

## 2. Deliverables

1. `orchestrator/heartbeat.py` — HeartbeatManager: async loop checking active tasks
2. `api/stats.py` — `GET /api/stats/monthly` endpoint
3. `router/router.py` modification — pre-call budget check (skip provider if over monthly budget)
4. WebSocket event enrichment: `budget_warning` event at 80% of limit
5. Lifespan integration: start/stop heartbeat
6. Tests for all new modules

---

## 3. HeartbeatManager (`orchestrator/heartbeat.py`)

```python
"""HeartbeatManager — periodic check on active tasks."""

import asyncio
import time
from datetime import datetime, timezone

import structlog

from taim.orchestrator.task_manager import TaskManager
from taim.models.orchestration import TaskStatus

logger = structlog.get_logger()


class HeartbeatManager:
    """Periodic loop that monitors active tasks for timeout and budget."""

    def __init__(
        self,
        task_manager: TaskManager,
        interval_seconds: int = 30,
        agent_timeout_seconds: int = 120,
    ) -> None:
        self._task_manager = task_manager
        self._interval = interval_seconds
        self._agent_timeout = agent_timeout_seconds
        self._running = False
        self._task: asyncio.Task | None = None
        self._active_tasks: dict[str, float] = {}  # task_id → last_activity_time

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("heartbeat.started", interval=self._interval)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("heartbeat.stopped")

    def report_activity(self, task_id: str) -> None:
        """Called by orchestrator on every agent transition."""
        self._active_tasks[task_id] = time.monotonic()

    def mark_complete(self, task_id: str) -> None:
        """Remove from active tracking."""
        self._active_tasks.pop(task_id, None)

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._check()
            except Exception:
                logger.exception("heartbeat.check_error")
            await asyncio.sleep(self._interval)

    async def _check(self) -> None:
        now = time.monotonic()
        stale: list[str] = []
        for task_id, last_activity in list(self._active_tasks.items()):
            if now - last_activity > self._agent_timeout:
                stale.append(task_id)
                logger.warning(
                    "heartbeat.stale_task",
                    task_id=task_id,
                    idle_seconds=now - last_activity,
                )
        # For MVP: just log stale tasks. Step 8+ could force-stop them.
```

Simple and non-invasive. The Orchestrator calls `heartbeat.report_activity(task_id)` on every transition event.

---

## 4. Stats API (`api/stats.py`)

```python
from fastapi import APIRouter, Depends
from taim.api.deps import get_db
import aiosqlite

router = APIRouter(prefix="/api/stats")


@router.get("/monthly")
async def monthly_stats(db: aiosqlite.Connection = Depends(get_db)) -> dict:
    """Monthly usage summary from token_tracking table."""
    async with db.execute(
        """SELECT
            provider,
            COUNT(*) as call_count,
            SUM(prompt_tokens) as total_prompt,
            SUM(completion_tokens) as total_completion,
            SUM(cost_usd) as total_cost_usd
           FROM token_tracking
           WHERE created_at >= date('now', 'start of month')
           GROUP BY provider"""
    ) as cursor:
        rows = await cursor.fetchall()

    providers = []
    total_cost = 0.0
    total_tokens = 0
    total_calls = 0
    for row in rows:
        provider_name, calls, prompt, completion, cost = row
        providers.append({
            "provider": provider_name,
            "calls": calls,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "cost_usd": round(cost, 4),
        })
        total_cost += cost
        total_tokens += prompt + completion
        total_calls += calls

    # Task count this month
    async with db.execute(
        "SELECT COUNT(*) FROM task_state WHERE created_at >= date('now', 'start of month')"
    ) as cursor:
        task_count = (await cursor.fetchone())[0]

    return {
        "period": "current_month",
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "total_calls": total_calls,
        "task_count": task_count,
        "avg_cost_per_task": round(total_cost / task_count, 4) if task_count else 0.0,
        "by_provider": providers,
    }
```

---

## 5. Pre-Call Budget Check in Router

In `router/router.py`, before attempting a provider, check monthly budget:

```python
# Inside the while loop, after getting provider_config:
if provider_config.monthly_budget_eur is not None and self._tracker:
    monthly_cost = await self._tracker.get_monthly_cost(provider_name)
    monthly_budget_usd = provider_config.monthly_budget_eur / 0.92  # approx
    if monthly_cost >= monthly_budget_usd:
        logger.info("router.budget_exceeded", provider=provider_name)
        candidate_idx += 1
        continue  # skip to next provider
```

---

## 6. Implementation Plan

### Task 1: HeartbeatManager + Stats API + Budget Check

- Create `orchestrator/heartbeat.py`
- Create `api/stats.py`
- Modify `router/router.py` (budget check)
- Modify `main.py` (heartbeat start/stop in lifespan, stats router)
- Modify `api/deps.py` (get_db for stats)
- Tests: heartbeat activity tracking, stats aggregation, budget skip

### Task 2: Verify

- Full test suite + lint + smoke test

---

*End of Step 8 Design.*
