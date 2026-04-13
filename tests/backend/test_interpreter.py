"""Tests for IntentInterpreter — full two-stage flow."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.conversation.interpreter import IntentInterpreter
from taim.models.chat import IntentCategory

from conftest import MockRouter, make_classification_response, make_intent_response


@pytest.fixture
def loader(tmp_vault: Path) -> PromptLoader:
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    return PromptLoader(ops.vault_config.prompts_dir)


@pytest.mark.asyncio
class TestDirectCategories:
    async def test_status_query_no_stage2(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("status_query", 0.95)])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="status?", session_id="s1")
        assert result.classification.category == IntentCategory.STATUS_QUERY
        assert result.intent is None
        assert result.direct_response is not None
        assert len(router.calls) == 1

    async def test_stop_command_no_stage2(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("stop_command", 0.92)])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="stop", session_id="s1")
        assert result.intent is None
        assert "no active team" in result.direct_response.lower()

    async def test_confirmation_no_stage2(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("confirmation", 0.95)])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="yes", session_id="s1")
        assert result.intent is None
        assert "proceeding" in result.direct_response.lower()


@pytest.mark.asyncio
class TestStage2Invocation:
    async def test_new_task_invokes_stage2(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("new_task", 0.95),
            make_intent_response("research", "Find SaaS competitors"),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="Research SaaS competitors", session_id="s1")
        assert result.intent is not None
        assert result.intent.task_type == "research"
        assert len(router.calls) == 2

    async def test_low_confidence_escalates(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("confirmation", 0.5),
            make_intent_response("clarification", "Unclear request"),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="maybe yes do it", session_id="s1")
        assert result.intent is not None
        assert len(router.calls) == 2

    async def test_needs_deep_analysis_flag_escalates(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("status_query", 0.95, needs_deep=True),
            make_intent_response(),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="how is the third agent doing on iteration 4?", session_id="s1")
        assert result.intent is not None
        assert len(router.calls) == 2


@pytest.mark.asyncio
class TestFollowup:
    async def test_missing_info_creates_followup(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("new_task", 0.95),
            make_intent_response(missing_info=["target audience"]),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="Write some content", session_id="s1")
        assert result.needs_followup is True
        assert "target audience" in result.followup_question

    async def test_no_missing_info_no_followup(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("new_task", 0.95),
            make_intent_response(missing_info=[]),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="Research X with €50 budget by tomorrow", session_id="s1")
        assert result.needs_followup is False


@pytest.mark.asyncio
class TestMemoryIntegration:
    async def test_loads_preferences_when_memory_provided(self, loader: PromptLoader) -> None:
        class StubMemory:
            async def get_preferences_text(self) -> str:
                return "User prefers concise outputs"

        router = MockRouter([
            make_classification_response("new_task", 0.95),
            make_intent_response(),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader, memory=StubMemory())
        await interpreter.interpret(message="x", session_id="s1")
        stage2_prompt = router.calls[1]["messages"][0]["content"]
        assert "User prefers concise outputs" in stage2_prompt

    async def test_no_memory_uses_placeholder(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("new_task", 0.95),
            make_intent_response(),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader, memory=None)
        await interpreter.interpret(message="x", session_id="s1")
        stage2_prompt = router.calls[1]["messages"][0]["content"]
        assert "no preferences yet" in stage2_prompt


@pytest.mark.asyncio
class TestRecentContext:
    async def test_includes_recent_messages_in_stage1(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("new_task", 0.95), make_intent_response()])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        await interpreter.interpret(
            message="continue with that",
            session_id="s1",
            recent_context=[
                {"role": "user", "content": "research X"},
                {"role": "assistant", "content": "got it"},
            ],
        )
        stage1_prompt = router.calls[0]["messages"][0]["content"]
        assert "research X" in stage1_prompt
