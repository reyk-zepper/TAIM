"""Health check endpoint."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends

from taim.api.deps import get_config, get_db
from taim.models.config import SystemConfig

router = APIRouter()


@router.get("/health")
async def health(
    config: SystemConfig = Depends(get_config),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """Health check — reports vault, DB, and provider status."""
    provider_names = [p.name for p in config.product.providers]
    vault_ok = config.vault.vault_root.is_dir()

    try:
        async with db.execute("SELECT 1") as cursor:
            await cursor.fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    all_ok = vault_ok and db_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "vault_ok": vault_ok,
        "db_ok": db_ok,
        "providers": provider_names,
        "version": "0.1.0",
    }
