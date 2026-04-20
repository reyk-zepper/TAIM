"""Tests for SWAT Builder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from taim.brain.agent_registry import AgentRegistry
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.models.chat import IntentResult, TaskConstraints
from taim.orchestrator.swat_builder import SwatBuilder
from taim.orchestrator.team_composer import TeamComposer

from conftest import MockRouter, make_response


@pytest.fixture
def setup(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    registry = AgentRegistry(ops.vault_config.agents_dir)
    registry.load()
    composer = TeamComposer(registry)
    return registry, loader, composer


def _intent(task_type: str = "research", objective: str = "test") -> IntentResult:
    return IntentResult(
        task_type=task_type, objective=objective, constraints=TaskConstraints(),
    )


@pytest.mark.asyncio
class TestBuildTeam:
    async def test_llm_returns_valid_team(self, setup) -> None:
        registry, loader, composer = setup
        llm_response = json.dumps({
            "agents": [
                {"role": "researcher", "agent_name": "researcher"},
                {"role": "analyst", "agent_name": "analyst"},
            ],
            "reasoning": "Research task needs both",
        })
        router = MockRouter([make_response(llm_response)])
        builder = SwatBuilder(registry, router, loader, composer)

        slots = await builder.build_team(_intent())
        names = [s.agent_name for s in slots]
        assert "researcher" in names
        assert "analyst" in names

    async def test_falls_back_on_llm_failure(self, setup) -> None:
        registry, loader, composer = setup
        router = MockRouter([Exception("LLM down")])
        builder = SwatBuilder(registry, router, loader, composer)

        slots = await builder.build_team(_intent())
        # Fallback to rule-based — should still get agents
        assert len(slots) >= 1

    async def test_suggested_team_wins(self, setup) -> None:
        registry, loader, composer = setup
        router = MockRouter([])  # Should never be called
        builder = SwatBuilder(registry, router, loader, composer)

        intent = IntentResult(
            task_type="x", objective="x",
            constraints=TaskConstraints(),
            suggested_team=["writer"],
        )
        slots = await builder.build_team(intent)
        assert slots[0].agent_name == "writer"

    async def test_invalid_llm_response_falls_back(self, setup) -> None:
        registry, loader, composer = setup
        router = MockRouter([make_response("not json at all")])
        builder = SwatBuilder(registry, router, loader, composer)

        slots = await builder.build_team(_intent())
        # Should fall back gracefully
        assert len(slots) >= 1

    async def test_llm_suggests_nonexistent_agent_filtered(self, setup) -> None:
        registry, loader, composer = setup
        llm_response = json.dumps({
            "agents": [
                {"role": "x", "agent_name": "nonexistent"},
                {"role": "researcher", "agent_name": "researcher"},
            ],
        })
        router = MockRouter([make_response(llm_response)])
        builder = SwatBuilder(registry, router, loader, composer)

        slots = await builder.build_team(_intent())
        names = [s.agent_name for s in slots]
        assert "nonexistent" not in names
        assert "researcher" in names
