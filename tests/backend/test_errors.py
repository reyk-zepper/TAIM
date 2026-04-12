"""Tests for the TAIM error hierarchy."""

from pathlib import Path

from taim.errors import (
    ConfigError,
    DatabaseError,
    PromptNotFoundError,
    PromptVariableError,
    TaimError,
    VaultError,
)


class TestTaimError:
    def test_has_user_message_and_detail(self) -> None:
        err = TaimError(user_message="Something went wrong.", detail="NullPointerException at line 42")
        assert err.user_message == "Something went wrong."
        assert err.detail == "NullPointerException at line 42"

    def test_detail_defaults_to_user_message(self) -> None:
        err = TaimError(user_message="Oops")
        assert err.detail == "Oops"

    def test_str_returns_detail(self) -> None:
        err = TaimError(user_message="Friendly", detail="Technical")
        assert str(err) == "Technical"

    def test_is_exception(self) -> None:
        assert issubclass(TaimError, Exception)


class TestSubclasses:
    def test_vault_error_is_taim_error(self) -> None:
        err = VaultError(user_message="Vault broken")
        assert isinstance(err, TaimError)

    def test_config_error_is_taim_error(self) -> None:
        err = ConfigError(user_message="Config broken")
        assert isinstance(err, TaimError)

    def test_database_error_is_taim_error(self) -> None:
        err = DatabaseError(user_message="DB broken")
        assert isinstance(err, TaimError)


class TestPromptNotFoundError:
    def test_builds_messages_from_args(self) -> None:
        err = PromptNotFoundError("intent-classify", Path("/vault/prompts/intent-classify.yaml"))
        assert "intent-classify" in err.user_message
        assert "missing from the vault" in err.user_message
        assert "/vault/prompts/intent-classify.yaml" in err.detail
        assert isinstance(err, TaimError)


class TestPromptVariableError:
    def test_builds_messages_from_args(self) -> None:
        err = PromptVariableError("intent-classify", "user_message")
        assert "check the logs" in err.user_message.lower()
        assert "user_message" in err.detail
        assert "intent-classify" in err.detail
        assert isinstance(err, TaimError)
