"""Stage 2 — deep task understanding using Tier 2 model."""

from __future__ import annotations

import json

from taim.brain.prompts import PromptLoader
from taim.models.chat import IntentResult, TaskConstraints
from taim.models.router import ModelTierEnum


async def understand_task(
    message: str,
    recent_context: str,
    router,
    prompt_loader: PromptLoader,
    user_preferences: str = "",
    session_id: str | None = None,
) -> IntentResult:
    """Stage 2: Deep task extraction using Tier 2 model."""
    prompt = prompt_loader.load(
        "intent-interpreter",
        {
            "user_message": message,
            "recent_context": recent_context or "(none)",
            "user_preferences": user_preferences or "(no preferences yet)",
        },
    )
    response = await router.complete(
        messages=[{"role": "system", "content": prompt}],
        tier=ModelTierEnum.TIER2_STANDARD,
        expected_format="json",
        session_id=session_id,
    )
    data = json.loads(response.content)
    return IntentResult(
        task_type=data["task_type"],
        objective=data["objective"],
        parameters=data.get("parameters", {}),
        constraints=TaskConstraints(**data.get("constraints", {})),
        missing_info=data.get("missing_info", []),
        suggested_team=data.get("suggested_team", []),
    )
