"""Pydantic models for tAIm configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from taim.settings import TaimSettings

_DEFAULT_CORS = ["http://localhost:5173", "http://localhost:3000"]


class ServerConfig(BaseModel):
    """Server settings — from taim.yaml, overridable by ENV."""

    host: str = "localhost"
    port: int = 8000
    cors_origins: list[str] = _DEFAULT_CORS.copy()

    @classmethod
    def from_yaml_and_env(cls, yaml_server: dict) -> ServerConfig:
        """Build from YAML baseline with ENV overrides."""
        cors_env = os.environ.get("TAIM_CORS_ORIGINS")
        return cls(
            host=os.environ.get("TAIM_HOST") or yaml_server.get("host", "localhost"),
            port=int(os.environ.get("TAIM_PORT") or yaml_server.get("port", 8000)),
            cors_origins=(
                [o.strip() for o in cors_env.split(",") if o.strip()]
                if cors_env
                else yaml_server.get("cors_origins", _DEFAULT_CORS.copy())
            ),
        )


class ProviderConfig(BaseModel):
    """LLM provider definition."""

    name: str
    api_key_env: str = ""
    host: str | None = None
    models: list[str]
    priority: int = 1
    monthly_budget_eur: float | None = None


class TierConfig(BaseModel):
    """Model tier definition."""

    description: str
    models: list[str]


class ProductConfig(BaseModel):
    """Product behavior — loaded from vault YAML files."""

    providers: list[ProviderConfig]
    tiering: dict[str, TierConfig]
    defaults: dict[str, Any]
    conversation_verbosity: str = "normal"
    conversation_language: str = "auto"
    heartbeat_interval: int = 30
    agent_timeout: int = 120
    default_iterations: int = 2
    usd_to_eur_rate: float = 0.92


class VaultConfig(BaseModel):
    """Resolved vault paths — computed once at startup."""

    vault_root: Path
    config_dir: Path
    agents_dir: Path
    teams_dir: Path
    rules_dir: Path
    shared_dir: Path
    users_dir: Path
    prompts_dir: Path
    state_dir: Path
    db_path: Path

    @classmethod
    def from_root(cls, vault_root: Path) -> VaultConfig:
        """Compute all sub-paths from vault root. Resolves to absolute."""
        root = vault_root.resolve()
        return cls(
            vault_root=root,
            config_dir=root / "config",
            agents_dir=root / "agents",
            teams_dir=root / "teams",
            rules_dir=root / "rules",
            shared_dir=root / "shared",
            users_dir=root / "users",
            prompts_dir=root / "system" / "prompts",
            state_dir=root / "system" / "state",
            db_path=root / "system" / "state" / "taim.db",
        )


class SystemConfig(BaseModel):
    """Complete runtime config — composed at startup, injected via DI."""

    model_config = {"arbitrary_types_allowed": True}

    server: ServerConfig
    vault: VaultConfig
    product: ProductConfig
    settings: TaimSettings
