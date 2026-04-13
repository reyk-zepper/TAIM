"""Tests for Summarizer."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.memory import MemoryManager
from taim.brain.prompts import PromptLoader
from taim.brain.summarizer import Summarizer
from taim.brain.vault import VaultOps
from taim.models.memory import ChatMessage

from conftest import MockRouter, make_response


@pytest.fixture
def summarizer(tmp_vault: Path) -> Summarizer:
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    memory_mgr = MemoryManager(ops.vault_config.users_dir)
    router = MockRouter([make_response(
        "The user researched SaaS competitors. 3 companies identified."
    )])
    return Summarizer(
        router=router,
        prompt_loader=loader,
        memory_manager=memory_mgr,
    )


@pytest.mark.asyncio
class TestSummarizeAndStore:
    async def test_generates_summary(self, summarizer: Summarizer) -> None:
        messages = [
            ChatMessage(role="user", content="Research B2B SaaS competitors"),
            ChatMessage(role="assistant", content="Found 3 companies..."),
        ]
        summary = await summarizer.summarize_and_store("s1", messages)
        assert "SaaS competitors" in summary or "3 companies" in summary

    async def test_writes_warm_memory_entry(
        self, summarizer: Summarizer, tmp_vault: Path
    ) -> None:
        messages = [ChatMessage(role="user", content="test")]
        await summarizer.summarize_and_store("abc-123", messages)
        memory_dir = tmp_vault / "users" / "default" / "memory"
        files = list(memory_dir.glob("session-abc-123-summary.md"))
        assert len(files) == 1

    async def test_summary_stored_with_session_tag(
        self, summarizer: Summarizer, tmp_vault: Path
    ) -> None:
        messages = [ChatMessage(role="user", content="test")]
        await summarizer.summarize_and_store("xyz", messages)
        memory_file = tmp_vault / "users" / "default" / "memory" / "session-xyz-summary.md"
        content = memory_file.read_text()
        assert "xyz" in content  # session_id in tags
        assert "session-summary" in content  # category
