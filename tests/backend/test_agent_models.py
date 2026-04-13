"""Tests for agent data models."""

from datetime import datetime, timezone

from taim.models.agent import (
    Agent, AgentRun, AgentState, AgentStateEnum, ReviewResult, StateTransition,
)


class TestAgentStateEnum:
    def test_all_states(self) -> None:
        assert AgentStateEnum.PLANNING == "PLANNING"
        assert AgentStateEnum.EXECUTING == "EXECUTING"
        assert AgentStateEnum.REVIEWING == "REVIEWING"
        assert AgentStateEnum.ITERATING == "ITERATING"
        assert AgentStateEnum.WAITING == "WAITING"
        assert AgentStateEnum.DONE == "DONE"
        assert AgentStateEnum.FAILED == "FAILED"


class TestAgent:
    def test_minimal(self) -> None:
        a = Agent(
            name="researcher", description="Research",
            model_preference=["tier2_standard"], skills=["web_research"],
        )
        assert a.max_iterations == 3
        assert a.tools == []
        assert a.requires_approval_for == []


class TestStateTransition:
    def test_minimal(self) -> None:
        t = StateTransition(
            from_state=AgentStateEnum.PLANNING,
            to_state=AgentStateEnum.EXECUTING,
            timestamp=datetime.now(timezone.utc),
        )
        assert t.reason == ""

    def test_initial_transition_has_no_from_state(self) -> None:
        t = StateTransition(
            from_state=None,
            to_state=AgentStateEnum.PLANNING,
            timestamp=datetime.now(timezone.utc),
        )
        assert t.from_state is None


class TestAgentState:
    def test_defaults(self) -> None:
        s = AgentState(agent_name="researcher", run_id="run-1")
        assert s.current_state == AgentStateEnum.PLANNING
        assert s.iteration == 0
        assert s.state_history == []


class TestAgentRun:
    def test_minimal(self) -> None:
        r = AgentRun(
            run_id="run-1", agent_name="researcher", task_id="task-1",
            final_state=AgentStateEnum.DONE,
        )
        assert r.team_id == ""
        assert r.failover_occurred is False


class TestReviewResult:
    def test_quality_ok(self) -> None:
        r = ReviewResult(quality_ok=True, feedback="Looks good")
        assert r.quality_ok is True
