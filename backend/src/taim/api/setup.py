"""Setup REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from taim.api.deps import get_config
from taim.models.config import SystemConfig

router = APIRouter(prefix="/api/setup")


@router.post("/init")
async def init_setup(config: SystemConfig = Depends(get_config)) -> dict:
    """Trigger re-onboarding by removing user profile."""
    profile_path = config.vault.users_dir / "default" / "memory" / "user-profile.md"
    if profile_path.exists():
        profile_path.unlink()
    return {"status": "reset", "message": "Onboarding will trigger on next WebSocket connect."}
