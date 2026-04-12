"""TAIM FastAPI application — entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from taim.api.chat import router as chat_router
from taim.api.health import router as health_router
from taim.brain.database import init_database
from taim.brain.logging import configure_logging
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.models.config import ServerConfig, SystemConfig
from taim.settings import TaimSettings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: init vault, load config, init DB, init PromptLoader."""
    settings = TaimSettings()
    configure_logging(settings.log_level, settings.log_format)

    vault_ops = VaultOps(settings.vault_path)
    vault_ops.ensure_vault()

    taim_yaml = vault_ops.load_raw_yaml("taim.yaml")
    product_config = vault_ops.load_product_config()
    server_config = ServerConfig.from_yaml_and_env(taim_yaml.get("server", {}))

    system_config = SystemConfig(
        server=server_config,
        vault=vault_ops.vault_config,
        product=product_config,
        settings=settings,
    )

    db = await init_database(system_config.vault.db_path)
    prompt_loader = PromptLoader(system_config.vault.prompts_dir)

    app.state.config = system_config
    app.state.db = db
    app.state.prompt_loader = prompt_loader

    logger.info(
        "taim.started",
        vault=str(system_config.vault.vault_root),
        host=server_config.host,
        port=server_config.port,
        providers=[p.name for p in product_config.providers],
    )

    yield

    await db.close()
    logger.info("taim.stopped")


def _resolve_cors_origins(vault_path: Path) -> list[str]:
    """Resolve CORS origins: ENV > YAML > defaults."""
    default_cors = ["http://localhost:5173", "http://localhost:3000"]
    env_cors = os.environ.get("TAIM_CORS_ORIGINS")
    if env_cors:
        return [o.strip() for o in env_cors.split(",") if o.strip()]

    yaml_path = vault_path.resolve() / "config" / "taim.yaml"
    if yaml_path.exists():
        try:
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            return raw.get("server", {}).get("cors_origins", default_cors)
        except yaml.YAMLError:
            pass

    return default_cors


def create_app() -> FastAPI:
    """Create and configure the TAIM FastAPI application."""
    settings = TaimSettings()
    cors_origins = _resolve_cors_origins(settings.vault_path)

    app = FastAPI(
        title="TAIM",
        description="Team AI Manager — AI team orchestration through natural language",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(chat_router)

    return app


app = create_app()
