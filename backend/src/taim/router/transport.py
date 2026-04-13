"""LLMTransport — wraps a single litellm.acompletion() call."""

from __future__ import annotations

import time

import litellm

from taim.errors import LLMTransportError
from taim.models.router import LLMErrorType, LLMResponse


class LLMTransport:
    """Makes a single LLM API call via litellm and returns a normalized response."""

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        provider: str,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: float = 30.0,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Make one LLM call. Returns LLMResponse or raises LLMTransportError."""
        litellm_model = f"{provider}/{model}"
        start = time.monotonic()

        kwargs: dict = {
            "model": litellm_model,
            "messages": messages,
            "num_retries": 0,
            "timeout": timeout,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await litellm.acompletion(**kwargs)
        except litellm.RateLimitError as e:
            raise LLMTransportError(LLMErrorType.RATE_LIMIT, str(e)) from e
        except litellm.Timeout as e:
            raise LLMTransportError(LLMErrorType.TIMEOUT, str(e)) from e
        except litellm.ContentPolicyViolationError as e:
            raise LLMTransportError(LLMErrorType.SAFETY_FILTER, str(e)) from e
        except litellm.AuthenticationError as e:
            raise LLMTransportError(LLMErrorType.AUTH_ERROR, str(e)) from e
        except litellm.APIConnectionError as e:
            raise LLMTransportError(LLMErrorType.PROVIDER_DOWN, str(e)) from e
        except litellm.APIError as e:
            raise LLMTransportError(LLMErrorType.PROVIDER_DOWN, str(e)) from e

        elapsed_ms = (time.monotonic() - start) * 1000
        usage = response.usage
        msg = response.choices[0].message

        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = 0.0

        tool_calls_raw: list[dict] = []
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_raw.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })

        return LLMResponse(
            content=msg.content or "",
            model=model,
            provider=provider,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=cost,
            latency_ms=elapsed_ms,
            tool_calls=tool_calls_raw,
        )
