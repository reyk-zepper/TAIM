"""Tests for orchestration models."""

from taim.models.orchestration import TaskExecutionResult, TaskPlan, TaskStatus


class TestTaskStatus:
    def test_values(self) -> None:
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.STOPPED == "stopped"
        assert TaskStatus.FAILED == "failed"


class TestTaskPlan:
    def test_minimal(self) -> None:
        p = TaskPlan(task_id="t1", objective="test", agent_name="researcher")
        assert p.parameters == {}


class TestTaskExecutionResult:
    def test_defaults(self) -> None:
        r = TaskExecutionResult(task_id="t1", status=TaskStatus.COMPLETED, agent_name="researcher")
        assert r.result_content == ""
        assert r.tokens_used == 0
        assert r.cost_eur == 0.0
