# Step 2: LLM Router — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the LLM Router — provider selection, model tiering, error-type-aware failover, per-call token tracking.

**Architecture:** LLMTransport wraps litellm calls, LLMRouter orchestrates with failover (max 3 attempts), TierResolver maps tiers to models, TokenTracker logs to SQLite. Design: `docs/plans/2026-04-12-step2-llm-router-design.md`.

**Tech Stack:** Python 3.11+, LiteLLM, aiosqlite, Pydantic v2, pytest

---

## File Structure

### Files to Create

```
backend/src/taim/models/router.py         # LLMResponse, ModelTierEnum, LLMErrorType, TokenUsage
backend/src/taim/router/transport.py       # LLMTransport
backend/src/taim/router/tiering.py         # TierResolver
backend/src/taim/router/failover.py        # ErrorClassifier, RetryDecision, message modifiers
backend/src/taim/router/tracking.py        # TokenTracker
backend/src/taim/router/router.py          # LLMRouter
tests/backend/test_router_models.py        # Model tests
tests/backend/test_transport.py            # Transport tests (mocked litellm)
tests/backend/test_tiering.py              # TierResolver tests
tests/backend/test_failover.py             # ErrorClassifier tests
tests/backend/test_tracking.py             # TokenTracker tests
tests/backend/test_router.py               # LLMRouter integration tests
```

### Files to Modify

```
backend/src/taim/errors.py                 # Add LLMTransportError, AllProvidersFailed
backend/src/taim/main.py                   # Add Router to lifespan + DI
backend/src/taim/api/deps.py               # Add get_router()
tests/backend/conftest.py                  # Add mock_transport, router fixtures
```

---

## Task 1: Router Data Models

**Files:**
- Create: `backend/src/taim/models/router.py`
- Create: `tests/backend/test_router_models.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/backend/test_router_models.py`
```python
"""Tests for LLM Router data models."""

from taim.models.router import (
    LLMErrorType,
    LLMResponse,
    ModelTierEnum,
    RetryAction,
    TokenUsage,
)


class TestModelTierEnum:
    def test_values(self) -> None:
        assert ModelTierEnum.TIER1_PREMIUM == "tier1_premium"
        assert ModelTierEnum.TIER2_STANDARD == "tier2_standard"
        assert ModelTierEnum.TIER3_ECONOMY == "tier3_economy"


class TestLLMErrorType:
    def test_all_types_exist(self) -> None:
        assert LLMErrorType.RATE_LIMIT == "rate_limit"
        assert LLMErrorType.TIMEOUT == "timeout"
        assert LLMErrorType.SAFETY_FILTER == "safety_filter"
        assert LLMErrorType.BAD_FORMAT == "bad_format"
        assert LLMErrorType.PROVIDER_DOWN == "provider_down"
        assert LLMErrorType.AUTH_ERROR == "auth_error"


class TestRetryAction:
    def test_values(self) -> None:
        assert RetryAction.RETRY_SAME == "retry_same"
        assert RetryAction.FAILOVER == "failover"
        assert RetryAction.SKIP == "skip"


class TestLLMResponse:
    def test_defaults(self) -> None:
        r = LLMResponse(
            content="hello",
            model="claude-haiku",
            provider="anthropic",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.001,
            latency_ms=200.0,
        )
        assert r.failover_occurred is False
        assert r.attempts == 1

    def test_with_failover(self) -> None:
        r = LLMResponse(
            content="hello",
            model="gpt-4o-mini",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.002,
            latency_ms=300.0,
            failover_occurred=True,
            attempts=2,
        )
        assert r.failover_occurred is True
        assert r.attempts == 2


class TestTokenUsage:
    def test_minimal(self) -> None:
        t = TokenUsage(
            call_id="call-1",
            model="claude-haiku",
            provider="anthropic",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.01,
        )
        assert t.agent_run_id is None
        assert t.task_id is None
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd /Users/reykz/repositorys/TAIM/backend && uv run pytest ../tests/backend/test_router_models.py -v`

- [ ] **Step 3: Implement models/router.py**

File: `backend/src/taim/models/router.py`
```python
"""Data models for the LLM Router."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ModelTierEnum(str, Enum):
    """LLM model tiers by capability and cost."""

    TIER1_PREMIUM = "tier1_premium"
    TIER2_STANDARD = "tier2_standard"
    TIER3_ECONOMY = "tier3_economy"


class LLMErrorType(str, Enum):
    """Classified LLM error types for failover decisions."""

    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    SAFETY_FILTER = "safety_filter"
    BAD_FORMAT = "bad_format"
    PROVIDER_DOWN = "provider_down"
    AUTH_ERROR = "auth_error"


class RetryAction(str, Enum):
    """Action to take after an LLM error."""

    RETRY_SAME = "retry_same"
    FAILOVER = "failover"
    SKIP = "skip"


class LLMResponse(BaseModel):
    """Normalized response from any LLM provider."""

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
    """Per-call token tracking record for SQLite."""

    call_id: str
    agent_run_id: str | None = None
    task_id: str | None = None
    session_id: str | None = None
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd /Users/reykz/repositorys/TAIM/backend && uv run pytest ../tests/backend/test_router_models.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/models/router.py tests/backend/test_router_models.py
git commit -m "feat: add LLM Router data models (tiers, errors, response, usage)"
```

---

## Task 2: Error Types for Router

**Files:**
- Modify: `backend/src/taim/errors.py`
- Modify: `tests/backend/test_errors.py`

- [ ] **Step 1: Write new tests**

Append to `tests/backend/test_errors.py`:
```python
from taim.models.router import LLMErrorType


class TestLLMTransportError:
    def test_has_error_type(self) -> None:
        from taim.errors import LLMTransportError
        err = LLMTransportError(LLMErrorType.RATE_LIMIT, "rate limited")
        assert err.error_type == LLMErrorType.RATE_LIMIT
        assert isinstance(err, TaimError)
        assert "busy" in err.user_message.lower() or "retrying" in err.user_message.lower()

    def test_auth_error_message(self) -> None:
        from taim.errors import LLMTransportError
        err = LLMTransportError(LLMErrorType.AUTH_ERROR, "401 Unauthorized")
        assert "api key" in err.user_message.lower() or "invalid" in err.user_message.lower()


class TestAllProvidersFailed:
    def test_is_taim_error(self) -> None:
        from taim.errors import AllProvidersFailed
        err = AllProvidersFailed(
            user_message="All AI services failed.",
            detail="3 attempts exhausted",
        )
        assert isinstance(err, TaimError)
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd /Users/reykz/repositorys/TAIM/backend && uv run pytest ../tests/backend/test_errors.py -v`

- [ ] **Step 3: Add error classes to errors.py**

Append to `backend/src/taim/errors.py`:
```python
from taim.models.router import LLMErrorType

_LLM_USER_MESSAGES = {
    LLMErrorType.RATE_LIMIT: "The AI service is temporarily busy. Retrying...",
    LLMErrorType.TIMEOUT: "The AI service is responding slowly. Trying alternatives...",
    LLMErrorType.SAFETY_FILTER: "The response was filtered by the AI service's safety system.",
    LLMErrorType.PROVIDER_DOWN: "The AI service is currently unavailable.",
    LLMErrorType.AUTH_ERROR: "The API key for this AI service appears invalid. Please check your configuration.",
    LLMErrorType.BAD_FORMAT: "The AI response wasn't in the expected format. Retrying...",
}


class LLMTransportError(TaimError):
    """Error from a single LLM transport call."""

    def __init__(self, error_type: LLMErrorType, detail: str) -> None:
        self.error_type = error_type
        super().__init__(
            user_message=_LLM_USER_MESSAGES.get(error_type, "An LLM error occurred."),
            detail=detail,
        )


class AllProvidersFailed(TaimError):
    """All LLM providers failed after maximum retry attempts."""
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd /Users/reykz/repositorys/TAIM/backend && uv run pytest ../tests/backend/test_errors.py -v`
Expected: `12 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/errors.py tests/backend/test_errors.py
git commit -m "feat: add LLMTransportError and AllProvidersFailed error types"
```

---

## Task 3: TierResolver

**Files:**
- Create: `backend/src/taim/router/tiering.py`
- Create: `tests/backend/test_tiering.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/backend/test_tiering.py`
```python
"""Tests for TierResolver — maps tier to provider/model candidates."""

from taim.models.config import ProductConfig, ProviderConfig, TierConfig
from taim.models.router import ModelTierEnum
from taim.router.tiering import TierResolver


def _make_config() -> ProductConfig:
    return ProductConfig(
        providers=[
            ProviderConfig(name="anthropic", models=["claude-sonnet-4", "claude-haiku-4-5"], priority=1),
            ProviderConfig(name="openai", models=["gpt-4o", "gpt-4o-mini"], priority=2),
            ProviderConfig(name="ollama", models=["qwen2.5:32b"], priority=3),
        ],
        tiering={
            "tier1_premium": TierConfig(description="Complex", models=["claude-sonnet-4", "gpt-4o"]),
            "tier2_standard": TierConfig(description="Standard", models=["claude-haiku-4-5", "gpt-4o-mini"]),
            "tier3_economy": TierConfig(description="Cheap", models=["gpt-4o-mini", "qwen2.5:32b"]),
        },
        defaults={},
    )


class TestResolve:
    def test_tier1_returns_premium_models(self) -> None:
        resolver = TierResolver(_make_config())
        candidates = resolver.resolve(ModelTierEnum.TIER1_PREMIUM)
        assert candidates[0] == ("anthropic", "claude-sonnet-4")
        assert candidates[1] == ("openai", "gpt-4o")

    def test_tier3_returns_economy_models(self) -> None:
        resolver = TierResolver(_make_config())
        candidates = resolver.resolve(ModelTierEnum.TIER3_ECONOMY)
        providers = [c[0] for c in candidates]
        assert "openai" in providers
        assert "ollama" in providers

    def test_sorted_by_provider_priority(self) -> None:
        resolver = TierResolver(_make_config())
        candidates = resolver.resolve(ModelTierEnum.TIER2_STANDARD)
        assert candidates[0][0] == "anthropic"  # priority 1
        assert candidates[1][0] == "openai"     # priority 2

    def test_empty_tier_returns_empty(self) -> None:
        config = ProductConfig(providers=[], tiering={}, defaults={})
        resolver = TierResolver(config)
        assert resolver.resolve(ModelTierEnum.TIER1_PREMIUM) == []

    def test_unknown_tier_returns_empty(self) -> None:
        resolver = TierResolver(_make_config())
        # Tier exists in enum but has no config
        config = ProductConfig(providers=[], tiering={}, defaults={})
        resolver2 = TierResolver(config)
        assert resolver2.resolve(ModelTierEnum.TIER1_PREMIUM) == []
```

- [ ] **Step 2: Run tests — expect FAIL**
- [ ] **Step 3: Implement tiering.py**

File: `backend/src/taim/router/tiering.py`
```python
"""TierResolver — maps ModelTierEnum to (provider, model) candidates."""

from __future__ import annotations

from taim.models.config import ProductConfig
from taim.models.router import ModelTierEnum


class TierResolver:
    """Maps a tier to an ordered list of (provider_name, model_name) candidates."""

    def __init__(self, product_config: ProductConfig) -> None:
        self._providers = sorted(product_config.providers, key=lambda p: p.priority)
        self._tiering = product_config.tiering

    def resolve(self, tier: ModelTierEnum) -> list[tuple[str, str]]:
        """Return (provider, model) pairs for the tier, sorted by provider priority."""
        tier_config = self._tiering.get(tier.value)
        if not tier_config:
            return []

        tier_models = set(tier_config.models)
        candidates: list[tuple[str, str]] = []

        for provider in self._providers:
            for model in provider.models:
                if model in tier_models:
                    candidates.append((provider.name, model))

        return candidates
```

- [ ] **Step 4: Run tests — expect PASS** (5 passed)
- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/router/tiering.py tests/backend/test_tiering.py
git commit -m "feat: add TierResolver for model tier to provider/model mapping"
```

---

## Task 4: ErrorClassifier & Failover Strategy

**Files:**
- Create: `backend/src/taim/router/failover.py`
- Create: `tests/backend/test_failover.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/backend/test_failover.py`
```python
"""Tests for ErrorClassifier and message modifiers."""

from taim.errors import LLMTransportError
from taim.models.router import LLMErrorType, RetryAction
from taim.router.failover import classify_error, _soften_messages, _add_format_reminder


class TestClassifyError:
    def test_rate_limit_retries_same(self) -> None:
        err = LLMTransportError(LLMErrorType.RATE_LIMIT, "429")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.RETRY_SAME
        assert decision.backoff_seconds > 0

    def test_rate_limit_backoff_increases(self) -> None:
        err = LLMTransportError(LLMErrorType.RATE_LIMIT, "429")
        d1 = classify_error(err, attempt_number=0, same_provider_attempts=1)
        d2 = classify_error(err, attempt_number=1, same_provider_attempts=2)
        assert d2.backoff_seconds > d1.backoff_seconds

    def test_timeout_first_retries_same(self) -> None:
        err = LLMTransportError(LLMErrorType.TIMEOUT, "timeout")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.RETRY_SAME

    def test_timeout_second_failover(self) -> None:
        err = LLMTransportError(LLMErrorType.TIMEOUT, "timeout")
        decision = classify_error(err, attempt_number=1, same_provider_attempts=2)
        assert decision.action == RetryAction.FAILOVER

    def test_safety_filter_first_softens(self) -> None:
        err = LLMTransportError(LLMErrorType.SAFETY_FILTER, "blocked")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.RETRY_SAME
        assert decision.modify_messages is not None

    def test_safety_filter_second_failover(self) -> None:
        err = LLMTransportError(LLMErrorType.SAFETY_FILTER, "blocked")
        decision = classify_error(err, attempt_number=1, same_provider_attempts=2)
        assert decision.action == RetryAction.FAILOVER

    def test_bad_format_first_adds_reminder(self) -> None:
        err = LLMTransportError(LLMErrorType.BAD_FORMAT, "not json")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.RETRY_SAME
        assert decision.modify_messages is not None

    def test_provider_down_immediate_failover(self) -> None:
        err = LLMTransportError(LLMErrorType.PROVIDER_DOWN, "connection refused")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.FAILOVER

    def test_auth_error_skips(self) -> None:
        err = LLMTransportError(LLMErrorType.AUTH_ERROR, "401")
        decision = classify_error(err, attempt_number=0, same_provider_attempts=1)
        assert decision.action == RetryAction.SKIP


class TestMessageModifiers:
    def test_soften_prepends_system_message(self) -> None:
        original = [{"role": "user", "content": "hello"}]
        softened = _soften_messages(original)
        assert len(softened) == 2
        assert softened[0]["role"] == "system"
        assert original == [{"role": "user", "content": "hello"}]  # Not mutated

    def test_format_reminder_appends(self) -> None:
        original = [{"role": "user", "content": "classify"}]
        reminded = _add_format_reminder(original)
        assert len(reminded) == 2
        assert reminded[-1]["role"] == "system"
        assert "json" in reminded[-1]["content"].lower()
        assert original == [{"role": "user", "content": "classify"}]  # Not mutated
```

- [ ] **Step 2: Run tests — expect FAIL**
- [ ] **Step 3: Implement failover.py**

File: `backend/src/taim/router/failover.py`
```python
"""Error classification and retry strategy for LLM failover."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from taim.errors import LLMTransportError
from taim.models.router import LLMErrorType, RetryAction


@dataclass
class RetryDecision:
    """What to do after an LLM transport error."""

    action: RetryAction
    backoff_seconds: float = 0.0
    modify_messages: Callable[[list[dict]], list[dict]] | None = None


def classify_error(
    error: LLMTransportError,
    attempt_number: int,
    same_provider_attempts: int,
) -> RetryDecision:
    """Decide retry action based on error type and attempt history."""
    match error.error_type:
        case LLMErrorType.RATE_LIMIT:
            backoff = min(2 ** (same_provider_attempts - 1), 4.0)
            return RetryDecision(action=RetryAction.RETRY_SAME, backoff_seconds=backoff)

        case LLMErrorType.TIMEOUT:
            if same_provider_attempts < 2:
                return RetryDecision(action=RetryAction.RETRY_SAME)
            return RetryDecision(action=RetryAction.FAILOVER)

        case LLMErrorType.SAFETY_FILTER:
            if same_provider_attempts < 2:
                return RetryDecision(
                    action=RetryAction.RETRY_SAME,
                    modify_messages=_soften_messages,
                )
            return RetryDecision(action=RetryAction.FAILOVER)

        case LLMErrorType.BAD_FORMAT:
            if same_provider_attempts < 2:
                return RetryDecision(
                    action=RetryAction.RETRY_SAME,
                    modify_messages=_add_format_reminder,
                )
            return RetryDecision(action=RetryAction.FAILOVER)

        case LLMErrorType.PROVIDER_DOWN:
            return RetryDecision(action=RetryAction.FAILOVER)

        case LLMErrorType.AUTH_ERROR:
            return RetryDecision(action=RetryAction.SKIP)

    return RetryDecision(action=RetryAction.FAILOVER)


def _soften_messages(messages: list[dict]) -> list[dict]:
    """Prepend a safety-conscious system instruction. Does not mutate original."""
    return [
        {
            "role": "system",
            "content": (
                "Please provide a helpful response within content guidelines. "
                "Avoid controversial or sensitive content."
            ),
        },
        *messages,
    ]


def _add_format_reminder(messages: list[dict]) -> list[dict]:
    """Append a JSON format instruction. Does not mutate original."""
    return [
        *messages,
        {
            "role": "system",
            "content": "IMPORTANT: Respond with valid JSON only. No markdown, no explanation, just the JSON object.",
        },
    ]
```

- [ ] **Step 4: Run tests — expect PASS** (11 passed)
- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/router/failover.py tests/backend/test_failover.py
git commit -m "feat: add error-type-aware failover strategy with message modifiers"
```

---

## Task 5: TokenTracker

**Files:**
- Create: `backend/src/taim/router/tracking.py`
- Create: `tests/backend/test_tracking.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/backend/test_tracking.py`
```python
"""Tests for TokenTracker — per-call SQLite logging."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.database import init_database
from taim.models.router import TokenUsage
from taim.router.tracking import TokenTracker


@pytest.fixture
async def tracker(tmp_path: Path):
    db = await init_database(tmp_path / "taim.db")
    t = TokenTracker(db)
    yield t
    await db.close()


@pytest.mark.asyncio
class TestRecord:
    async def test_inserts_row(self, tracker: TokenTracker) -> None:
        usage = TokenUsage(
            call_id="call-1",
            model="claude-haiku",
            provider="anthropic",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.01,
        )
        await tracker.record(usage)
        # Verify via direct query
        async with tracker._db.execute("SELECT COUNT(*) FROM token_tracking") as cur:
            row = await cur.fetchone()
            assert row[0] == 1

    async def test_records_all_fields(self, tracker: TokenTracker) -> None:
        usage = TokenUsage(
            call_id="call-2",
            agent_run_id="run-1",
            task_id="task-1",
            session_id="sess-1",
            model="gpt-4o-mini",
            provider="openai",
            prompt_tokens=200,
            completion_tokens=100,
            cost_usd=0.05,
        )
        await tracker.record(usage)
        async with tracker._db.execute(
            "SELECT model, provider, prompt_tokens, cost_usd FROM token_tracking WHERE call_id = ?",
            ("call-2",),
        ) as cur:
            row = await cur.fetchone()
            assert row == ("gpt-4o-mini", "openai", 200, 0.05)


@pytest.mark.asyncio
class TestGetMonthlyCost:
    async def test_returns_zero_for_no_records(self, tracker: TokenTracker) -> None:
        cost = await tracker.get_monthly_cost("anthropic")
        assert cost == 0.0

    async def test_sums_costs_for_provider(self, tracker: TokenTracker) -> None:
        for i in range(3):
            await tracker.record(TokenUsage(
                call_id=f"call-{i}",
                model="claude-haiku",
                provider="anthropic",
                prompt_tokens=100,
                completion_tokens=50,
                cost_usd=0.10,
            ))
        cost = await tracker.get_monthly_cost("anthropic")
        assert abs(cost - 0.30) < 0.001

    async def test_filters_by_provider(self, tracker: TokenTracker) -> None:
        await tracker.record(TokenUsage(
            call_id="call-a", model="claude", provider="anthropic",
            prompt_tokens=100, completion_tokens=50, cost_usd=0.10,
        ))
        await tracker.record(TokenUsage(
            call_id="call-o", model="gpt", provider="openai",
            prompt_tokens=100, completion_tokens=50, cost_usd=0.20,
        ))
        assert abs(await tracker.get_monthly_cost("anthropic") - 0.10) < 0.001
        assert abs(await tracker.get_monthly_cost("openai") - 0.20) < 0.001
```

- [ ] **Step 2: Run tests — expect FAIL**
- [ ] **Step 3: Implement tracking.py**

File: `backend/src/taim/router/tracking.py`
```python
"""TokenTracker — per-call token logging to SQLite."""

from __future__ import annotations

import aiosqlite

from taim.models.router import TokenUsage


class TokenTracker:
    """Logs every LLM call to the token_tracking table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def record(self, usage: TokenUsage) -> None:
        """Insert a token tracking row."""
        await self._db.execute(
            """INSERT INTO token_tracking
               (call_id, agent_run_id, task_id, session_id, model, provider,
                prompt_tokens, completion_tokens, cost_usd)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                usage.call_id,
                usage.agent_run_id,
                usage.task_id,
                usage.session_id,
                usage.model,
                usage.provider,
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.cost_usd,
            ),
        )
        await self._db.commit()

    async def get_monthly_cost(self, provider: str) -> float:
        """Sum cost_usd for current calendar month for a provider."""
        async with self._db.execute(
            """SELECT COALESCE(SUM(cost_usd), 0.0) FROM token_tracking
               WHERE provider = ? AND created_at >= date('now', 'start of month')""",
            (provider,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0.0
```

- [ ] **Step 4: Run tests — expect PASS** (5 passed)
- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/router/tracking.py tests/backend/test_tracking.py
git commit -m "feat: add TokenTracker for per-call SQLite logging"
```

---

## Task 6: LLMTransport

**Files:**
- Create: `backend/src/taim/router/transport.py`
- Create: `tests/backend/test_transport.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/backend/test_transport.py`
```python
"""Tests for LLMTransport — litellm call wrapper with error mapping."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from taim.errors import LLMTransportError
from taim.models.router import LLMErrorType
from taim.router.transport import LLMTransport


def _mock_response(content: str = "hello", prompt_tokens: int = 10, completion_tokens: int = 5):
    """Create a mock litellm response."""
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
        result = await transport.complete(
            messages=[{"role": "user", "content": "hello"}],
            model="claude-haiku-4-5",
            provider="anthropic",
            api_key="test-key",
        )
        assert result.content == "world"
        assert result.provider == "anthropic"
        assert result.model == "claude-haiku-4-5"
        assert result.prompt_tokens == 10
        assert result.cost_usd == 0.001

    @patch("taim.router.transport.litellm")
    async def test_passes_correct_model_format(self, mock_litellm) -> None:
        mock_litellm.acompletion = AsyncMock(return_value=_mock_response())
        mock_litellm.completion_cost = MagicMock(return_value=0.0)

        transport = LLMTransport()
        await transport.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="claude-haiku-4-5",
            provider="anthropic",
            api_key="key",
        )
        call_kwargs = mock_litellm.acompletion.call_args[1]
        assert call_kwargs["model"] == "anthropic/claude-haiku-4-5"
        assert call_kwargs["num_retries"] == 0

    @patch("taim.router.transport.litellm")
    async def test_ollama_uses_api_base(self, mock_litellm) -> None:
        mock_litellm.acompletion = AsyncMock(return_value=_mock_response())
        mock_litellm.completion_cost = MagicMock(return_value=0.0)

        transport = LLMTransport()
        await transport.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="qwen2.5:32b",
            provider="ollama",
            api_base="http://localhost:11434",
        )
        call_kwargs = mock_litellm.acompletion.call_args[1]
        assert call_kwargs["api_base"] == "http://localhost:11434"


@pytest.mark.asyncio
class TestErrorMapping:
    @patch("taim.router.transport.litellm")
    async def test_rate_limit(self, mock_litellm) -> None:
        mock_litellm.acompletion = AsyncMock(side_effect=Exception("rate limit"))
        mock_litellm.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_litellm.acompletion.side_effect = mock_litellm.RateLimitError("429")

        transport = LLMTransport()
        with pytest.raises(LLMTransportError) as exc_info:
            await transport.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="m", provider="p", api_key="k",
            )
        assert exc_info.value.error_type == LLMErrorType.RATE_LIMIT

    @patch("taim.router.transport.litellm")
    async def test_auth_error(self, mock_litellm) -> None:
        mock_litellm.acompletion = AsyncMock()
        mock_litellm.AuthenticationError = type("AuthenticationError", (Exception,), {})
        mock_litellm.acompletion.side_effect = mock_litellm.AuthenticationError("401")

        transport = LLMTransport()
        with pytest.raises(LLMTransportError) as exc_info:
            await transport.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="m", provider="p", api_key="k",
            )
        assert exc_info.value.error_type == LLMErrorType.AUTH_ERROR

    @patch("taim.router.transport.litellm")
    async def test_connection_error(self, mock_litellm) -> None:
        mock_litellm.acompletion = AsyncMock()
        mock_litellm.APIConnectionError = type("APIConnectionError", (Exception,), {"__init__": lambda self, *a, **kw: None})
        mock_litellm.acompletion.side_effect = mock_litellm.APIConnectionError("refused")

        transport = LLMTransport()
        with pytest.raises(LLMTransportError) as exc_info:
            await transport.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="m", provider="p", api_key="k",
            )
        assert exc_info.value.error_type == LLMErrorType.PROVIDER_DOWN

    @patch("taim.router.transport.litellm")
    async def test_cost_fallback_zero(self, mock_litellm) -> None:
        mock_litellm.acompletion = AsyncMock(return_value=_mock_response())
        mock_litellm.completion_cost = MagicMock(side_effect=Exception("unknown model"))

        transport = LLMTransport()
        result = await transport.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="local-model", provider="ollama",
        )
        assert result.cost_usd == 0.0
```

- [ ] **Step 2: Run tests — expect FAIL**
- [ ] **Step 3: Implement transport.py**

File: `backend/src/taim/router/transport.py`
```python
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

        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = 0.0

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=model,
            provider=provider,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=cost,
            latency_ms=elapsed_ms,
        )
```

- [ ] **Step 4: Run tests — expect PASS** (7 passed)
- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/router/transport.py tests/backend/test_transport.py
git commit -m "feat: add LLMTransport with litellm error mapping and cost tracking"
```

---

## Task 7: LLMRouter (Core)

**Files:**
- Create: `backend/src/taim/router/router.py`
- Create: `tests/backend/test_router.py`
- Modify: `tests/backend/conftest.py` (add mock fixtures)

- [ ] **Step 1: Add mock fixtures to conftest.py**

Append to `tests/backend/conftest.py`:
```python
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
```

- [ ] **Step 2: Write the failing tests**

File: `tests/backend/test_router.py`
```python
"""Tests for LLMRouter — orchestrates calls with failover."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.database import init_database
from taim.errors import AllProvidersFailed, ConfigError, LLMTransportError
from taim.models.config import ProductConfig, ProviderConfig, TierConfig
from taim.models.router import LLMErrorType, ModelTierEnum
from taim.router.router import LLMRouter
from taim.router.tiering import TierResolver
from taim.router.tracking import TokenTracker

from conftest import MockTransport, make_response


def _config() -> ProductConfig:
    return ProductConfig(
        providers=[
            ProviderConfig(name="primary", api_key_env="PRIMARY_KEY", models=["model-a"], priority=1),
            ProviderConfig(name="secondary", api_key_env="SECONDARY_KEY", models=["model-b"], priority=2),
        ],
        tiering={
            "tier2_standard": TierConfig(description="Standard", models=["model-a", "model-b"]),
        },
        defaults={},
    )


@pytest.fixture
async def db(tmp_path: Path):
    conn = await init_database(tmp_path / "taim.db")
    yield conn
    await conn.close()


def _make_router(transport, config=None, db=None) -> LLMRouter:
    cfg = config or _config()
    tracker = TokenTracker(db) if db else None
    return LLMRouter(
        transport=transport,
        tier_resolver=TierResolver(cfg),
        tracker=tracker,
        product_config=cfg,
    )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_returns_response_on_success(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "test-key")
        transport = MockTransport([make_response("hello")])
        router = _make_router(transport, db=db)
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
        )
        assert result.content == "hello"
        assert result.attempts == 1
        assert result.failover_occurred is False

    async def test_tracks_tokens(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "test-key")
        transport = MockTransport([make_response()])
        router = _make_router(transport, db=db)
        await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
        )
        async with db.execute("SELECT COUNT(*) FROM token_tracking") as cur:
            row = await cur.fetchone()
            assert row[0] == 1


@pytest.mark.asyncio
class TestFailover:
    async def test_failover_on_provider_down(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k1")
        monkeypatch.setenv("SECONDARY_KEY", "k2")
        transport = MockTransport([
            LLMTransportError(LLMErrorType.PROVIDER_DOWN, "connection refused"),
            make_response("from secondary"),
        ])
        router = _make_router(transport, db=db)
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
        )
        assert result.content == "from secondary"
        assert result.failover_occurred is True
        assert result.attempts == 2

    async def test_auth_error_skips_without_counting(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "bad-key")
        monkeypatch.setenv("SECONDARY_KEY", "good-key")
        transport = MockTransport([
            LLMTransportError(LLMErrorType.AUTH_ERROR, "401"),
            make_response("from secondary"),
        ])
        router = _make_router(transport, db=db)
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
        )
        assert result.content == "from secondary"
        assert result.attempts == 1  # Auth skip doesn't count


@pytest.mark.asyncio
class TestMaxAttempts:
    async def test_all_providers_failed(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k1")
        monkeypatch.setenv("SECONDARY_KEY", "k2")
        transport = MockTransport([
            LLMTransportError(LLMErrorType.PROVIDER_DOWN, "down"),
            LLMTransportError(LLMErrorType.PROVIDER_DOWN, "down"),
            LLMTransportError(LLMErrorType.PROVIDER_DOWN, "down"),
        ])
        router = _make_router(transport, db=db)
        with pytest.raises(AllProvidersFailed):
            await router.complete(
                messages=[{"role": "user", "content": "hi"}],
                tier=ModelTierEnum.TIER2_STANDARD,
            )


@pytest.mark.asyncio
class TestJsonValidation:
    async def test_valid_json_passes(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k")
        transport = MockTransport([make_response('{"key": "value"}')])
        router = _make_router(transport, db=db)
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
            expected_format="json",
        )
        assert result.content == '{"key": "value"}'

    async def test_invalid_json_retries_with_reminder(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k")
        transport = MockTransport([
            make_response("not json"),
            make_response('{"fixed": true}'),
        ])
        router = _make_router(transport, db=db)
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
            expected_format="json",
        )
        assert result.content == '{"fixed": true}'
        assert result.attempts == 2


@pytest.mark.asyncio
class TestNoCandidates:
    async def test_raises_config_error(self, db) -> None:
        config = ProductConfig(providers=[], tiering={}, defaults={})
        transport = MockTransport([])
        router = _make_router(transport, config=config, db=db)
        with pytest.raises(ConfigError, match="No AI models configured"):
            await router.complete(
                messages=[{"role": "user", "content": "hi"}],
                tier=ModelTierEnum.TIER2_STANDARD,
            )
```

- [ ] **Step 3: Implement router.py**

File: `backend/src/taim/router/router.py`
```python
"""LLMRouter — orchestrates LLM calls with tiering, failover, and tracking."""

from __future__ import annotations

import asyncio
import json
import os
from uuid import uuid4

import structlog

from taim.errors import AllProvidersFailed, ConfigError, LLMTransportError
from taim.models.config import ProductConfig
from taim.models.router import LLMErrorType, LLMResponse, ModelTierEnum, TokenUsage
from taim.router.failover import RetryAction, classify_error
from taim.router.tiering import TierResolver
from taim.router.tracking import TokenTracker
from taim.router.transport import LLMTransport

logger = structlog.get_logger()


class LLMRouter:
    """Routes LLM calls to the best provider/model with failover."""

    MAX_ATTEMPTS = 3

    def __init__(
        self,
        transport: LLMTransport,
        tier_resolver: TierResolver,
        tracker: TokenTracker | None,
        product_config: ProductConfig,
    ) -> None:
        self._transport = transport
        self._tier_resolver = tier_resolver
        self._tracker = tracker
        self._providers = {p.name: p for p in product_config.providers}

    async def complete(
        self,
        messages: list[dict[str, str]],
        tier: ModelTierEnum,
        expected_format: str | None = None,
        task_id: str | None = None,
        agent_run_id: str | None = None,
        session_id: str | None = None,
    ) -> LLMResponse:
        """Route an LLM call with failover. Max 3 attempts."""
        candidates = self._tier_resolver.resolve(tier)
        if not candidates:
            raise ConfigError(
                user_message="No AI models configured for this task type.",
                detail=f"No candidates for tier {tier.value}",
            )

        attempts = 0
        candidate_idx = 0
        provider_attempts: dict[str, int] = {}
        current_messages = messages
        errors: list[tuple[str, str, LLMErrorType]] = []

        while attempts < self.MAX_ATTEMPTS and candidate_idx < len(candidates):
            provider_name, model_name = candidates[candidate_idx]
            provider_config = self._providers.get(provider_name)
            if not provider_config:
                candidate_idx += 1
                continue

            provider_attempts.setdefault(provider_name, 0)

            api_key = (
                os.environ.get(provider_config.api_key_env)
                if provider_config.api_key_env
                else None
            )
            api_base = provider_config.host

            try:
                response = await self._transport.complete(
                    messages=current_messages,
                    model=model_name,
                    provider=provider_name,
                    api_key=api_key,
                    api_base=api_base,
                )

                # Format validation
                if expected_format == "json":
                    try:
                        json.loads(response.content)
                    except json.JSONDecodeError:
                        raise LLMTransportError(
                            LLMErrorType.BAD_FORMAT,
                            f"Response is not valid JSON: {response.content[:100]}",
                        )

                # Success
                response.failover_occurred = attempts > 0
                response.attempts = attempts + 1

                if self._tracker:
                    await self._tracker.record(
                        TokenUsage(
                            call_id=str(uuid4()),
                            agent_run_id=agent_run_id,
                            task_id=task_id,
                            session_id=session_id,
                            model=model_name,
                            provider=provider_name,
                            prompt_tokens=response.prompt_tokens,
                            completion_tokens=response.completion_tokens,
                            cost_usd=response.cost_usd,
                        )
                    )

                logger.debug(
                    "router.complete",
                    provider=provider_name,
                    model=model_name,
                    attempts=response.attempts,
                    failover=response.failover_occurred,
                    latency_ms=response.latency_ms,
                )
                return response

            except LLMTransportError as e:
                provider_attempts[provider_name] += 1
                errors.append((provider_name, model_name, e.error_type))

                decision = classify_error(
                    e, attempts, provider_attempts[provider_name]
                )

                logger.warning(
                    "router.error",
                    provider=provider_name,
                    model=model_name,
                    error_type=e.error_type.value,
                    action=decision.action.value,
                )

                if decision.action == RetryAction.SKIP:
                    candidate_idx += 1
                    continue

                attempts += 1

                if decision.action == RetryAction.RETRY_SAME:
                    if decision.backoff_seconds > 0:
                        await asyncio.sleep(decision.backoff_seconds)
                    if decision.modify_messages:
                        current_messages = decision.modify_messages(messages)
                elif decision.action == RetryAction.FAILOVER:
                    candidate_idx += 1
                    current_messages = messages

        raise AllProvidersFailed(
            user_message="All AI services failed. Please check your API keys and try again.",
            detail=f"All providers failed after {attempts} attempts: {errors}",
        )
```

- [ ] **Step 4: Run tests — expect PASS** (~10 passed)
- [ ] **Step 5: Run full suite**

Run: `cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v`

- [ ] **Step 6: Commit**

```bash
git add backend/src/taim/router/router.py tests/backend/test_router.py tests/backend/conftest.py
git commit -m "feat: add LLMRouter with error-type-aware failover and JSON validation"
```

---

## Task 8: Integration & Main App Update

**Files:**
- Modify: `backend/src/taim/main.py`
- Modify: `backend/src/taim/api/deps.py`
- Modify: `backend/src/taim/router/__init__.py`

- [ ] **Step 1: Update router/__init__.py with exports**

File: `backend/src/taim/router/__init__.py`
```python
"""TAIM LLM Router — provider selection, failover, and tracking."""

from taim.router.router import LLMRouter
from taim.router.transport import LLMTransport
from taim.router.tiering import TierResolver
from taim.router.tracking import TokenTracker

__all__ = ["LLMRouter", "LLMTransport", "TierResolver", "TokenTracker"]
```

- [ ] **Step 2: Add Router to lifespan in main.py**

In `main.py` lifespan, after `prompt_loader = PromptLoader(...)`:
```python
    # 7. Router init
    from taim.router import LLMRouter, LLMTransport, TierResolver, TokenTracker
    transport = LLMTransport()
    tier_resolver = TierResolver(product_config)
    tracker = TokenTracker(db)
    router = LLMRouter(transport, tier_resolver, tracker, product_config)

    app.state.router = router
```

- [ ] **Step 3: Add get_router to deps.py**

Append to `backend/src/taim/api/deps.py`:
```python
from taim.router.router import LLMRouter

def get_router(request: Request) -> LLMRouter:
    """Inject the LLMRouter singleton."""
    return request.app.state.router
```

- [ ] **Step 4: Run full test suite**

Run: `cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v`

- [ ] **Step 5: Run ruff**

Run: `cd /Users/reykz/repositorys/TAIM/backend && uv run ruff check src/ && uv run ruff format --check src/`

- [ ] **Step 6: Commit**

```bash
git add backend/src/taim/router/__init__.py backend/src/taim/main.py backend/src/taim/api/deps.py
git commit -m "feat: integrate LLM Router into FastAPI lifespan and DI"
```

---

## Task 9: Final Verification

- [ ] **Step 1: Run full test suite with coverage**

Run: `cd /Users/reykz/repositorys/TAIM/backend && uv run pytest --cov=taim --cov-report=term-missing -v`

- [ ] **Step 2: Run ruff lint + format**

Run: `cd /Users/reykz/repositorys/TAIM/backend && uv run ruff check src/ && uv run ruff format --check src/`

- [ ] **Step 3: Manual startup test**

Run: `cd /Users/reykz/repositorys/TAIM/backend && uv run uvicorn taim.main:app --host localhost --port 8000`
Expected: Server starts with `taim.started` log, health endpoint works.

- [ ] **Step 4: Fix any issues and commit**

---

## Summary

| Task | Module | Tests | Est. Steps |
|------|--------|-------|------------|
| 1 | models/router.py | test_router_models.py | 5 |
| 2 | errors.py (extend) | test_errors.py (extend) | 5 |
| 3 | router/tiering.py | test_tiering.py | 5 |
| 4 | router/failover.py | test_failover.py | 5 |
| 5 | router/tracking.py | test_tracking.py | 5 |
| 6 | router/transport.py | test_transport.py | 5 |
| 7 | router/router.py | test_router.py | 6 |
| 8 | main.py + deps.py (extend) | — | 6 |
| 9 | Verification | — | 4 |
| **Total** | **8 new files** | **7 test files** | **46 steps** |

Parallelizable: Tasks 3+4+5 (tiering, failover, tracking) are independent.
