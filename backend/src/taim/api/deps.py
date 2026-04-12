"""FastAPI dependency injection functions."""

from __future__ import annotations

import aiosqlite
from fastapi import Request

from taim.brain.prompts import PromptLoader
from taim.models.config import SystemConfig
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
