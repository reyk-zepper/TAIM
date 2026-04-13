"""Stage 1 — quick intent classification using Tier 3 model."""

from __future__ import annotations

import json

from taim.brain.prompts import PromptLoader
from taim.models.chat import IntentCategory, IntentClassification
from taim.models.router import ModelTierEnum

CONFIDENCE_THRESHOLD = 0.80


async def classify_intent(
    message: str,
    recent_context: str,
    router,
    prompt_loader: PromptLoader,
    session_id: str | None = None,
) -> IntentClassification:
    """Stage 1: Quick classification using Tier 3 model."""
    prompt = prompt_loader.load(
        "intent-classifier",
        {"user_message": message, "recent_context": recent_context or "(none)"},
    )
    response = await router.complete(
        messages=[{"role": "system", "content": prompt}],
        tier=ModelTierEnum.TIER3_ECONOMY,
        expected_format="json",
        session_id=session_id,
    )
    data = json.loads(response.content)
    return IntentClassification(
        category=IntentCategory(data["category"]),
        confidence=float(data["confidence"]),
        needs_deep_analysis=bool(data.get("needs_deep_analysis", False)),
    )
