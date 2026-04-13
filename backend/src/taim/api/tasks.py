"""Task REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from taim.api.deps import get_task_manager
from taim.orchestrator.task_manager import TaskManager

router = APIRouter(prefix="/api/tasks")


@router.get("")
async def list_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    manager: TaskManager = Depends(get_task_manager),
) -> dict:
    tasks = await manager.list_recent(limit=limit)
    return {"tasks": tasks, "count": len(tasks)}
