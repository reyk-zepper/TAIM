"""Data models for the LLM Router."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ModelTierEnum(str, Enum):  # noqa: UP042
    TIER1_PREMIUM = "tier1_premium"
    TIER2_STANDARD = "tier2_standard"
    TIER3_ECONOMY = "tier3_economy"


class LLMErrorType(str, Enum):  # noqa: UP042
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    SAFETY_FILTER = "safety_filter"
    BAD_FORMAT = "bad_format"
    PROVIDER_DOWN = "provider_down"
    AUTH_ERROR = "auth_error"


class RetryAction(str, Enum):  # noqa: UP042
    RETRY_SAME = "retry_same"
    FAILOVER = "failover"
    SKIP = "skip"


class LLMResponse(BaseModel):
    content: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: float
    failover_occurred: bool = False
    attempts: int = 1


class TokenUsage(BaseModel):
    call_id: str
    agent_run_id: str | None = None
    task_id: str | None = None
    session_id: str | None = None
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
