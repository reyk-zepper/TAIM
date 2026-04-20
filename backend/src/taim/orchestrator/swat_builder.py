"""SWAT Builder — LLM-assisted dynamic team composition."""

from __future__ import annotations

import json

import structlog

from taim.brain.agent_registry import AgentRegistry
from taim.brain.prompts import PromptLoader
from taim.models.chat import IntentResult
from taim.models.orchestration import TeamAgentSlot
from taim.models.router import ModelTierEnum
from taim.orchestrator.team_composer import TeamComposer

logger = structlog.get_logger()


class SwatBuilder:
    """Dynamically composes teams using LLM analysis + registry awareness.

    Falls back to rule-based TeamComposer if LLM is unavailable or fails.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        router,
        prompt_loader: PromptLoader,
        fallback_composer: TeamComposer,
    ) -> None:
        self._registry = registry
        self._router = router
        self._prompts = prompt_loader
        self._fallback = fallback_composer

    async def build_team(self, intent: IntentResult) -> list[TeamAgentSlot]:
        """Build a team dynamically. Falls back to rules on failure."""
        # If user explicitly suggested agents, honor that
        if intent.suggested_team:
            slots = []
            for name in intent.suggested_team:
                if self._registry.get_agent(name):
                    slots.append(TeamAgentSlot(role=name, agent_name=name))
            if slots:
                return slots

        # Try LLM-based composition
        try:
            return await self._build_with_llm(intent)
        except Exception:
            logger.warning("swat_builder.llm_failed_using_fallback")
            return self._fallback.compose_team(intent)

    async def _build_with_llm(self, intent: IntentResult) -> list[TeamAgentSlot]:
        """Use a Tier 3 LLM to propose a team."""
        available_agents = self._registry.list_agents()
        if not available_agents:
            return []

        agent_descriptions = "\n".join(
            f"- {a.name}: {a.description} (skills: {', '.join(a.skills)})" for a in available_agents
        )

        try:
            prompt = self._prompts.load(
                "team-composer",
                {
                    "task_type": intent.task_type,
                    "objective": intent.objective,
                    "available_agents": agent_descriptions,
                    "parameters": json.dumps(intent.parameters) if intent.parameters else "none",
                },
            )
        except Exception:
            logger.warning("swat_builder.prompt_missing")
            return self._fallback.compose_team(intent)

        response = await self._router.complete(
            messages=[{"role": "system", "content": prompt}],
            tier=ModelTierEnum.TIER3_ECONOMY,
            expected_format="json",
        )

        data = json.loads(response.content)
        agents_data = data.get("agents", [])
        if not agents_data:
            return self._fallback.compose_team(intent)

        slots = []
        for entry in agents_data:
            name = entry.get("agent_name") or entry.get("name", "")
            role = entry.get("role", name)
            if self._registry.get_agent(name):
                slots.append(TeamAgentSlot(role=role, agent_name=name))

        return slots if slots else self._fallback.compose_team(intent)
