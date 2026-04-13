"""Tests for AgentStateMachine skill prepending."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.agent_run_store import AgentRunStore
from taim.brain.agent_state_machine import AgentStateMachine
from taim.brain.database import init_database
from taim.brain.prompts import PromptLoader
from taim.brain.skill_registry import SkillRegistry
from taim.brain.vault import VaultOps
from taim.models.agent import Agent, AgentStateEnum

from conftest import MockRouter, make_response


@pytest_asyncio.fixture
async def setup(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    db = await init_database(ops.vault_config.db_path)
    store = AgentRunStore(db)

    skills_dir = ops.vault_config.vault_root / "system" / "skills"
    skill_reg = SkillRegistry(skills_dir)
    skill_reg.load()

    yield ops, loader, store, skill_reg
    await db.close()


def _make_agent(skills: list[str] | None = None) -> Agent:
    return Agent(
        name="researcher",
        description="Test agent",
        model_preference=["tier2_standard"],
        skills=skills or [],
    )


@pytest.mark.asyncio
class TestSkillPrepending:
    async def test_skill_prepended_when_present(self, setup) -> None:
        _, loader, store, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = _make_agent(skills=["web_research"])
        sm = AgentStateMachine(
            agent=agent,
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="t1",
            task_description="research SaaS competitors",
            skill_registry=skill_reg,
        )
        await sm.run()
        # The EXECUTING call (index 1) should have skill content prepended
        executing_messages = router.calls[1]["messages"]
        prompt_content = executing_messages[0]["content"]
        # Web research skill mentions web_search/conducting research
        assert "research" in prompt_content.lower()
        # Skill template includes "conducting web research"
        assert "web research" in prompt_content.lower() or "web_search" in prompt_content.lower()

    async def test_no_skill_no_prepending(self, setup) -> None:
        _, loader, store, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = _make_agent(skills=[])
        sm = AgentStateMachine(
            agent=agent,
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="t1",
            task_description="task",
            skill_registry=skill_reg,
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE

    async def test_no_registry_no_prepending(self, setup) -> None:
        _, loader, store, _ = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = _make_agent(skills=["web_research"])
        sm = AgentStateMachine(
            agent=agent,
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="t1",
            task_description="task",
            skill_registry=None,
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE

    async def test_unknown_skill_continues(self, setup) -> None:
        _, loader, store, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = _make_agent(skills=["nonexistent_skill"])
        sm = AgentStateMachine(
            agent=agent,
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="t1",
            task_description="task",
            skill_registry=skill_reg,
        )
        run = await sm.run()
        # Agent continues with base prompt only
        assert run.final_state == AgentStateEnum.DONE

    async def test_task_description_in_prompt(self, setup) -> None:
        _, loader, store, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = _make_agent(skills=["web_research"])
        sm = AgentStateMachine(
            agent=agent,
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="t1",
            task_description="UNIQUE_MARKER_xyz",
            skill_registry=skill_reg,
        )
        await sm.run()
        executing_prompt = router.calls[1]["messages"][0]["content"]
        assert "UNIQUE_MARKER_xyz" in executing_prompt
