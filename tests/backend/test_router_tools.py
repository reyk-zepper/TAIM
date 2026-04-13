"""Tests for Router tool support."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from taim.brain.database import init_database
from taim.models.config import ProductConfig, ProviderConfig, TierConfig
from taim.models.router import LLMResponse, ModelTierEnum
from taim.router.router import LLMRouter
from taim.router.tiering import TierResolver
from taim.router.tracking import TokenTracker
from taim.router.transport import LLMTransport

from conftest import MockTransport, make_response


def _config() -> ProductConfig:
    return ProductConfig(
        providers=[
            ProviderConfig(name="primary", api_key_env="PRIMARY_KEY", models=["m1"], priority=1),
        ],
        tiering={"tier2_standard": TierConfig(description="S", models=["m1"])},
        defaults={},
    )


@pytest_asyncio.fixture
async def db(tmp_path: Path):
    conn = await init_database(tmp_path / "taim.db")
    yield conn
    await conn.close()


@pytest.mark.asyncio
class TestToolsParameter:
    async def test_tools_passed_to_transport(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k")
        transport = MockTransport([make_response("ok")])
        router = LLMRouter(
            transport=transport,
            tier_resolver=TierResolver(_config()),
            tracker=TokenTracker(db),
            product_config=_config(),
        )
        my_tools = [{"type": "function", "function": {"name": "echo"}}]
        await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
            tools=my_tools,
        )
        assert transport.calls[0]["tools"] == my_tools

    async def test_no_json_validation_when_tools(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k")
        transport = MockTransport([make_response("not json at all")])
        router = LLMRouter(
            transport=transport,
            tier_resolver=TierResolver(_config()),
            tracker=TokenTracker(db),
            product_config=_config(),
        )
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
            expected_format="json",
            tools=[{"type": "function", "function": {"name": "x"}}],
        )
        assert result.content == "not json at all"


class TestLLMResponseToolCalls:
    def test_default_empty(self) -> None:
        r = LLMResponse(
            content="x", model="m", provider="p",
            prompt_tokens=1, completion_tokens=1, cost_usd=0.0, latency_ms=10.0,
        )
        assert r.tool_calls == []


@pytest.mark.asyncio
class TestTransportToolExtraction:
    @patch("taim.router.transport.litellm")
    async def test_extracts_tool_calls(self, mock_litellm) -> None:
        mock_tool_call = MagicMock()
        mock_tool_call.id = "tc-1"
        mock_tool_call.function.name = "echo"
        mock_tool_call.function.arguments = '{"msg": "hi"}'

        mock_msg = MagicMock()
        mock_msg.content = ""
        mock_msg.tool_calls = [mock_tool_call]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_msg)]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        mock_litellm.completion_cost = MagicMock(return_value=0.001)

        transport = LLMTransport()
        result = await transport.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="m", provider="p", api_key="k",
            tools=[{"type": "function", "function": {"name": "echo"}}],
        )
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "echo"
        assert result.tool_calls[0]["id"] == "tc-1"
        assert result.tool_calls[0]["arguments"] == '{"msg": "hi"}'

    @patch("taim.router.transport.litellm")
    async def test_no_tool_calls_when_message_has_none(self, mock_litellm) -> None:
        mock_msg = MagicMock()
        mock_msg.content = "regular response"
        mock_msg.tool_calls = None

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_msg)]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        mock_litellm.completion_cost = MagicMock(return_value=0.001)

        transport = LLMTransport()
        result = await transport.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="m", provider="p", api_key="k",
        )
        assert result.tool_calls == []
        assert result.content == "regular response"
