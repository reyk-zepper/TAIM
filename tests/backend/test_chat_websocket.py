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
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)

    router = MockRouter([
        make_classification_response("status_query", 0.95),
    ])
    interpreter = IntentInterpreter(router=router, prompt_loader=loader)

    app = FastAPI()
    app.include_router(chat_router)
    app.state.interpreter = interpreter
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
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    router = MockRouter([
        make_classification_response("new_task", 0.95),
        make_intent_response("research", "Find competitors"),
    ])
    interpreter = IntentInterpreter(router=router, prompt_loader=loader)

    app = FastAPI()
    app.include_router(chat_router)
    app.state.interpreter = interpreter

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
