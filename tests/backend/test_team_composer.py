"""Tests for TeamComposer."""

from pathlib import Path

import pytest

from taim.brain.agent_registry import AgentRegistry
from taim.brain.vault import VaultOps
from taim.models.chat import IntentResult, TaskConstraints
from taim.orchestrator.team_composer import TeamComposer


@pytest.fixture
def registry(tmp_vault: Path) -> AgentRegistry:
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    r = AgentRegistry(ops.vault_config.agents_dir)
    r.load()
    return r


def _intent(task_type: str = "", objective: str = "", suggested: list[str] | None = None) -> IntentResult:
    return IntentResult(
        task_type=task_type,
        objective=objective,
        constraints=TaskConstraints(),
        suggested_team=suggested or [],
    )


class TestComposeSingleAgent:
    def test_suggested_team_wins(self, registry) -> None:
        composer = TeamComposer(registry)
        agent = composer.compose_single_agent(_intent(suggested=["writer"]))
        assert agent is not None and agent.name == "writer"

    def test_research_task_type(self, registry) -> None:
        composer = TeamComposer(registry)
        agent = composer.compose_single_agent(_intent(task_type="research"))
        assert agent is not None and agent.name == "researcher"

    def test_code_review_task_type(self, registry) -> None:
        composer = TeamComposer(registry)
        agent = composer.compose_single_agent(_intent(task_type="code_review"))
        assert agent is not None and agent.name == "reviewer"

    def test_data_analysis_task_type(self, registry) -> None:
        composer = TeamComposer(registry)
        agent = composer.compose_single_agent(_intent(task_type="data_analysis"))
        assert agent is not None and agent.name == "analyst"

    def test_content_writing_task_type(self, registry) -> None:
        composer = TeamComposer(registry)
        agent = composer.compose_single_agent(_intent(task_type="content_writing"))
        assert agent is not None and agent.name == "writer"

    def test_skill_fallback(self, registry) -> None:
        """Unknown task_type but objective mentions a skill keyword."""
        composer = TeamComposer(registry)
        # "pattern" is in analyst.skills ("pattern_recognition")
        agent = composer.compose_single_agent(_intent(task_type="misc", objective="find patterns in data"))
        assert agent is not None

    def test_empty_registry_returns_none(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        registry = AgentRegistry(empty_dir)
        registry.load()
        composer = TeamComposer(registry)
        agent = composer.compose_single_agent(_intent(task_type="research"))
        assert agent is None

    def test_last_resort_first_agent(self, registry) -> None:
        """Unknown everything — returns some agent (not None)."""
        composer = TeamComposer(registry)
        agent = composer.compose_single_agent(_intent(task_type="xyz"))
        assert agent is not None
