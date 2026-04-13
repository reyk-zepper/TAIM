"""Tests for AgentStateMachine."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.agent_run_store import AgentRunStore
from taim.brain.agent_state_machine import AgentStateMachine, TransitionEvent
from taim.brain.database import init_database
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.models.agent import Agent, AgentStateEnum

from conftest import MockRouter, make_response


def _make_agent(name: str = "researcher", max_iter: int = 2) -> Agent:
    return Agent(
        name=name,
        description=f"Test {name}",
        model_preference=["tier2_standard"],
        skills=[],
        max_iterations=max_iter,
    )


@pytest_asyncio.fixture
async def setup(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    db = await init_database(ops.vault_config.db_path)
    store = AgentRunStore(db)
    yield ops, loader, store
    await db.close()


@pytest.mark.asyncio
class TestHappyPath:
    async def test_planning_to_done(self, setup) -> None:
        _, loader, store = setup
        router = MockRouter([
            make_response("The plan is X"),
            make_response("Execution result"),
            make_response('{"quality_ok": true, "feedback": "Good"}'),
        ])
        sm = AgentStateMachine(
            agent=_make_agent(),
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="task-1",
            task_description="Research X",
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
        assert run.result_content == "Execution result"
        assert len(run.state_history) == 4

    async def test_transition_events(self, setup) -> None:
        _, loader, store = setup
        events: list[TransitionEvent] = []
        async def capture(e: TransitionEvent) -> None:
            events.append(e)
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": ""}'),
        ])
        sm = AgentStateMachine(
            agent=_make_agent(),
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
            on_transition=capture,
        )
        await sm.run()
        states = [e.to_state for e in events]
        assert states == [
            AgentStateEnum.PLANNING, AgentStateEnum.EXECUTING,
            AgentStateEnum.REVIEWING, AgentStateEnum.DONE,
        ]


@pytest.mark.asyncio
class TestIterationLoop:
    async def test_reviewing_to_iterating_to_executing(self, setup) -> None:
        _, loader, store = setup
        router = MockRouter([
            make_response("plan"),
            make_response("first result"),
            make_response('{"quality_ok": false, "feedback": "needs more detail"}'),
            make_response("improved result"),
            make_response("re-executed result"),
            make_response('{"quality_ok": true, "feedback": "better"}'),
        ])
        sm = AgentStateMachine(
            agent=_make_agent(max_iter=3),
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
        assert run.result_content == "re-executed result"

    async def test_max_iterations_stops(self, setup) -> None:
        _, loader, store = setup
        # Always fail review. With max_iter=1, iteration loop hits the cap.
        # Sequence: PLAN, EXEC, REV(fail), ITER, EXEC, REV(fail at cap → DONE)
        router = MockRouter([
            make_response("plan"),
            make_response("r1"),
            make_response('{"quality_ok": false, "feedback": "bad"}'),
            make_response("r2"),
            make_response("r3"),
            make_response('{"quality_ok": false, "feedback": "still bad"}'),
        ])
        sm = AgentStateMachine(
            agent=_make_agent(max_iter=1),
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
        assert "max_iterations" in run.state_history[-1].reason


@pytest.mark.asyncio
class TestFailure:
    async def test_all_providers_failed_transitions_to_failed(self, setup) -> None:
        from taim.errors import AllProvidersFailed
        _, loader, store = setup
        router = MockRouter([AllProvidersFailed(user_message="fail", detail="d")])
        sm = AgentStateMachine(
            agent=_make_agent(),
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.FAILED

    async def test_unparseable_review_accepts_result(self, setup) -> None:
        _, loader, store = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response("totally not json"),
        ])
        sm = AgentStateMachine(
            agent=_make_agent(),
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
        )
        run = await sm.run()
        # Fail-safe: accepted as-is
        assert run.final_state == AgentStateEnum.DONE


@pytest.mark.asyncio
class TestPromptFallback:
    async def test_researcher_override_loadable(self, setup) -> None:
        """researcher/executing.yaml exists (seeded). Verify it's loadable."""
        _, loader, _ = setup
        override = loader.load("agents/researcher/executing", {
            "task_description": "x", "agent_description": "y", "plan": "p",
            "iteration": "0", "user_preferences": "(none)",
        })
        assert "researcher" in override.lower() or "verify sources" in override.lower()

    async def test_falls_back_to_default_for_unknown_agent(self, setup) -> None:
        _, loader, store = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = Agent(
            name="nonexistent_agent",
            description="No override",
            model_preference=["tier2_standard"],
            skills=[],
        )
        sm = AgentStateMachine(
            agent=agent,
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
