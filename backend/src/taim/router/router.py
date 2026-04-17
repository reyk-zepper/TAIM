"""LLMRouter — orchestrates LLM calls with tiering, failover, and tracking."""

from __future__ import annotations

import asyncio
import json
import os
from uuid import uuid4

import structlog

from taim.errors import AllProvidersFailed, ConfigError, LLMTransportError
from taim.models.config import ProductConfig
from taim.models.router import LLMErrorType, LLMResponse, ModelTierEnum, RetryAction, TokenUsage
from taim.router.failover import classify_error
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
        tools: list[dict] | None = None,
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

            # Pre-call budget check (US-6.4)
            if (
                provider_config.monthly_budget_eur is not None
                and self._tracker
            ):
                try:
                    monthly_cost = await self._tracker.get_monthly_cost(provider_name)
                    # Approximate: compare USD cost against EUR budget / 0.92
                    budget_usd = provider_config.monthly_budget_eur / 0.92
                    if monthly_cost >= budget_usd:
                        logger.info(
                            "router.budget_exceeded",
                            provider=provider_name,
                            monthly_cost=monthly_cost,
                            budget_usd=budget_usd,
                        )
                        candidate_idx += 1
                        continue
                except Exception:
                    logger.exception("router.budget_check_error")

            api_key = (
                os.environ.get(provider_config.api_key_env) if provider_config.api_key_env else None
            )
            api_base = provider_config.host

            try:
                response = await self._transport.complete(
                    messages=current_messages,
                    model=model_name,
                    provider=provider_name,
                    api_key=api_key,
                    api_base=api_base,
                    tools=tools,
                )

                # Format validation
                if expected_format == "json" and not tools:
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

                decision = classify_error(e, attempts, provider_attempts[provider_name])

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
