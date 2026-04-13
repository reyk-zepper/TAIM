"""Data models for chat / intent interpretation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class IntentCategory(StrEnum):
    NEW_TASK = "new_task"
    CONFIRMATION = "confirmation"
    FOLLOW_UP = "follow_up"
    STATUS_QUERY = "status_query"
    CONFIGURATION = "configuration"
    STOP_COMMAND = "stop_command"
    ONBOARDING_RESPONSE = "onboarding_response"


class IntentClassification(BaseModel):
    """Stage 1 output."""

    category: IntentCategory
    confidence: float = Field(ge=0.0, le=1.0)
    needs_deep_analysis: bool = False


class TaskConstraints(BaseModel):
    """Constraints parsed from a Stage 2 user message."""

    time_limit_seconds: int | None = None
    budget_eur: float | None = None
    specific_agents: list[str] = []
    model_tier_override: str | None = None


class IntentResult(BaseModel):
    """Stage 2 output — structured task command."""

    task_type: str
    objective: str
    parameters: dict[str, str | int | float | bool] = {}
    constraints: TaskConstraints = TaskConstraints()
    missing_info: list[str] = []
    suggested_team: list[str] = []


class InterpreterResult(BaseModel):
    """Final output of IntentInterpreter."""

    classification: IntentClassification
    intent: IntentResult | None = None
    direct_response: str | None = None
    needs_followup: bool = False
    followup_question: str | None = None
