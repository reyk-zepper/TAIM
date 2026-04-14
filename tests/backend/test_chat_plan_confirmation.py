"""Integration test: multi-agent plan confirmation flow."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from taim.api.chat import router as chat_router
from taim.brain.agent_registry import AgentRegistry
from taim.brain.agent_run_store import AgentRunStore
from taim.brain.database import init_database
from taim.brain.hot_memory import HotMemory
from taim.brain.memory import MemoryManager
from taim.brain.prompts import PromptLoader
from taim.brain.session_store import SessionStore
from taim.brain.skill_registry import SkillRegistry
from taim.brain.vault import VaultOps
from taim.conversation import IntentInterpreter
from taim.orchestrator.orchestrator import Orchestrator
from taim.orchestrator.task_manager import TaskManager
from taim.orchestrator.team_composer import TeamComposer

from conftest import MockRouter, make_classification_response, make_intent_response, make_response


def _build_app(tmp_vault: Path, router_responses: list) -> FastAPI:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    memory_mgr = MemoryManager(ops.vault_config.users_dir)

    db = loop.run_until_complete(init_database(ops.vault_config.db_path))
    run_store = AgentRunStore(db)
    task_mgr = TaskManager(db)
    store = SessionStore(db)

    agent_reg = AgentRegistry(ops.vault_config.agents_dir)
    agent_reg.load()
    composer = TeamComposer(agent_reg)

    skill_reg = SkillRegistry(ops.vault_config.vault_root / "system" / "skills")
    skill_reg.load()

    router = MockRouter(router_responses)
    interpreter = IntentInterpreter(router=router, prompt_loader=loader, memory=memory_mgr)
    orchestrator = Orchestrator(
        composer=composer,
        task_manager=task_mgr,
        agent_registry=agent_reg,
        agent_run_store=run_store,
        prompt_loader=loader,
        router=router,
        skill_registry=skill_reg,
    )

    app = FastAPI()
    app.include_router(chat_router)
    app.state.interpreter = interpreter
    app.state.hot_memory = HotMemory()
    app.state.session_store = store
    app.state.summarizer = None
    app.state.memory = memory_mgr
    app.state.orchestrator = orchestrator
    app.state.team_composer = composer
    app.state.pending_plans = {}
    app.state._test_db = db

    return app


def test_multi_agent_plan_proposed_then_confirmed(tmp_vault: Path) -> None:
    """Multi-agent task → plan_proposed → user confirms → team executes."""
    router_responses = [
        # Intent: Stage 1 (new_task) + Stage 2 (research)
        make_classification_response("new_task", 0.95),
        make_intent_response(task_type="research", objective="Research SaaS"),
        # Plan confirmation message: Stage 1 (confirmation)
        make_classification_response("confirmation", 0.99),
        # Agent 1 (researcher): plan + execute + review
        make_response("plan"), make_response("research findings"), make_response('{"quality_ok": true, "feedback": "ok"}'),
        # Agent 2 (analyst): plan + execute + review
        make_response("plan"), make_response("analysis complete"), make_response('{"quality_ok": true, "feedback": "ok"}'),
    ]
    app = _build_app(tmp_vault, router_responses)

    client = TestClient(app)
    try:
        with client.websocket_connect("/ws/sess-team") as ws:
            # Send initial task
            ws.send_json({"content": "Research SaaS competitors"})

            # Expect: thinking → plan_proposed
            thinking = ws.receive_json()
            assert thinking["type"] == "thinking"
            plan = ws.receive_json()
            assert plan["type"] == "plan_proposed"
            assert "researcher" in plan["content"].lower()

            # Send confirmation
            ws.send_json({"content": "go"})

            # Expect: agent_started → multiple agent_state → agent_completed
            events = []
            for _ in range(40):  # safety cap
                msg = ws.receive_json()
                events.append(msg)
                if msg["type"] in ("agent_completed", "error"):
                    break

            types = [e["type"] for e in events]
            assert "agent_started" in types
            assert events[-1]["type"] == "agent_completed"
            assert "analysis" in events[-1]["content"].lower()
    finally:
        asyncio.get_event_loop().run_until_complete(app.state._test_db.close())


def test_single_agent_skips_confirmation(tmp_vault: Path) -> None:
    """Single-agent task → direct execution, no plan_proposed."""
    router_responses = [
        # Intent: Stage 1 (new_task) + Stage 2 (code_review → only reviewer)
        make_classification_response("new_task", 0.95),
        make_intent_response(task_type="code_review", objective="Review code"),
        # Agent (reviewer): plan + execute + review
        make_response("plan"), make_response("review result"), make_response('{"quality_ok": true, "feedback": "ok"}'),
    ]
    app = _build_app(tmp_vault, router_responses)

    client = TestClient(app)
    try:
        with client.websocket_connect("/ws/sess-single") as ws:
            ws.send_json({"content": "Review this code"})

            # Expect: thinking → agent_started → ... → agent_completed (NO plan_proposed)
            events = []
            for _ in range(30):
                msg = ws.receive_json()
                events.append(msg)
                if msg["type"] in ("agent_completed", "error"):
                    break

            types = [e["type"] for e in events]
            assert "plan_proposed" not in types
            assert "agent_completed" in types
    finally:
        asyncio.get_event_loop().run_until_complete(app.state._test_db.close())
