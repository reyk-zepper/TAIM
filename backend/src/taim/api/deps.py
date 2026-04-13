"""FastAPI dependency injection functions."""

from __future__ import annotations

import aiosqlite
from fastapi import Request

from taim.brain.agent_registry import AgentRegistry
from taim.brain.agent_run_store import AgentRunStore
from taim.brain.prompts import PromptLoader
from taim.conversation import IntentInterpreter
from taim.models.config import SystemConfig
from taim.orchestrator.tools import ToolExecutor
from taim.router.router import LLMRouter


def get_config(request: Request) -> SystemConfig:
    """Inject the SystemConfig singleton."""
    return request.app.state.config


def get_db(request: Request) -> aiosqlite.Connection:
    """Inject the SQLite database connection."""
    return request.app.state.db


def get_prompt_loader(request: Request) -> PromptLoader:
    """Inject the PromptLoader singleton."""
    return request.app.state.prompt_loader


def get_router(request: Request) -> LLMRouter:
    """Inject the LLMRouter singleton."""
    return request.app.state.router


def get_interpreter(request: Request) -> IntentInterpreter:
    """Inject the IntentInterpreter singleton."""
    return request.app.state.interpreter


def get_registry(request: Request) -> AgentRegistry:
    """Inject the AgentRegistry singleton."""
    return request.app.state.agent_registry


def get_agent_run_store(request: Request) -> AgentRunStore:
    """Inject the AgentRunStore singleton."""
    return request.app.state.agent_run_store


def get_tool_executor(request: Request) -> ToolExecutor:
    """Inject the ToolExecutor singleton."""
    return request.app.state.tool_executor
