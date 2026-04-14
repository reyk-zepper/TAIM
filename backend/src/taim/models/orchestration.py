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


class OrchestrationPattern(StrEnum):
    SEQUENTIAL = "sequential"


class TeamAgentSlot(BaseModel):
    """One agent assigned to a role in a team."""

    role: str
    agent_name: str


class TaskPlan(BaseModel):
    """What the Orchestrator decides to execute. Step 7b: multi-agent support."""

    task_id: str
    objective: str
    parameters: dict[str, Any] = {}
    agents: list[TeamAgentSlot]
    pattern: OrchestrationPattern = OrchestrationPattern.SEQUENTIAL
    estimated_cost_eur: float = 0.0

    @property
    def is_single_agent(self) -> bool:
        return len(self.agents) <= 1

    @property
    def primary_agent_name(self) -> str:
        return self.agents[0].agent_name if self.agents else ""


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
