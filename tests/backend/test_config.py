"""Tests for Pydantic config models."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.models.config import (
    ProductConfig,
    ProviderConfig,
    ServerConfig,
    SystemConfig,
    TierConfig,
    VaultConfig,
)
from taim.settings import TaimSettings


class TestVaultConfig:
    def test_from_root_resolves_all_paths(self, tmp_path: Path) -> None:
        vc = VaultConfig.from_root(tmp_path / "vault")
        assert vc.vault_root == (tmp_path / "vault").resolve()
        assert vc.config_dir == vc.vault_root / "config"
        assert vc.agents_dir == vc.vault_root / "agents"
        assert vc.prompts_dir == vc.vault_root / "system" / "prompts"
        assert vc.db_path == vc.vault_root / "system" / "state" / "taim.db"

    def test_paths_are_absolute(self) -> None:
        vc = VaultConfig.from_root(Path("./relative"))
        assert vc.vault_root.is_absolute()


class TestServerConfig:
    def test_defaults(self) -> None:
        sc = ServerConfig()
        assert sc.host == "localhost"
        assert sc.port == 8000
        assert "http://localhost:5173" in sc.cors_origins

    def test_from_yaml_uses_yaml_values(self) -> None:
        sc = ServerConfig.from_yaml_and_env({"host": "0.0.0.0", "port": 9000})
        assert sc.host == "0.0.0.0"
        assert sc.port == 9000

    def test_env_overrides_yaml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_HOST", "192.168.1.1")
        monkeypatch.setenv("TAIM_PORT", "3000")
        sc = ServerConfig.from_yaml_and_env({"host": "0.0.0.0", "port": 9000})
        assert sc.host == "192.168.1.1"
        assert sc.port == 3000

    def test_cors_from_yaml(self) -> None:
        sc = ServerConfig.from_yaml_and_env(
            {"cors_origins": ["http://example.com"]}
        )
        assert sc.cors_origins == ["http://example.com"]

    def test_cors_env_overrides_yaml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TAIM_CORS_ORIGINS", "http://a.com,http://b.com")
        sc = ServerConfig.from_yaml_and_env(
            {"cors_origins": ["http://example.com"]}
        )
        assert sc.cors_origins == ["http://a.com", "http://b.com"]

    def test_falls_back_to_defaults_when_yaml_empty(self) -> None:
        sc = ServerConfig.from_yaml_and_env({})
        assert sc.host == "localhost"
        assert sc.port == 8000


class TestProviderConfig:
    def test_minimal(self) -> None:
        pc = ProviderConfig(name="anthropic", models=["claude-sonnet-4-20250514"])
        assert pc.name == "anthropic"
        assert pc.priority == 1
        assert pc.monthly_budget_eur is None

    def test_full(self) -> None:
        pc = ProviderConfig(
            name="openai",
            api_key_env="OPENAI_API_KEY",
            models=["gpt-4o"],
            priority=2,
            monthly_budget_eur=50.0,
        )
        assert pc.api_key_env == "OPENAI_API_KEY"
        assert pc.monthly_budget_eur == 50.0


class TestProductConfig:
    def test_defaults(self) -> None:
        pc = ProductConfig(
            providers=[],
            tiering={},
            defaults={},
        )
        assert pc.conversation_verbosity == "normal"
        assert pc.heartbeat_interval == 30
        assert pc.usd_to_eur_rate == 0.92


class TestSystemConfig:
    def test_composes_all_layers(self, tmp_path: Path) -> None:
        sc = SystemConfig(
            server=ServerConfig(),
            vault=VaultConfig.from_root(tmp_path),
            product=ProductConfig(providers=[], tiering={}, defaults={}),
            settings=TaimSettings(),
        )
        assert sc.server.host == "localhost"
        assert sc.vault.vault_root == tmp_path.resolve()
        assert sc.product.conversation_verbosity == "normal"
