"""Tests for LLMTransport — litellm wrapper with error mapping."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from taim.errors import LLMTransportError
from taim.models.router import LLMErrorType
from taim.router.transport import LLMTransport


def _mock_response(content: str = "hello", prompt_tokens: int = 10, completion_tokens: int = 5):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    return response


@pytest.mark.asyncio
class TestComplete:
    @patch("taim.router.transport.litellm")
    async def test_returns_llm_response(self, mock_litellm) -> None:
        mock_litellm.acompletion = AsyncMock(return_value=_mock_response("world"))
        mock_litellm.completion_cost = MagicMock(return_value=0.001)
        transport = LLMTransport()
        result = await transport.complete(messages=[{"role": "user", "content": "hi"}], model="claude-haiku", provider="anthropic", api_key="test-key")
        assert result.content == "world"
        assert result.provider == "anthropic"
        assert result.cost_usd == 0.001

    @patch("taim.router.transport.litellm")
    async def test_passes_provider_model_format(self, mock_litellm) -> None:
        mock_litellm.acompletion = AsyncMock(return_value=_mock_response())
        mock_litellm.completion_cost = MagicMock(return_value=0.0)
        transport = LLMTransport()
        await transport.complete(messages=[{"role": "user", "content": "hi"}], model="claude-haiku", provider="anthropic", api_key="key")
        call_kwargs = mock_litellm.acompletion.call_args[1]
        assert call_kwargs["model"] == "anthropic/claude-haiku"
        assert call_kwargs["num_retries"] == 0

    @patch("taim.router.transport.litellm")
    async def test_ollama_uses_api_base(self, mock_litellm) -> None:
        mock_litellm.acompletion = AsyncMock(return_value=_mock_response())
        mock_litellm.completion_cost = MagicMock(return_value=0.0)
        transport = LLMTransport()
        await transport.complete(messages=[{"role": "user", "content": "hi"}], model="qwen", provider="ollama", api_base="http://localhost:11434")
        assert mock_litellm.acompletion.call_args[1]["api_base"] == "http://localhost:11434"

    @patch("taim.router.transport.litellm")
    async def test_cost_fallback_zero(self, mock_litellm) -> None:
        mock_litellm.acompletion = AsyncMock(return_value=_mock_response())
        mock_litellm.completion_cost = MagicMock(side_effect=Exception("unknown"))
        transport = LLMTransport()
        result = await transport.complete(messages=[{"role": "user", "content": "hi"}], model="local", provider="ollama")
        assert result.cost_usd == 0.0


@pytest.mark.asyncio
class TestErrorMapping:
    @patch("taim.router.transport.litellm")
    async def test_rate_limit(self, mock_litellm) -> None:
        mock_litellm.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_litellm.acompletion = AsyncMock(side_effect=mock_litellm.RateLimitError("429"))
        # Need to ensure the except clause can catch it — the transport imports litellm at module level
        # so we need to also patch the exception classes on the mock
        mock_litellm.Timeout = type("Timeout", (Exception,), {})
        mock_litellm.ContentPolicyViolationError = type("CPV", (Exception,), {})
        mock_litellm.AuthenticationError = type("AE", (Exception,), {})
        mock_litellm.APIConnectionError = type("ACE", (Exception,), {})
        mock_litellm.APIError = type("APIE", (Exception,), {})

        transport = LLMTransport()
        with pytest.raises(LLMTransportError) as exc_info:
            await transport.complete(messages=[{"role": "user", "content": "hi"}], model="m", provider="p", api_key="k")
        assert exc_info.value.error_type == LLMErrorType.RATE_LIMIT

    @patch("taim.router.transport.litellm")
    async def test_auth_error(self, mock_litellm) -> None:
        mock_litellm.RateLimitError = type("RLE", (Exception,), {})
        mock_litellm.Timeout = type("T", (Exception,), {})
        mock_litellm.ContentPolicyViolationError = type("CPV", (Exception,), {})
        mock_litellm.AuthenticationError = type("AE", (Exception,), {})
        mock_litellm.APIConnectionError = type("ACE", (Exception,), {})
        mock_litellm.APIError = type("APIE", (Exception,), {})
        mock_litellm.acompletion = AsyncMock(side_effect=mock_litellm.AuthenticationError("401"))

        transport = LLMTransport()
        with pytest.raises(LLMTransportError) as exc_info:
            await transport.complete(messages=[{"role": "user", "content": "hi"}], model="m", provider="p", api_key="k")
        assert exc_info.value.error_type == LLMErrorType.AUTH_ERROR

    @patch("taim.router.transport.litellm")
    async def test_connection_error(self, mock_litellm) -> None:
        mock_litellm.RateLimitError = type("RLE", (Exception,), {})
        mock_litellm.Timeout = type("T", (Exception,), {})
        mock_litellm.ContentPolicyViolationError = type("CPV", (Exception,), {})
        mock_litellm.AuthenticationError = type("AE", (Exception,), {})
        mock_litellm.APIConnectionError = type("ACE", (Exception,), {})
        mock_litellm.APIError = type("APIE", (Exception,), {})
        mock_litellm.acompletion = AsyncMock(side_effect=mock_litellm.APIConnectionError("refused"))

        transport = LLMTransport()
        with pytest.raises(LLMTransportError) as exc_info:
            await transport.complete(messages=[{"role": "user", "content": "hi"}], model="m", provider="p", api_key="k")
        assert exc_info.value.error_type == LLMErrorType.PROVIDER_DOWN
