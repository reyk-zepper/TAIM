"""Shared test fixtures for TAIM backend tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all TAIM_* env vars to prevent test pollution."""
    for key in list(os.environ.keys()):
        if key.startswith("TAIM_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


from taim.brain.vault import VaultOps


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    """Create a temporary vault with full structure and default configs."""
    vault = tmp_path / "taim-vault"
    ops = VaultOps(vault)
    ops.ensure_vault()
    return vault


from taim.models.router import LLMResponse


class MockTransport:
    """Test transport that returns canned responses or raises errors."""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def complete(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_response(content: str = "ok", **overrides) -> LLMResponse:
    defaults = {
        "content": content,
        "model": "test-model",
        "provider": "test-provider",
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "cost_usd": 0.001,
        "latency_ms": 100.0,
    }
    defaults.update(overrides)
    return LLMResponse(**defaults)


class MockRouter:
    """Test router that returns canned responses for interpreter tests."""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def make_classification_response(category: str, confidence: float = 0.95, needs_deep: bool = False) -> LLMResponse:
    """Build an LLMResponse with a JSON classification body."""
    import json
    body = json.dumps({
        "category": category,
        "confidence": confidence,
        "needs_deep_analysis": needs_deep,
    })
    return make_response(content=body)


def make_intent_response(
    task_type: str = "research",
    objective: str = "Find competitors",
    missing_info: list[str] | None = None,
) -> LLMResponse:
    """Build an LLMResponse with a JSON intent body."""
    import json
    body = json.dumps({
        "task_type": task_type,
        "objective": objective,
        "parameters": {},
        "constraints": {"time_limit_seconds": None, "budget_eur": None},
        "missing_info": missing_info or [],
        "suggested_team": [],
    })
    return make_response(content=body)
