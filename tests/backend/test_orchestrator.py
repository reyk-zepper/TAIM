"""Tests for Orchestrator — end-to-end coordination."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.agent_registry import AgentRegistry
from taim.brain.agent_run_store import AgentRunStore
from taim.brain.database import init_database
from taim.brain.prompts import PromptLoader
from taim.brain.skill_registry import SkillRegistry
from taim.brain.vault import VaultOps
from taim.models.chat import IntentResult, TaskConstraints
from taim.models.orchestration import TaskStatus
from taim.orchestrator.orchestrator import Orchestrator
from taim.orchestrator.task_manager import TaskManager
from taim.orchestrator.team_composer import TeamComposer

from conftest import MockRouter, make_response


@pytest_asyncio.fixture
async def setup(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    db = await init_database(ops.vault_config.db_path)
    run_store = AgentRunStore(db)
    task_mgr = TaskManager(db)

    agent_reg = AgentRegistry(ops.vault_config.agents_dir)
    agent_reg.load()
    composer = TeamComposer(agent_reg)

    skill_reg = SkillRegistry(ops.vault_config.vault_root / "system" / "skills")
    skill_reg.load()

    yield ops, loader, db, run_store, task_mgr, agent_reg, composer, skill_reg
    await db.close()


def _build_orchestrator(
    router,
    composer: TeamComposer,
    task_mgr: TaskManager,
    agent_reg: AgentRegistry,
    run_store: AgentRunStore,
    loader: PromptLoader,
    skill_reg: SkillRegistry,
) -> Orchestrator:
    return Orchestrator(
        composer=composer,
        task_manager=task_mgr,
        agent_registry=agent_reg,
        agent_run_store=run_store,
        prompt_loader=loader,
        router=router,
        skill_registry=skill_reg,
    )


def _intent(task_type: str = "research", objective: str = "test task") -> IntentResult:
    return IntentResult(
        task_type=task_type,
        objective=objective,
        constraints=TaskConstraints(),
    )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_intent_to_completion(self, setup) -> None:
        _, loader, _, run_store, task_mgr, agent_reg, composer, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result text"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        orch = _build_orchestrator(router, composer, task_mgr, agent_reg, run_store, loader, skill_reg)

        result = await orch.execute(_intent(), session_id="s1")
        assert result.status == TaskStatus.COMPLETED
        assert result.agent_name == "researcher"  # rule: research → researcher
        assert result.result_content == "result text"
        assert result.duration_ms > 0

    async def test_task_created_in_db(self, setup) -> None:
        _, loader, _, run_store, task_mgr, agent_reg, composer, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        orch = _build_orchestrator(router, composer, task_mgr, agent_reg, run_store, loader, skill_reg)

        await orch.execute(_intent(), session_id="s1")
        tasks = await task_mgr.list_recent()
        assert len(tasks) == 1
        assert tasks[0]["status"] == "completed"
        assert tasks[0]["objective"] == "test task"


@pytest.mark.asyncio
class TestFailures:
    async def test_no_agent_available(self, tmp_path: Path) -> None:
        # Empty registry
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        db = await init_database(tmp_path / "taim.db")
        try:
            agent_reg = AgentRegistry(agents_dir)
            agent_reg.load()
            composer = TeamComposer(agent_reg)
            task_mgr = TaskManager(db)
            run_store = AgentRunStore(db)

            prompts_dir = tmp_path / "prompts"
            prompts_dir.mkdir()
            loader = PromptLoader(prompts_dir)

            router = MockRouter([])
            orch = Orchestrator(
                composer=composer,
                task_manager=task_mgr,
                agent_registry=agent_reg,
                agent_run_store=run_store,
                prompt_loader=loader,
                router=router,
            )

            result = await orch.execute(_intent(), session_id="s1")
            assert result.status == TaskStatus.FAILED
            assert "No suitable agent" in result.error
        finally:
            await db.close()


@pytest.mark.asyncio
class TestEventCallbacks:
    async def test_agent_events_forwarded(self, setup) -> None:
        _, loader, _, run_store, task_mgr, agent_reg, composer, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        orch = _build_orchestrator(router, composer, task_mgr, agent_reg, run_store, loader, skill_reg)

        events = []

        async def capture(e):
            events.append(e)

        result = await orch.execute(_intent(), session_id="s1", on_agent_event=capture)
        assert result.status == TaskStatus.COMPLETED
        # Should have received PLANNING, EXECUTING, REVIEWING, DONE transitions
        states = [e.to_state.value for e in events]
        assert "PLANNING" in states
        assert "EXECUTING" in states
        assert "DONE" in states


@pytest.mark.asyncio
class TestTaskDescription:
    async def test_includes_parameters(self, setup) -> None:
        _, loader, _, run_store, task_mgr, agent_reg, composer, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        orch = _build_orchestrator(router, composer, task_mgr, agent_reg, run_store, loader, skill_reg)

        intent = IntentResult(
            task_type="research",
            objective="Find info",
            parameters={"topic": "SaaS competitors", "year": 2026},
            constraints=TaskConstraints(),
        )
        await orch.execute(intent, session_id="s1")

        # The PLANNING prompt (first router call) should include the parameters
        planning_messages = router.calls[0]["messages"]
        planning_prompt = planning_messages[0]["content"]
        assert "SaaS competitors" in planning_prompt
