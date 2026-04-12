"""Error classification and retry strategy for LLM failover."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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
                return RetryDecision(action=RetryAction.RETRY_SAME, modify_messages=_soften_messages)
            return RetryDecision(action=RetryAction.FAILOVER)
        case LLMErrorType.BAD_FORMAT:
            if same_provider_attempts < 2:
                return RetryDecision(action=RetryAction.RETRY_SAME, modify_messages=_add_format_reminder)
            return RetryDecision(action=RetryAction.FAILOVER)
        case LLMErrorType.PROVIDER_DOWN:
            return RetryDecision(action=RetryAction.FAILOVER)
        case LLMErrorType.AUTH_ERROR:
            return RetryDecision(action=RetryAction.SKIP)
    return RetryDecision(action=RetryAction.FAILOVER)


def _soften_messages(messages: list[dict]) -> list[dict]:
    """Prepend a safety-conscious system instruction. Does not mutate original."""
    return [
        {"role": "system", "content": "Please provide a helpful response within content guidelines. Avoid controversial or sensitive content."},
        *messages,
    ]


def _add_format_reminder(messages: list[dict]) -> list[dict]:
    """Append a JSON format instruction. Does not mutate original."""
    return [
        *messages,
        {"role": "system", "content": "IMPORTANT: Respond with valid JSON only. No markdown, no explanation, just the JSON object."},
    ]
