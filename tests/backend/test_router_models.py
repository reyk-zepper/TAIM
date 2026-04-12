"""Tests for LLM Router data models."""

from taim.models.router import (
    LLMErrorType, LLMResponse, ModelTierEnum, RetryAction, TokenUsage,
)


class TestModelTierEnum:
    def test_values(self) -> None:
        assert ModelTierEnum.TIER1_PREMIUM == "tier1_premium"
        assert ModelTierEnum.TIER2_STANDARD == "tier2_standard"
        assert ModelTierEnum.TIER3_ECONOMY == "tier3_economy"


class TestLLMErrorType:
    def test_all_types_exist(self) -> None:
        assert LLMErrorType.RATE_LIMIT == "rate_limit"
        assert LLMErrorType.AUTH_ERROR == "auth_error"


class TestRetryAction:
    def test_values(self) -> None:
        assert RetryAction.RETRY_SAME == "retry_same"
        assert RetryAction.FAILOVER == "failover"
        assert RetryAction.SKIP == "skip"


class TestLLMResponse:
    def test_defaults(self) -> None:
        r = LLMResponse(content="hello", model="m", provider="p", prompt_tokens=10, completion_tokens=5, cost_usd=0.001, latency_ms=200.0)
        assert r.failover_occurred is False
        assert r.attempts == 1


class TestTokenUsage:
    def test_minimal(self) -> None:
        t = TokenUsage(call_id="c1", model="m", provider="p", prompt_tokens=100, completion_tokens=50, cost_usd=0.01)
        assert t.agent_run_id is None
