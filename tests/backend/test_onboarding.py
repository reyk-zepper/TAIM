"""Tests for OnboardingFlow and SmartDefaults."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.memory import MemoryManager
from taim.conversation.defaults import SmartDefaults
from taim.conversation.onboarding import OnboardingFlow, OnboardingState, OnboardingStep
from taim.models.chat import IntentResult, TaskConstraints


@pytest.fixture
def memory(tmp_path: Path) -> MemoryManager:
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    return MemoryManager(users_dir)


@pytest.mark.asyncio
class TestOnboardingFlow:
    async def test_is_needed_when_no_profile(self, memory: MemoryManager) -> None:
        flow = OnboardingFlow(memory)
        assert await flow.is_needed() is True

    async def test_not_needed_after_completion(self, memory: MemoryManager) -> None:
        flow = OnboardingFlow(memory)
        state = OnboardingState()

        await flow.handle_response(state, "I'm a marketing manager")
        await flow.handle_response(state, "skip")
        await flow.handle_response(state, "no rules")
        await flow.handle_response(state, "ok")

        assert state.is_complete
        assert await flow.is_needed() is False

    async def test_full_flow_steps(self, memory: MemoryManager) -> None:
        flow = OnboardingFlow(memory)
        state = OnboardingState()
        assert state.step == OnboardingStep.WELCOME

        r1 = await flow.handle_response(state, "Marketing manager at B2B SaaS")
        assert state.step == OnboardingStep.API_KEY
        assert "API key" in r1

        r2 = await flow.handle_response(state, "ollama")
        assert state.step == OnboardingStep.RULES
        assert "rules" in r2.lower()

        r3 = await flow.handle_response(state, "GDPR compliance required")
        assert state.step == OnboardingStep.SUMMARY
        assert "GDPR" in r3
        assert "Marketing manager" in r3

        r4 = await flow.handle_response(state, "ok")
        assert state.is_complete
        assert "all set" in r4.lower()

    async def test_persists_profile(self, memory: MemoryManager) -> None:
        flow = OnboardingFlow(memory)
        state = OnboardingState()
        await flow.handle_response(state, "Data scientist")
        await flow.handle_response(state, "skip")
        await flow.handle_response(state, "no rules")

        entry = await memory.read_entry("user-profile.md")
        assert entry is not None
        assert "Data scientist" in entry.content

    async def test_persists_rules(self, memory: MemoryManager) -> None:
        flow = OnboardingFlow(memory)
        state = OnboardingState()
        await flow.handle_response(state, "Dev")
        await flow.handle_response(state, "skip")
        await flow.handle_response(state, "Never share API keys")

        entry = await memory.read_entry("compliance-rules.md")
        assert entry is not None
        assert "API keys" in entry.content

    async def test_no_rules_skips_persistence(self, memory: MemoryManager) -> None:
        flow = OnboardingFlow(memory)
        state = OnboardingState()
        await flow.handle_response(state, "Dev")
        await flow.handle_response(state, "skip")
        await flow.handle_response(state, "no rules")

        entry = await memory.read_entry("compliance-rules.md")
        assert entry is None

    async def test_welcome_message(self, memory: MemoryManager) -> None:
        flow = OnboardingFlow(memory)
        msg = flow.get_welcome_message()
        assert "tAIm" in msg
        assert "work" in msg.lower()


class TestSmartDefaults:
    def test_applies_time_budget(self) -> None:
        defaults = SmartDefaults({"team": {"time_budget": "3h"}})
        intent = IntentResult(
            task_type="research",
            objective="test",
            constraints=TaskConstraints(),
        )
        result = defaults.apply(intent)
        assert result.constraints.time_limit_seconds == 10800

    def test_applies_token_budget(self) -> None:
        defaults = SmartDefaults({"team": {"token_budget": 100000}})
        intent = IntentResult(
            task_type="research",
            objective="test",
            constraints=TaskConstraints(),
        )
        result = defaults.apply(intent)
        assert result.constraints.budget_eur == 1.0

    def test_does_not_override_explicit_constraints(self) -> None:
        defaults = SmartDefaults({"team": {"time_budget": "3h"}})
        intent = IntentResult(
            task_type="research",
            objective="test",
            constraints=TaskConstraints(time_limit_seconds=600),
        )
        result = defaults.apply(intent)
        assert result.constraints.time_limit_seconds == 600

    def test_parse_time_formats(self) -> None:
        assert SmartDefaults._parse_time("2h") == 7200
        assert SmartDefaults._parse_time("30m") == 1800
        assert SmartDefaults._parse_time("1h30m") == 5400
