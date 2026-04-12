"""TAIM error hierarchy with dual personality: user-friendly + developer-detailed."""

from __future__ import annotations

from pathlib import Path

from taim.models.router import LLMErrorType


class TaimError(Exception):
    """Base error with user-facing and developer-facing messages."""

    def __init__(self, user_message: str, detail: str | None = None) -> None:
        self.user_message = user_message
        self.detail = detail or user_message
        super().__init__(self.detail)


class VaultError(TaimError):
    """Vault filesystem errors."""


class ConfigError(TaimError):
    """Configuration loading/validation errors."""


class DatabaseError(TaimError):
    """SQLite errors."""


class PromptNotFoundError(TaimError):
    """Requested prompt YAML file doesn't exist."""

    def __init__(self, prompt_name: str, path: Path) -> None:
        super().__init__(
            user_message=f"A required prompt template '{prompt_name}' is missing from the vault.",
            detail=f"Prompt file not found: {path}",
        )


class PromptVariableError(TaimError):
    """A template variable was required but not provided."""

    def __init__(self, prompt_name: str, variable: str) -> None:
        super().__init__(
            user_message="An internal configuration error occurred. Please check the logs.",
            detail=f"Missing variable '{variable}' in prompt '{prompt_name}'",
        )


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
