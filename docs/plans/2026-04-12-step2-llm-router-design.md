# Step 2: LLM Router — Implementation Design

> Version: 1.0
> Date: 2026-04-12
> Status: Reviewed — critical review applied
> Scope: US-6.1, US-6.2, US-6.3 (P0), US-6.4 infrastructure only (P1)

---

## 1. Overview

Step 2 builds the LLM Router — the single gateway through which every LLM call in TAIM flows. It handles provider selection, model tiering, error-type-aware failover, and per-call token tracking.

**Deliverables:**
1. LLMTransport — wraps a single `litellm.acompletion()` call
2. TierResolver — maps ModelTierEnum to ordered (provider, model) candidates
3. ErrorClassifier + RetryStrategy — error-type-aware failover logic
4. LLMRouter — orchestrates transport calls with failover (max 3 attempts)
5. TokenTracker — per-call logging to `token_tracking` SQLite table
6. Router integration into FastAPI DI

**What Step 2 does NOT build:**
- No streaming (complete responses only — streaming is Step 5)
- No budget enforcement blocking (infrastructure built, blocking is Step 8)
- No low-quality detection heuristics (Phase 2)

**Guiding Principle:** The Router is invisible to the user. When it works perfectly, the user never knows it exists. When it fails, the user gets a clear, human-friendly explanation with actionable suggestions (AD-10).

---

## 2. Module Architecture

### 2.1 File Layout

```
backend/src/taim/
├── router/
│   ├── __init__.py
│   ├── transport.py       # LLMTransport — single litellm call wrapper
│   ├── router.py          # LLMRouter — orchestrates with failover
│   ├── tiering.py         # TierResolver — tier → [(provider, model)]
│   ├── failover.py        # ErrorClassifier, RetryDecision
│   └── tracking.py        # TokenTracker — per-call SQLite logging
├── models/
│   ├── config.py          # (existing — ProviderConfig, TierConfig, etc.)
│   └── router.py          # (new — LLMResponse, LLMErrorType, TokenUsage)
```

### 2.2 Dependency Graph

```
models/router.py         (no TAIM deps — pure Pydantic)
    ↓
router/failover.py       (depends on: models/router)
router/tiering.py        (depends on: models/config, models/router)
router/transport.py      (depends on: models/router — wraps litellm)
router/tracking.py       (depends on: models/router — writes SQLite)
    ↓
router/router.py         (depends on: all above — composes)
    ↓
main.py                  (adds Router to lifespan + DI)
```

---

## 3. Data Models

### 3.1 New Models (`models/router.py`)

```python
from enum import Enum
from pydantic import BaseModel

class ModelTierEnum(str, Enum):
    TIER1_PREMIUM = "tier1_premium"
    TIER2_STANDARD = "tier2_standard"
    TIER3_ECONOMY = "tier3_economy"

class LLMErrorType(str, Enum):
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    SAFETY_FILTER = "safety_filter"
    BAD_FORMAT = "bad_format"
    PROVIDER_DOWN = "provider_down"
    AUTH_ERROR = "auth_error"

class RetryAction(str, Enum):
    RETRY_SAME = "retry_same"     # Retry same provider (with possible modifications)
    FAILOVER = "failover"         # Move to next provider
    SKIP = "skip"                 # Skip provider, don't count as attempt

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
```

---

## 4. LLMTransport

### 4.1 Responsibility

One thing: make a single `litellm.acompletion()` call and return a normalized `LLMResponse`, or raise a typed exception.

### 4.2 Design

```python
class LLMTransport:
    """Wraps a single litellm.acompletion() call."""

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

        try:
            response = await litellm.acompletion(
                model=litellm_model,
                messages=messages,
                api_key=api_key,
                api_base=api_base,
                num_retries=0,          # TAIM handles retries
                request_timeout=timeout,
            )
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
            cost = 0.0  # Ollama or unknown model

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

### 4.3 LLMTransportError

```python
class LLMTransportError(TaimError):
    """Error from a single LLM transport call."""

    def __init__(self, error_type: LLMErrorType, detail: str) -> None:
        self.error_type = error_type
        super().__init__(
            user_message=_USER_MESSAGES.get(error_type, "An LLM error occurred."),
            detail=detail,
        )

_USER_MESSAGES = {
    LLMErrorType.RATE_LIMIT: "The AI service is temporarily busy. Retrying...",
    LLMErrorType.TIMEOUT: "The AI service is responding slowly. Trying alternatives...",
    LLMErrorType.SAFETY_FILTER: "The response was filtered by the AI service's safety system.",
    LLMErrorType.PROVIDER_DOWN: "The AI service is currently unavailable.",
    LLMErrorType.AUTH_ERROR: "The API key for this AI service appears invalid. Please check your configuration.",
    LLMErrorType.BAD_FORMAT: "The AI response wasn't in the expected format. Retrying...",
}
```

---

## 5. TierResolver

### 5.1 Responsibility

Map a `ModelTierEnum` to an ordered list of `(provider_name, model_name)` candidates, sorted by provider priority.

### 5.2 Design

```python
class TierResolver:
    """Maps tier → [(provider, model)] candidates ordered by priority."""

    def __init__(self, product_config: ProductConfig) -> None:
        self._providers = {p.name: p for p in product_config.providers}
        self._tiering = product_config.tiering

    def resolve(self, tier: ModelTierEnum) -> list[tuple[str, str]]:
        """Returns (provider_name, model_name) pairs for the tier, sorted by priority."""
        tier_config = self._tiering.get(tier.value)
        if not tier_config:
            return []

        tier_models = set(tier_config.models)
        candidates = []

        for provider in sorted(self._providers.values(), key=lambda p: p.priority):
            for model in provider.models:
                if model in tier_models:
                    candidates.append((provider.name, model))

        return candidates
```

### 5.3 Fallback Behavior

If a tier has no candidates (e.g., tier3_economy with no configured models), the Router raises a `ConfigError` with: "No models configured for tier 'tier3_economy'. Please check providers.yaml."

---

## 6. ErrorClassifier & RetryStrategy

### 6.1 Error → Action Mapping

```python
@dataclass
class RetryDecision:
    action: RetryAction
    backoff_seconds: float = 0.0
    modify_messages: Callable[[list[dict]], list[dict]] | None = None

def classify_error(
    error: LLMTransportError,
    attempt_number: int,
    same_provider_attempts: int,
) -> RetryDecision:
    """Decide what to do after a transport error."""

    match error.error_type:
        case LLMErrorType.RATE_LIMIT:
            backoff = min(2 ** (same_provider_attempts - 1), 4)  # 1s, 2s, 4s
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
            return RetryDecision(action=RetryAction.SKIP)  # Don't count as attempt
```

### 6.2 Message Modifiers

```python
def _soften_messages(messages: list[dict]) -> list[dict]:
    """Prepend a safety-conscious system instruction."""
    softener = {
        "role": "system",
        "content": "Please provide a helpful response within content guidelines. "
                   "Avoid controversial or sensitive content.",
    }
    return [softener, *messages]

def _add_format_reminder(messages: list[dict]) -> list[dict]:
    """Append a format instruction to the last system message."""
    reminder = {
        "role": "system",
        "content": "IMPORTANT: Respond with valid JSON only. No markdown, no explanation, just the JSON object.",
    }
    return [*messages, reminder]
```

**Critical:** These create NEW lists — the caller's original messages are never mutated (Review Finding #5).

---

## 7. LLMRouter

### 7.1 Core Loop

```python
class LLMRouter:
    MAX_ATTEMPTS = 3

    def __init__(
        self,
        transport: LLMTransport,
        tier_resolver: TierResolver,
        tracker: TokenTracker,
        product_config: ProductConfig,
    ) -> None: ...

    async def complete(
        self,
        messages: list[dict[str, str]],
        tier: ModelTierEnum,
        expected_format: str | None = None,  # "json" or None
        task_id: str | None = None,
        agent_run_id: str | None = None,
        session_id: str | None = None,
    ) -> LLMResponse:
        candidates = self._tier_resolver.resolve(tier)
        if not candidates:
            raise ConfigError(
                user_message=f"No AI models configured for this task type.",
                detail=f"No candidates for tier {tier.value}",
            )

        attempts = 0
        candidate_idx = 0
        provider_attempts: dict[str, int] = {}
        current_messages = messages
        errors: list[tuple[str, str, LLMErrorType]] = []

        while attempts < self.MAX_ATTEMPTS and candidate_idx < len(candidates):
            provider_name, model_name = candidates[candidate_idx]
            provider_config = self._get_provider(provider_name)
            provider_attempts.setdefault(provider_name, 0)

            # Resolve API key at call time (not startup)
            api_key = os.environ.get(provider_config.api_key_env) if provider_config.api_key_env else None
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
                        raise LLMTransportError(LLMErrorType.BAD_FORMAT, "Response is not valid JSON")

                # Success — track and return
                response.failover_occurred = attempts > 0
                response.attempts = attempts + 1
                await self._tracker.record(TokenUsage(
                    call_id=str(uuid4()),
                    agent_run_id=agent_run_id,
                    task_id=task_id,
                    session_id=session_id,
                    model=model_name,
                    provider=provider_name,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    cost_usd=response.cost_usd,
                ))
                return response

            except LLMTransportError as e:
                provider_attempts[provider_name] += 1
                errors.append((provider_name, model_name, e.error_type))

                decision = classify_error(e, attempts, provider_attempts[provider_name])

                if decision.action == RetryAction.SKIP:
                    # Auth error — skip provider, don't count attempt
                    candidate_idx += 1
                    continue

                attempts += 1

                if decision.action == RetryAction.RETRY_SAME:
                    if decision.backoff_seconds > 0:
                        await asyncio.sleep(decision.backoff_seconds)
                    if decision.modify_messages:
                        current_messages = decision.modify_messages(messages)  # Copy, not mutate
                elif decision.action == RetryAction.FAILOVER:
                    candidate_idx += 1
                    current_messages = messages  # Reset to original

        raise AllProvidersFailed(
            user_message="All AI services failed. Please check your API keys and try again.",
            detail=f"All providers failed after {attempts} attempts: {errors}",
        )
```

### 7.2 API Key Resolution

Keys are resolved at call time via `os.environ.get(provider.api_key_env)`:
- Allows key changes without restart
- Missing key → litellm raises AuthError → Router skips provider
- Ollama: no key needed, uses `api_base` instead

### 7.3 Degraded Mode (US-6.1 AC4)

If no providers are configured (`candidates == []`), the Router raises `ConfigError` with a human-friendly message. The server doesn't crash — the health endpoint shows `providers: []` and any LLM call fails gracefully.

---

## 8. TokenTracker

### 8.1 Design

```python
class TokenTracker:
    """Per-call token logging to SQLite."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def record(self, usage: TokenUsage) -> None:
        """Insert a token tracking row."""
        await self._db.execute(
            """INSERT INTO token_tracking
               (call_id, agent_run_id, task_id, session_id, model, provider,
                prompt_tokens, completion_tokens, cost_usd)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (usage.call_id, usage.agent_run_id, usage.task_id, usage.session_id,
             usage.model, usage.provider, usage.prompt_tokens,
             usage.completion_tokens, usage.cost_usd),
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

### 8.2 Budget Infrastructure (P1 prep)

`get_monthly_cost()` is built now but not called by the Router in Step 2. Step 8 (Heartbeat & Tracking) will add the pre-call budget check.

---

## 9. FastAPI Integration

### 9.1 Lifespan Addition

```python
# In main.py lifespan, after PromptLoader init:
transport = LLMTransport()
tier_resolver = TierResolver(product_config)
tracker = TokenTracker(db)
router = LLMRouter(transport, tier_resolver, tracker, product_config)

app.state.router = router
```

### 9.2 New DI Function

```python
# api/deps.py
def get_router(request: Request) -> LLMRouter:
    return request.app.state.router
```

---

## 10. Test Strategy

### 10.1 MockTransport

All Router tests use a mock transport — never real LLM calls:

```python
class MockTransport:
    """Test transport that returns canned responses or raises errors."""

    def __init__(self, responses: list[LLMResponse | LLMTransportError]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def complete(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, LLMTransportError):
            raise response
        return response
```

### 10.2 Test Categories

| Test File | Tests | Module |
|-----------|-------|--------|
| `test_transport.py` | LiteLLM exception mapping, response normalization, cost calc | `transport.py` |
| `test_tiering.py` | Tier resolution, priority ordering, empty tier handling | `tiering.py` |
| `test_failover.py` | All 6 error types, retry/failover/skip decisions | `failover.py` |
| `test_router.py` | Happy path, failover flows, max attempts, JSON validation, auth skip | `router.py` |
| `test_tracking.py` | SQLite insert, monthly cost query | `tracking.py` |

### 10.3 Transport Tests

`test_transport.py` needs special handling — it tests the actual litellm exception mapping. Use `pytest-mock` to mock `litellm.acompletion` and make it raise specific exceptions.

---

## Appendix: Review Log

| # | Finding | Resolution |
|---|---------|------------|
| 1 | Auth errors must not consume attempts | SKIP action in ErrorClassifier |
| 2 | LiteLLM retries must be disabled | `num_retries=0` in transport |
| 3 | No streaming correct for Step 2 | Confirmed — thinking indicators don't need streaming |
| 4 | Low-quality detection is Phase 2 | Not built, Router accepts tier override for future use |
| 5 | Prompt modification must be transparent | Message modifiers create copies, never mutate original |
| 6 | litellm.completion_cost() for costs | Used with fallback to 0.0 for Ollama/unknown |
| 7 | LiteLLM needs provider/model format | Transport builds `f"{provider}/{model}"` |
| 8 | Budget enforcement P1 | Infrastructure built, blocking deferred to Step 8 |

---

*End of Step 2 LLM Router Design.*
