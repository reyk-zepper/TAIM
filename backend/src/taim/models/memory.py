"""Data models for the memory system."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import ClassVar

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """A Markdown memory note with YAML frontmatter."""

    title: str
    category: str
    tags: list[str] = []
    created: date
    updated: date
    content: str
    confidence: float = 1.0
    source: str = "session"


class MemoryIndexEntry(BaseModel):
    """One line in INDEX.md."""

    filename: str
    summary: str
    tags: list[str]
    updated: date


class MemoryIndex(BaseModel):
    """Parsed INDEX.md."""

    entries: list[MemoryIndexEntry] = []


class ChatMessage(BaseModel):
    """Message in hot memory / session history."""

    role: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HotMemorySession(BaseModel):
    """Per-session in-memory state."""

    MAX_MESSAGES: ClassVar[int] = 20

    session_id: str
    user_id: str = "default"
    messages: list[ChatMessage] = []
    task_context: dict = {}
    team_state: dict = {}
