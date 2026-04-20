"""Data models for the Learning Loop."""

from __future__ import annotations

from pydantic import BaseModel


class TaskFeedback(BaseModel):
    """Quality assessment of a completed agent run."""

    task_id: str
    agent_name: str
    score: float  # 0.0 (bad) to 1.0 (excellent)
    source: str  # "auto_heuristic" or "user_explicit"
    signals: dict = {}
    task_type: str = ""
    objective: str = ""
