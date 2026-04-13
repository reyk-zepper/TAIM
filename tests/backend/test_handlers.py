"""Tests for direct intent handlers (status, stop)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from taim.conversation.handlers import handle_status, handle_stop


@pytest.mark.asyncio
class TestHandleStatus:
    async def test_no_orchestrator_returns_placeholder(self) -> None:
        result = await handle_status(session_id="s1", orchestrator=None)
        assert "no active team" in result.lower()

    async def test_with_orchestrator_no_team(self) -> None:
        class StubOrch:
            async def get_status(self, session_id: str):
                return SimpleNamespace(has_team=False)
        result = await handle_status(session_id="s1", orchestrator=StubOrch())
        assert "no active team" in result.lower()

    async def test_with_orchestrator_active_team(self) -> None:
        class StubOrch:
            async def get_status(self, session_id: str):
                return SimpleNamespace(
                    has_team=True,
                    team_name="ResearchTeam",
                    agents=[SimpleNamespace(name="Researcher", state="EXECUTING", iteration=2)],
                    tokens_total=1500,
                    cost_eur=0.05,
                )
        result = await handle_status(session_id="s1", orchestrator=StubOrch())
        assert "ResearchTeam" in result
        assert "EXECUTING" in result
        assert "0.05" in result


@pytest.mark.asyncio
class TestHandleStop:
    async def test_no_orchestrator_returns_placeholder(self) -> None:
        result = await handle_stop(session_id="s1", orchestrator=None)
        assert "no active team" in result.lower() or "no team" in result.lower()

    async def test_with_orchestrator_stops_and_summarizes(self) -> None:
        class StubOrch:
            async def stop_team(self, session_id: str):
                return "Researcher completed 2 iterations"
        result = await handle_stop(session_id="s1", orchestrator=StubOrch())
        assert "stopped" in result.lower()
        assert "Researcher completed 2 iterations" in result
