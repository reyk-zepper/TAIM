"""tAIm FastAPI application — entry point."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

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

    # 7. Router init
    from taim.router import LLMRouter, LLMTransport, TierResolver, TokenTracker

    transport = LLMTransport()
    tier_resolver = TierResolver(product_config)
    tracker = TokenTracker(db)
    llm_router = LLMRouter(transport, tier_resolver, tracker, product_config)

    # 8. Memory System
    from taim.brain.hot_memory import HotMemory
    from taim.brain.memory import MemoryManager
    from taim.brain.session_store import SessionStore
    from taim.brain.summarizer import Summarizer

    memory_manager = MemoryManager(system_config.vault.users_dir)
    hot_memory = HotMemory()
    session_store = SessionStore(db)
    summarizer = Summarizer(llm_router, prompt_loader, memory_manager)

    app.state.memory = memory_manager
    app.state.hot_memory = hot_memory
    app.state.session_store = session_store
    app.state.summarizer = summarizer

    # 10. Agent Registry + Run Store
    from taim.brain.agent_registry import AgentRegistry
    from taim.brain.agent_run_store import AgentRunStore

    registry = AgentRegistry(system_config.vault.agents_dir)
    registry.load()
    agent_run_store = AgentRunStore(db)

    app.state.agent_registry = registry
    app.state.agent_run_store = agent_run_store

    logger.info("agents.loaded", count=len(registry.list_agents()))

    # 11. Tool System
    from taim.orchestrator.builtin_tools.file_io import file_read, file_write
    from taim.orchestrator.builtin_tools.memory_tools import (
        vault_memory_read,
        vault_memory_write,
    )
    from taim.orchestrator.tool_registry import ToolRegistry
    from taim.orchestrator.tools import ToolExecutor

    tool_registry = ToolRegistry(system_config.vault.vault_root / "system" / "tools")
    tool_registry.load()

    global_denylist = (
        product_config.defaults.get("tools", {}).get("global_denylist", [])
        if isinstance(product_config.defaults.get("tools"), dict)
        else []
    )
    tool_executor = ToolExecutor(
        registry=tool_registry,
        global_denylist=global_denylist,
    )
    tool_executor.register("file_read", file_read)
    tool_executor.register("file_write", file_write)
    tool_executor.register("vault_memory_read", vault_memory_read)
    tool_executor.register("vault_memory_write", vault_memory_write)

    app.state.tool_registry = tool_registry
    app.state.tool_executor = tool_executor
    app.state.tool_context = {
        "allowed_roots": [system_config.vault.vault_root],
        "memory_manager": memory_manager,
    }

    logger.info("tools.loaded", count=len(tool_executor.list_tools()))

    # 12. Skill Registry
    from taim.brain.skill_registry import SkillRegistry

    skill_registry = SkillRegistry(system_config.vault.vault_root / "system" / "skills")
    skill_registry.load()
    skill_registry.validate_against_tools(tool_registry)
    app.state.skill_registry = skill_registry
    logger.info("skills.loaded", count=len(skill_registry.list_skills()))

    # 9. Intent Interpreter — now with real memory
    from taim.conversation import IntentInterpreter

    interpreter = IntentInterpreter(
        router=llm_router,
        prompt_loader=prompt_loader,
        memory=memory_manager,
        orchestrator=None,  # Step 7 still
    )

    app.state.config = system_config
    app.state.db = db
    app.state.prompt_loader = prompt_loader
    app.state.router = llm_router
    app.state.interpreter = interpreter

    logger.info(
        "taim.started",
        vault=str(system_config.vault.vault_root),
        host=server_config.host,
        port=server_config.port,
        providers=[p.name for p in product_config.providers],
        tiers=list(product_config.tiering.keys()),
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
    """Create and configure the tAIm FastAPI application."""
    settings = TaimSettings()
    cors_origins = _resolve_cors_origins(settings.vault_path)

    app = FastAPI(
        title="tAIm",
        description="tAIm — Team AI Manager. AI team orchestration through natural language.",
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

    from taim.api.agents import router as agents_router

    app.include_router(agents_router)

    from taim.api.tools import router as tools_router

    app.include_router(tools_router)

    from taim.api.skills import router as skills_router

    app.include_router(skills_router)

    return app


app = create_app()
