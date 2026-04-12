"""TierResolver — maps ModelTierEnum to (provider, model) candidates."""

from __future__ import annotations

from taim.models.config import ProductConfig
from taim.models.router import ModelTierEnum


class TierResolver:
    """Maps a tier to an ordered list of (provider_name, model_name) candidates."""

    def __init__(self, product_config: ProductConfig) -> None:
        self._providers = sorted(product_config.providers, key=lambda p: p.priority)
        self._tiering = product_config.tiering

    def resolve(self, tier: ModelTierEnum) -> list[tuple[str, str]]:
        """Return (provider, model) pairs for the tier, sorted by provider priority."""
        tier_config = self._tiering.get(tier.value)
        if not tier_config:
            return []

        tier_models = set(tier_config.models)
        candidates: list[tuple[str, str]] = []

        for provider in self._providers:
            for model in provider.models:
                if model in tier_models:
                    candidates.append((provider.name, model))

        return candidates
