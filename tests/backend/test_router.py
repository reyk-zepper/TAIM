"""Tests for LLMRouter — orchestrates calls with failover."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.database import init_database
from taim.errors import AllProvidersFailed, ConfigError, LLMTransportError
from taim.models.config import ProductConfig, ProviderConfig, TierConfig
from taim.models.router import LLMErrorType, ModelTierEnum
from taim.router.router import LLMRouter
from taim.router.tiering import TierResolver
from taim.router.tracking import TokenTracker

from backend.conftest import MockTransport, make_response


def _config() -> ProductConfig:
    return ProductConfig(
        providers=[
            ProviderConfig(name="primary", api_key_env="PRIMARY_KEY", models=["model-a"], priority=1),
            ProviderConfig(name="secondary", api_key_env="SECONDARY_KEY", models=["model-b"], priority=2),
        ],
        tiering={"tier2_standard": TierConfig(description="Standard", models=["model-a", "model-b"])},
        defaults={},
    )


@pytest_asyncio.fixture
async def db(tmp_path: Path):
    conn = await init_database(tmp_path / "taim.db")
    yield conn
    await conn.close()


def _make_router(transport, config=None, db=None) -> LLMRouter:
    cfg = config or _config()
    tracker = TokenTracker(db) if db else None
    return LLMRouter(
        transport=transport,
        tier_resolver=TierResolver(cfg),
        tracker=tracker,
        product_config=cfg,
    )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_returns_response(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "test-key")
        transport = MockTransport([make_response("hello")])
        router = _make_router(transport, db=db)
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
        )
        assert result.content == "hello"
        assert result.attempts == 1
        assert result.failover_occurred is False

    async def test_tracks_tokens(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "test-key")
        transport = MockTransport([make_response()])
        router = _make_router(transport, db=db)
        await router.complete(messages=[{"role": "user", "content": "hi"}], tier=ModelTierEnum.TIER2_STANDARD)
        async with db.execute("SELECT COUNT(*) FROM token_tracking") as cur:
            assert (await cur.fetchone())[0] == 1


@pytest.mark.asyncio
class TestFailover:
    async def test_failover_on_provider_down(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k1")
        monkeypatch.setenv("SECONDARY_KEY", "k2")
        transport = MockTransport([
            LLMTransportError(LLMErrorType.PROVIDER_DOWN, "refused"),
            make_response("from secondary"),
        ])
        router = _make_router(transport, db=db)
        result = await router.complete(messages=[{"role": "user", "content": "hi"}], tier=ModelTierEnum.TIER2_STANDARD)
        assert result.content == "from secondary"
        assert result.failover_occurred is True
        assert result.attempts == 2

    async def test_auth_error_skips_without_counting(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "bad")
        monkeypatch.setenv("SECONDARY_KEY", "good")
        transport = MockTransport([
            LLMTransportError(LLMErrorType.AUTH_ERROR, "401"),
            make_response("from secondary"),
        ])
        router = _make_router(transport, db=db)
        result = await router.complete(messages=[{"role": "user", "content": "hi"}], tier=ModelTierEnum.TIER2_STANDARD)
        assert result.content == "from secondary"
        assert result.attempts == 1  # Auth skip doesn't count


@pytest.mark.asyncio
class TestMaxAttempts:
    async def test_all_providers_failed(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k1")
        monkeypatch.setenv("SECONDARY_KEY", "k2")
        transport = MockTransport([
            LLMTransportError(LLMErrorType.PROVIDER_DOWN, "d"),
            LLMTransportError(LLMErrorType.PROVIDER_DOWN, "d"),
            LLMTransportError(LLMErrorType.PROVIDER_DOWN, "d"),
        ])
        router = _make_router(transport, db=db)
        with pytest.raises(AllProvidersFailed):
            await router.complete(messages=[{"role": "user", "content": "hi"}], tier=ModelTierEnum.TIER2_STANDARD)


@pytest.mark.asyncio
class TestJsonValidation:
    async def test_valid_json_passes(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k")
        transport = MockTransport([make_response('{"key": "value"}')])
        router = _make_router(transport, db=db)
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
            expected_format="json",
        )
        assert result.content == '{"key": "value"}'

    async def test_invalid_json_retries_with_reminder(self, db, monkeypatch) -> None:
        monkeypatch.setenv("PRIMARY_KEY", "k")
        transport = MockTransport([
            make_response("not json"),
            make_response('{"fixed": true}'),
        ])
        router = _make_router(transport, db=db)
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            tier=ModelTierEnum.TIER2_STANDARD,
            expected_format="json",
        )
        assert result.content == '{"fixed": true}'
        assert result.attempts == 2


@pytest.mark.asyncio
class TestNoCandidates:
    async def test_raises_config_error(self, db) -> None:
        config = ProductConfig(providers=[], tiering={}, defaults={})
        transport = MockTransport([])
        router = _make_router(transport, config=config, db=db)
        with pytest.raises(ConfigError):
            await router.complete(messages=[{"role": "user", "content": "hi"}], tier=ModelTierEnum.TIER2_STANDARD)
