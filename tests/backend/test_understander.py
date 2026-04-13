"""Tests for Stage 2 — deep task understanding."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.conversation.understander import understand_task

from conftest import MockRouter, make_intent_response


@pytest.fixture
def loader(tmp_vault: Path) -> PromptLoader:
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    return PromptLoader(ops.vault_config.prompts_dir)


@pytest.mark.asyncio
class TestUnderstandTask:
    async def test_returns_intent_result(self, loader: PromptLoader) -> None:
        router = MockRouter([make_intent_response("research", "Find SaaS competitors")])
        result = await understand_task(
            message="Research B2B SaaS competitors",
            recent_context="",
            router=router,
            prompt_loader=loader,
        )
        assert result.task_type == "research"
        assert result.objective == "Find SaaS competitors"

    async def test_uses_tier2(self, loader: PromptLoader) -> None:
        from taim.models.router import ModelTierEnum
        router = MockRouter([make_intent_response()])
        await understand_task(message="x", recent_context="", router=router, prompt_loader=loader)
        assert router.calls[0]["tier"] == ModelTierEnum.TIER2_STANDARD

    async def test_includes_user_preferences(self, loader: PromptLoader) -> None:
        router = MockRouter([make_intent_response()])
        await understand_task(
            message="x",
            recent_context="",
            router=router,
            prompt_loader=loader,
            user_preferences="prefers concise outputs",
        )
        assert "prefers concise outputs" in router.calls[0]["messages"][0]["content"]

    async def test_handles_empty_preferences(self, loader: PromptLoader) -> None:
        router = MockRouter([make_intent_response()])
        await understand_task(message="x", recent_context="", router=router, prompt_loader=loader, user_preferences="")
        assert "no preferences yet" in router.calls[0]["messages"][0]["content"]

    async def test_extracts_missing_info(self, loader: PromptLoader) -> None:
        router = MockRouter([make_intent_response(missing_info=["timeline", "budget"])])
        result = await understand_task(message="x", recent_context="", router=router, prompt_loader=loader)
        assert result.missing_info == ["timeline", "budget"]
