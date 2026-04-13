"""Integration tests for the chat WebSocket."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from taim.api.chat import router as chat_router
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.conversation import IntentInterpreter

from conftest import MockRouter, make_classification_response, make_intent_response


@pytest.fixture
def app(tmp_vault: Path) -> FastAPI:
    import asyncio
    from taim.brain.database import init_database
    from taim.brain.hot_memory import HotMemory
    from taim.brain.memory import MemoryManager
    from taim.brain.session_store import SessionStore

    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    memory_mgr = MemoryManager(ops.vault_config.users_dir)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    db = loop.run_until_complete(init_database(ops.vault_config.db_path))
    store = SessionStore(db)

    router = MockRouter([
        make_classification_response("status_query", 0.95),
    ])
    interpreter = IntentInterpreter(router=router, prompt_loader=loader, memory=memory_mgr)

    app = FastAPI()
    app.include_router(chat_router)
    app.state.interpreter = interpreter
    app.state.hot_memory = HotMemory()
    app.state.session_store = store
    app.state.summarizer = None
    app.state.memory = memory_mgr
    return app


def test_websocket_status_query(app: FastAPI) -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws/sess-1") as ws:
        ws.send_json({"content": "status?"})
        thinking = ws.receive_json()
        assert thinking["type"] == "thinking"
        response = ws.receive_json()
        assert response["type"] == "system"
        assert "no active team" in response["content"].lower()
        assert response["category"] == "status_query"


def test_websocket_intent_response(tmp_vault: Path) -> None:
    """Verify a new_task message returns intent type and intent body."""
    import asyncio
    from taim.brain.database import init_database
    from taim.brain.hot_memory import HotMemory
    from taim.brain.memory import MemoryManager
    from taim.brain.session_store import SessionStore

    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    memory_mgr = MemoryManager(ops.vault_config.users_dir)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    db = loop.run_until_complete(init_database(ops.vault_config.db_path))
    store = SessionStore(db)

    router = MockRouter([
        make_classification_response("new_task", 0.95),
        make_intent_response("research", "Find competitors"),
    ])
    interpreter = IntentInterpreter(router=router, prompt_loader=loader, memory=memory_mgr)

    app = FastAPI()
    app.include_router(chat_router)
    app.state.interpreter = interpreter
    app.state.hot_memory = HotMemory()
    app.state.session_store = store
    app.state.summarizer = None
    app.state.memory = memory_mgr

    client = TestClient(app)
    with client.websocket_connect("/ws/sess-1") as ws:
        ws.send_json({"content": "Research SaaS competitors"})
        thinking = ws.receive_json()
        assert thinking["type"] == "thinking"
        response = ws.receive_json()
        assert response["type"] == "intent"
        assert response["category"] == "new_task"
        assert response["intent"]["task_type"] == "research"
        assert "Find competitors" in response["content"]


def test_websocket_persists_session_state(tmp_vault: Path) -> None:
    """After a message, session_state SQLite row should exist with the conversation."""
    import asyncio
    from taim.brain.database import init_database
    from taim.brain.hot_memory import HotMemory
    from taim.brain.memory import MemoryManager
    from taim.brain.session_store import SessionStore

    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    memory_mgr = MemoryManager(ops.vault_config.users_dir)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    db = loop.run_until_complete(init_database(ops.vault_config.db_path))
    try:
        store = SessionStore(db)

        router = MockRouter([
            make_classification_response("status_query", 0.95),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader, memory=memory_mgr)

        app = FastAPI()
        app.include_router(chat_router)
        app.state.interpreter = interpreter
        app.state.hot_memory = HotMemory()
        app.state.session_store = store
        app.state.summarizer = None
        app.state.memory = memory_mgr

        client = TestClient(app)
        with client.websocket_connect("/ws/sess-persist") as ws:
            ws.send_json({"content": "status?"})
            ws.receive_json()  # thinking
            ws.receive_json()  # response

        loaded = loop.run_until_complete(store.load("sess-persist"))
        assert loaded is not None
        assert len(loaded.messages) == 2  # user + assistant
        assert loaded.messages[0].role == "user"
        assert loaded.messages[0].content == "status?"
    finally:
        loop.run_until_complete(db.close())
