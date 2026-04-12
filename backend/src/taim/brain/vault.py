"""VaultOps — TAIM Vault filesystem operations."""

from __future__ import annotations

from pathlib import Path

import yaml

from taim.errors import ConfigError, VaultError
from taim.models.config import (
    ProductConfig,
    ProviderConfig,
    TierConfig,
    VaultConfig,
)

_DEFAULT_TAIM_YAML = """\
# TAIM — Main Configuration
version: "0.1.0"

server:
  host: "localhost"
  port: 8000
  cors_origins:
    - "http://localhost:5173"
    - "http://localhost:3000"

conversation:
  verbosity: normal
  language: auto

orchestrator:
  heartbeat_interval: 30
  agent_timeout: 120
  default_iterations: 2

tracking:
  currency: "EUR"
  usd_to_eur_rate: 0.92
"""

_DEFAULT_PROVIDERS_YAML = """\
# TAIM — LLM Provider Configuration
# API keys are loaded from environment variables (never stored here).
providers: []

tiering:
  tier1_premium:
    description: "Complex reasoning, architecture, strategy"
    models: []
  tier2_standard:
    description: "Code generation, text processing, analysis"
    models: []
  tier3_economy:
    description: "Classification, formatting, routing"
    models: []
"""

_DEFAULT_DEFAULTS_YAML = """\
# TAIM — Smart Defaults
team:
  time_budget: "2h"
  token_budget: 500000
  iteration_rounds: 2
  on_limit_reached: graceful_stop

agent:
  max_iterations: 10
  default_tier: tier2_standard
  approval_gates:
    - file_deletion
    - external_communication
    - budget_exceeded

output:
  format: markdown
  language: auto

costs:
  display_currency: true
  warning_threshold: 10.00
"""


class VaultOps:
    """Filesystem operations for the TAIM Vault."""

    def __init__(self, vault_path: Path) -> None:
        resolved = vault_path.resolve()
        if resolved.exists() and not resolved.is_dir():
            raise VaultError(
                user_message=f"The vault path '{vault_path}' points to a file, not a directory.",
                detail=f"Vault path {resolved} points to a file, not a directory",
            )
        self.vault_config = VaultConfig.from_root(resolved)

    def ensure_vault(self) -> None:
        """Create vault directory structure if missing. Idempotent."""
        directories = [
            self.vault_config.config_dir,
            self.vault_config.agents_dir,
            self.vault_config.teams_dir,
            self.vault_config.rules_dir / "compliance",
            self.vault_config.rules_dir / "behavior",
            self.vault_config.shared_dir,
            self.vault_config.users_dir / "default" / "memory",
            self.vault_config.prompts_dir,
            self.vault_config.state_dir,
        ]
        try:
            for d in directories:
                d.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise VaultError(
                user_message=(
                    "TAIM can't create its data directory. "
                    f"Please check file permissions for '{self.vault_config.vault_root}'."
                ),
                detail=f"PermissionError creating directory: {e}",
            ) from e

        index_path = self.vault_config.users_dir / "default" / "INDEX.md"
        if not index_path.exists():
            index_path.write_text("# Memory Index\n\n<!-- Entries added automatically -->\n")

        self._ensure_default_configs()

    def load_raw_yaml(self, filename: str) -> dict:
        """Load a YAML file from the config directory."""
        path = self.vault_config.config_dir / filename
        if not path.exists():
            raise ConfigError(
                user_message=f"Configuration file '{filename}' is missing from the vault.",
                detail=f"Configuration file '{filename}' is missing from the vault: {path}",
            )
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise ConfigError(
                user_message=(
                    f"Configuration file '{filename}' has a syntax error. "
                    "Please check the file format."
                ),
                detail=f"Configuration file '{filename}' has a syntax error in {path}: {e}",
            ) from e

    def load_product_config(self) -> ProductConfig:
        """Load and validate all YAML config files into ProductConfig."""
        taim_cfg = self.load_raw_yaml("taim.yaml")
        providers_cfg = self.load_raw_yaml("providers.yaml")
        defaults_cfg = self.load_raw_yaml("defaults.yaml")

        providers = [ProviderConfig(**p) for p in providers_cfg.get("providers", [])]
        tiering = {
            name: TierConfig(**tier)
            for name, tier in providers_cfg.get("tiering", {}).items()
        }

        conversation = taim_cfg.get("conversation", {})
        orchestrator = taim_cfg.get("orchestrator", {})
        tracking = taim_cfg.get("tracking", {})

        return ProductConfig(
            providers=providers,
            tiering=tiering,
            defaults=defaults_cfg,
            conversation_verbosity=conversation.get("verbosity", "normal"),
            conversation_language=conversation.get("language", "auto"),
            heartbeat_interval=orchestrator.get("heartbeat_interval", 30),
            agent_timeout=orchestrator.get("agent_timeout", 120),
            default_iterations=orchestrator.get("default_iterations", 2),
            usd_to_eur_rate=tracking.get("usd_to_eur_rate", 0.92),
        )

    def _ensure_default_configs(self) -> None:
        """Write default config files only if they don't exist."""
        defaults = {
            "taim.yaml": _DEFAULT_TAIM_YAML,
            "providers.yaml": _DEFAULT_PROVIDERS_YAML,
            "defaults.yaml": _DEFAULT_DEFAULTS_YAML,
        }
        for filename, content in defaults.items():
            path = self.vault_config.config_dir / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")
