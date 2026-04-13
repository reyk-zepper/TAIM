"""Skill model — reusable prompt+tool pattern."""

from __future__ import annotations

from pydantic import BaseModel


class Skill(BaseModel):
    """Reusable prompt+tool pattern for agent specialization."""

    name: str
    description: str
    required_tools: list[str] = []
    prompt_template: str
    output_format: str = "markdown"
