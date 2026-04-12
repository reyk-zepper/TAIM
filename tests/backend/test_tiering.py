"""Tests for TierResolver."""

from taim.models.config import ProductConfig, ProviderConfig, TierConfig
from taim.models.router import ModelTierEnum
from taim.router.tiering import TierResolver


def _make_config() -> ProductConfig:
    return ProductConfig(
        providers=[
            ProviderConfig(name="anthropic", models=["claude-sonnet-4", "claude-haiku-4-5"], priority=1),
            ProviderConfig(name="openai", models=["gpt-4o", "gpt-4o-mini"], priority=2),
            ProviderConfig(name="ollama", models=["qwen2.5:32b"], priority=3),
        ],
        tiering={
            "tier1_premium": TierConfig(description="Complex", models=["claude-sonnet-4", "gpt-4o"]),
            "tier2_standard": TierConfig(description="Standard", models=["claude-haiku-4-5", "gpt-4o-mini"]),
            "tier3_economy": TierConfig(description="Cheap", models=["gpt-4o-mini", "qwen2.5:32b"]),
        },
        defaults={},
    )


class TestResolve:
    def test_tier1_returns_premium_models(self) -> None:
        resolver = TierResolver(_make_config())
        candidates = resolver.resolve(ModelTierEnum.TIER1_PREMIUM)
        assert candidates[0] == ("anthropic", "claude-sonnet-4")
        assert candidates[1] == ("openai", "gpt-4o")

    def test_tier3_returns_economy_models(self) -> None:
        resolver = TierResolver(_make_config())
        candidates = resolver.resolve(ModelTierEnum.TIER3_ECONOMY)
        providers = [c[0] for c in candidates]
        assert "openai" in providers
        assert "ollama" in providers

    def test_sorted_by_provider_priority(self) -> None:
        resolver = TierResolver(_make_config())
        candidates = resolver.resolve(ModelTierEnum.TIER2_STANDARD)
        assert candidates[0][0] == "anthropic"
        assert candidates[1][0] == "openai"

    def test_empty_config_returns_empty(self) -> None:
        config = ProductConfig(providers=[], tiering={}, defaults={})
        resolver = TierResolver(config)
        assert resolver.resolve(ModelTierEnum.TIER1_PREMIUM) == []
