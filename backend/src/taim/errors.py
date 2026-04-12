"""TAIM error hierarchy with dual personality: user-friendly + developer-detailed."""

from __future__ import annotations

from pathlib import Path


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
