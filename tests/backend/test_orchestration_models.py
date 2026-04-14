"""Tests for orchestration models."""

from taim.models.orchestration import (
    OrchestrationPattern,
    TaskExecutionResult,
    TaskPlan,
    TaskStatus,
    TeamAgentSlot,
)


class TestTaskStatus:
    def test_values(self) -> None:
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.STOPPED == "stopped"
        assert TaskStatus.FAILED == "failed"


class TestOrchestrationPattern:
    def test_sequential(self) -> None:
        assert OrchestrationPattern.SEQUENTIAL == "sequential"


class TestTeamAgentSlot:
    def test_minimal(self) -> None:
        s = TeamAgentSlot(role="researcher", agent_name="researcher")
        assert s.role == "researcher"
        assert s.agent_name == "researcher"

    def test_different_role_and_name(self) -> None:
        s = TeamAgentSlot(role="primary", agent_name="coder")
        assert s.role == "primary"
        assert s.agent_name == "coder"


class TestTaskPlan:
    def test_single_agent(self) -> None:
        p = TaskPlan(
            task_id="t1",
            objective="test",
            agents=[TeamAgentSlot(role="primary", agent_name="researcher")],
        )
        assert p.is_single_agent is True
        assert p.primary_agent_name == "researcher"

    def test_multi_agent(self) -> None:
        p = TaskPlan(
            task_id="t1",
            objective="test",
            agents=[
                TeamAgentSlot(role="researcher", agent_name="researcher"),
                TeamAgentSlot(role="analyst", agent_name="analyst"),
            ],
        )
        assert p.is_single_agent is False
        assert p.primary_agent_name == "researcher"

    def test_empty_agents(self) -> None:
        p = TaskPlan(task_id="t1", objective="test", agents=[])
        assert p.is_single_agent is True
        assert p.primary_agent_name == ""

    def test_parameters_default_empty(self) -> None:
        p = TaskPlan(
            task_id="t1",
            objective="test",
            agents=[TeamAgentSlot(role="primary", agent_name="researcher")],
        )
        assert p.parameters == {}

    def test_pattern_default_sequential(self) -> None:
        p = TaskPlan(
            task_id="t1",
            objective="test",
            agents=[TeamAgentSlot(role="primary", agent_name="researcher")],
        )
        assert p.pattern == OrchestrationPattern.SEQUENTIAL

    def test_estimated_cost_default_zero(self) -> None:
        p = TaskPlan(
            task_id="t1",
            objective="test",
            agents=[TeamAgentSlot(role="primary", agent_name="researcher")],
        )
        assert p.estimated_cost_eur == 0.0


class TestTaskExecutionResult:
    def test_defaults(self) -> None:
        r = TaskExecutionResult(task_id="t1", status=TaskStatus.COMPLETED, agent_name="researcher")
        assert r.result_content == ""
        assert r.tokens_used == 0
        assert r.cost_eur == 0.0
