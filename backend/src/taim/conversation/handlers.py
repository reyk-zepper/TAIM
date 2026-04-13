"""Direct intent handlers — no LLM calls."""

from __future__ import annotations

from typing import Protocol


class Orchestrator(Protocol):
    """Protocol for orchestrator dependency. Real implementation in Step 7."""

    async def get_status(self, session_id: str): ...
    async def stop_team(self, session_id: str) -> str: ...


async def handle_status(
    session_id: str,
    orchestrator: Orchestrator | None = None,
) -> str:
    """Status query — formatted text response, no LLM call."""
    if orchestrator is None:
        return "There's no active team right now."

    status = await orchestrator.get_status(session_id)
    if not status.has_team:
        return "There's no active team right now."

    lines = [f"Team status: {status.team_name}"]
    for agent in status.agents:
        lines.append(f"  • {agent.name}: {agent.state} (iteration {agent.iteration})")
    lines.append(f"Tokens used: {status.tokens_total}")
    lines.append(f"Cost so far: €{status.cost_eur:.4f}")
    return "\n".join(lines)


async def handle_stop(
    session_id: str,
    orchestrator: Orchestrator | None = None,
) -> str:
    """Stop command — triggers graceful stop on orchestrator."""
    if orchestrator is None:
        return "There's no active team to stop."

    summary = await orchestrator.stop_team(session_id)
    return f"Team stopped. Here's what was completed: {summary}"
