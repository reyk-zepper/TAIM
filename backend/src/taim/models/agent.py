"""Data models for agents and their execution state."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class AgentStateEnum(StrEnum):
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    REVIEWING = "REVIEWING"
    ITERATING = "ITERATING"
    WAITING = "WAITING"
    DONE = "DONE"
    FAILED = "FAILED"


class Agent(BaseModel):
    """Agent definition loaded from taim-vault/agents/{name}.yaml."""

    name: str
    description: str
    model_preference: list[str]
    skills: list[str]
    tools: list[str] = []
    max_iterations: int = 3
    requires_approval_for: list[str] = []


class StateTransition(BaseModel):
    """One transition in the state history."""

    from_state: AgentStateEnum | None
    to_state: AgentStateEnum
    timestamp: datetime
    reason: str = ""


class AgentState(BaseModel):
    """Runtime state snapshot for an agent run."""

    agent_name: str
    run_id: str
    current_state: AgentStateEnum = AgentStateEnum.PLANNING
    iteration: int = 0
    tokens_used: int = 0
    cost_eur: float = 0.0
    state_history: list[StateTransition] = []
    plan: str = ""
    current_result: str = ""
    review_feedback: str = ""


class AgentRun(BaseModel):
    """Completed execution record (for agent_runs SQLite table)."""

    run_id: str
    agent_name: str
    task_id: str
    team_id: str = ""
    session_id: str | None = None
    final_state: AgentStateEnum
    state_history: list[StateTransition] = []
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_eur: float = 0.0
    provider: str | None = None
    model_used: str | None = None
    failover_occurred: bool = False
    result_content: str = ""


class ReviewResult(BaseModel):
    """Structured output from REVIEWING state prompt."""

    quality_ok: bool
    feedback: str
    completeness: float = 1.0  # 0.0 to 1.0
    accuracy: float = 1.0  # 0.0 to 1.0
    relevance: float = 1.0  # 0.0 to 1.0
    rule_compliance: bool = True  # Were all mandatory rules followed?
