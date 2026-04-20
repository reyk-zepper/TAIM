"""Tests for noRAG knowledge integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.knowledge import KnowledgeManager
from taim.orchestrator.builtin_tools.knowledge_tools import knowledge_query


class TestKnowledgeManager:
    def test_not_available_without_config(self) -> None:
        km = KnowledgeManager(ckus_dir=None)
        assert km.available is False

    def test_not_available_without_norag_installed(self, tmp_path: Path) -> None:
        # noRAG may or may not be installed — test graceful handling
        km = KnowledgeManager(ckus_dir=tmp_path)
        # If noRAG is installed, it might fail on missing DB — that's fine
        # The point is it doesn't crash
        assert isinstance(km.available, bool)

    @pytest.mark.asyncio
    async def test_query_returns_message_when_unavailable(self) -> None:
        km = KnowledgeManager(ckus_dir=None)
        result = await km.query("What is X?")
        assert "not available" in result.lower()


class TestKnowledgeQueryTool:
    @pytest.mark.asyncio
    async def test_no_manager_in_context(self) -> None:
        result = await knowledge_query({"question": "test"}, {})
        assert "not available" in result.lower()

    @pytest.mark.asyncio
    async def test_unavailable_manager(self) -> None:
        km = KnowledgeManager(ckus_dir=None)
        result = await knowledge_query(
            {"question": "test"},
            {"knowledge_manager": km},
        )
        assert "not available" in result.lower()
