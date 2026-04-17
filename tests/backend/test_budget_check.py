"""Tests for pre-call budget check in LLMRouter."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.database import init_database
from taim.errors import AllProvidersFailed
from taim.models.config import ProductConfig, ProviderConfig, TierConfig
from taim.models.router import ModelTierEnum, TokenUsage
from taim.router.router import LLMRouter
from taim.router.tiering import TierResolver
from taim.router.tracking import TokenTracker

from conftest import MockTransport, make_response


@pytest_asyncio.fixture
async def db(tmp_path: Path):
    conn = await init_database(tmp_path / "taim.db")
    yield conn
    await conn.close()


@pytest.mark.asyncio
class TestBudgetCheck:
    async def test_skips_provider_over_budget(self, db, monkeypatch) -> None:
        """Provider with exceeded budget is skipped, falls to next."""
        monkeypatch.setenv("PRIMARY_KEY", "k1")
        monkeypatch.setenv("SECONDARY_KEY", "k2")

        config = ProductConfig(
            providers=[
                ProviderConfig(
                    name="primary", api_key_env="PRIMARY_KEY",
                    models=["m1"], priority=1,
                    monthly_budget_eur=0.01,  # Very low budget
                ),
                ProviderConfig(
                    name="secondary", api_key_env="SECONDARY_KEY",
                    models=["m1"], priority=2,
                    monthly_budget_eur=None,  # No budget limit
                ),
            ],
            tiering={"tier2_standard": TierConfig(description="S", models=["m1"])},
            defaults={},
        )

        tracker = TokenTracker(db)
        # Record past usage that exceeds primary's budget
        await tracker.record(TokenUsage(
            call_id="old-1", model="m1", provider="primary",
            prompt_tokens=1000, completion_tokens=500, cost_usd=0.02,  # > 0.01/0.92
        ))

        transport = MockTransport([make_response("from secondary")])
        router = LLMRouter(
            transport=transport,
            tier_resolver=TierResolver(config),
            tracker=tracker,
            product_config=config,
        )

        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
        )
        # Should have skipped primary, used secondary
        assert transport.calls[0]["provider"] == "secondary"

    async def test_no_budget_no_skip(self, db, monkeypatch) -> None:
        """Provider without monthly_budget_eur is never skipped."""
        monkeypatch.setenv("PRIMARY_KEY", "k1")

        config = ProductConfig(
            providers=[
                ProviderConfig(
                    name="primary", api_key_env="PRIMARY_KEY",
                    models=["m1"], priority=1,
                    monthly_budget_eur=None,  # No budget
                ),
            ],
            tiering={"tier2_standard": TierConfig(description="S", models=["m1"])},
            defaults={},
        )

        tracker = TokenTracker(db)
        transport = MockTransport([make_response("ok")])
        router = LLMRouter(
            transport=transport,
            tier_resolver=TierResolver(config),
            tracker=tracker,
            product_config=config,
        )

        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
        )
        assert result.content == "ok"
