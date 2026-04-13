"""Data models for tool execution."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Tool(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    requires_approval: bool = False
    source: str = "builtin"


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    call_id: str
    tool_name: str
    success: bool
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0


class ToolExecutionEvent(BaseModel):
    agent_name: str
    run_id: str
    tool_name: str
    status: str
    duration_ms: float = 0.0
    error: str = ""
    summary: str = ""
