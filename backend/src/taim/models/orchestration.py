"""Data models for orchestration."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class TaskPlan(BaseModel):
    """What the Orchestrator decides to execute. Step 7a: single-agent only."""

    task_id: str
    objective: str
    parameters: dict[str, Any] = {}
    agent_name: str


class TaskExecutionResult(BaseModel):
    """Final outcome of orchestrator run."""

    task_id: str
    status: TaskStatus
    agent_name: str
    result_content: str = ""
    tokens_used: int = 0
    cost_eur: float = 0.0
    duration_ms: float = 0.0
    error: str = ""
