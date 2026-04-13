"""Tests for Stage 1 — quick intent classification."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.conversation.classifier import CONFIDENCE_THRESHOLD, classify_intent
from taim.models.chat import IntentCategory

from conftest import MockRouter, make_classification_response


@pytest.fixture
def loader(tmp_vault: Path) -> PromptLoader:
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    return PromptLoader(ops.vault_config.prompts_dir)


@pytest.mark.asyncio
class TestClassifyIntent:
    async def test_returns_classification(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("new_task", 0.9)])
        result = await classify_intent(
            message="Build me a competitive analysis",
            recent_context="",
            router=router,
            prompt_loader=loader,
        )
        assert result.category == IntentCategory.NEW_TASK
        assert result.confidence == 0.9

    async def test_uses_tier3(self, loader: PromptLoader) -> None:
        from taim.models.router import ModelTierEnum
        router = MockRouter([make_classification_response("confirmation")])
        await classify_intent(message="yes", recent_context="", router=router, prompt_loader=loader)
        assert router.calls[0]["tier"] == ModelTierEnum.TIER3_ECONOMY

    async def test_requests_json_format(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("status_query")])
        await classify_intent(message="status?", recent_context="", router=router, prompt_loader=loader)
        assert router.calls[0]["expected_format"] == "json"

    async def test_passes_session_id(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("stop_command")])
        await classify_intent(message="stop", recent_context="", router=router, prompt_loader=loader, session_id="sess-1")
        assert router.calls[0]["session_id"] == "sess-1"


def test_threshold_constant() -> None:
    assert CONFIDENCE_THRESHOLD == 0.80
