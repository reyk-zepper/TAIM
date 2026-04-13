"""Integration test: chat WebSocket → orchestrator → agent events."""

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
    app.state._test_db = db  # Keep alive for close after test

    return app


def test_websocket_new_task_triggers_orchestrator(tmp_vault: Path) -> None:
    """Send a new_task message, expect agent_started → agent_state → agent_completed."""
    router_responses = [
        # Stage 1 classifier
        make_classification_response("new_task", 0.95),
        # Stage 2 understander
        make_intent_response(task_type="research", objective="Find SaaS competitors"),
        # Agent PLANNING
        make_response("plan"),
        # Agent EXECUTING
        make_response("final result text"),
        # Agent REVIEWING
        make_response('{"quality_ok": true, "feedback": "ok"}'),
    ]
    app = _build_app(tmp_vault, router_responses)

    client = TestClient(app)
    try:
        with client.websocket_connect("/ws/sess-orch") as ws:
            ws.send_json({"content": "Research SaaS competitors"})

            # Expect: thinking → agent_started → multiple agent_state → agent_completed
            thinking = ws.receive_json()
            assert thinking["type"] == "thinking"

            # Collect events until agent_completed or timeout
            events = []
            for _ in range(30):  # safety cap
                msg = ws.receive_json()
                events.append(msg)
                if msg["type"] in ("agent_completed", "error"):
                    break

            types = [e["type"] for e in events]
            assert "agent_started" in types
            assert "agent_state" in types
            assert events[-1]["type"] == "agent_completed"
            assert "final result text" in events[-1]["content"]
    finally:
        asyncio.get_event_loop().run_until_complete(app.state._test_db.close())
