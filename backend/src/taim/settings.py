"""TaimSettings — ENV-only infrastructure settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class TaimSettings(BaseSettings):
    """Pure infrastructure settings loaded from ENV + .env file.

    These have no YAML counterpart. Server host/port/CORS live in taim.yaml.
    """

    model_config = SettingsConfigDict(
        env_prefix="TAIM_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    vault_path: Path = Path("./taim-vault")
    env: str = "development"
    log_level: str = "INFO"
    log_format: str = "dev"
