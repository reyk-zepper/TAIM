"""Tests for TaimSettings (ENV-based infrastructure config)."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.settings import TaimSettings


class TestDefaults:
    def test_default_vault_path(self) -> None:
        s = TaimSettings()
        assert s.vault_path == Path("./taim-vault")

    def test_default_env(self) -> None:
        s = TaimSettings()
        assert s.env == "development"

    def test_default_log_level(self) -> None:
        s = TaimSettings()
        assert s.log_level == "INFO"

    def test_default_log_format(self) -> None:
        s = TaimSettings()
        assert s.log_format == "dev"


class TestEnvOverride:
    def test_vault_path_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_VAULT_PATH", "/custom/vault")
        s = TaimSettings()
        assert s.vault_path == Path("/custom/vault")

    def test_env_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_ENV", "production")
        s = TaimSettings()
        assert s.env == "production"

    def test_log_level_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_LOG_LEVEL", "DEBUG")
        s = TaimSettings()
        assert s.log_level == "DEBUG"

    def test_log_format_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_LOG_FORMAT", "json")
        s = TaimSettings()
        assert s.log_format == "json"
