"""HeartbeatManager — periodic check on active tasks."""

from __future__ import annotations

import asyncio
import time

import structlog

logger = structlog.get_logger()


class HeartbeatManager:
    """Periodic loop that monitors active tasks for timeout."""

    def __init__(
        self,
        interval_seconds: int = 30,
        agent_timeout_seconds: int = 120,
    ) -> None:
        self._interval = interval_seconds
        self._agent_timeout = agent_timeout_seconds
        self._running = False
        self._task: asyncio.Task | None = None
        self._active_tasks: dict[str, float] = {}  # task_id → last_activity_time

    def start(self) -> None:
        """Start the heartbeat loop as a background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("heartbeat.started", interval=self._interval)

    def stop(self) -> None:
        """Stop the heartbeat loop."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("heartbeat.stopped")

    def report_activity(self, task_id: str) -> None:
        """Called on every agent transition to reset the timeout clock."""
        self._active_tasks[task_id] = time.monotonic()

    def mark_complete(self, task_id: str) -> None:
        """Remove from active tracking when a task finishes."""
        self._active_tasks.pop(task_id, None)

    def get_stale_tasks(self) -> list[str]:
        """Return task_ids that haven't had activity within timeout."""
        now = time.monotonic()
        return [
            task_id
            for task_id, last_activity in self._active_tasks.items()
            if now - last_activity > self._agent_timeout
        ]

    @property
    def active_count(self) -> int:
        return len(self._active_tasks)

    async def _loop(self) -> None:
        while self._running:
            try:
                stale = self.get_stale_tasks()
                for task_id in stale:
                    logger.warning(
                        "heartbeat.stale_task",
                        task_id=task_id,
                        idle_seconds=time.monotonic() - self._active_tasks[task_id],
                    )
            except Exception:
                logger.exception("heartbeat.check_error")
            await asyncio.sleep(self._interval)
