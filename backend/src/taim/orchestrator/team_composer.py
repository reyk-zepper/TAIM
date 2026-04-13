"""TeamComposer — rule-based agent selection for Step 7a."""

from __future__ import annotations

from taim.brain.agent_registry import AgentRegistry
from taim.models.agent import Agent
from taim.models.chat import IntentResult


# Rule-based mapping: task_type substring → agent priority list
_TASK_TYPE_TO_AGENTS = {
    "code_review": ["reviewer", "coder"],
    "code_generation": ["coder"],
    "code": ["coder", "reviewer"],
    "data_analysis": ["analyst"],
    "analysis": ["analyst", "researcher"],
    "content_writing": ["writer"],
    "content": ["writer"],
    "writing": ["writer", "researcher"],
    "research": ["researcher", "analyst"],
}


class TeamComposer:
    """Selects agents for a task. Rule-based in 7a; LLM-based in 7c."""

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    def compose_single_agent(self, intent: IntentResult) -> Agent | None:
        """Return the best matching single agent for this task. None if none suitable."""
        # 1) Explicit suggestion from intent wins
        for name in intent.suggested_team or []:
            agent = self._registry.get_agent(name)
            if agent:
                return agent

        # 2) Rule-based by task_type
        task_type_lower = (intent.task_type or "").lower()
        for pattern, candidates in _TASK_TYPE_TO_AGENTS.items():
            if pattern in task_type_lower:
                for candidate in candidates:
                    agent = self._registry.get_agent(candidate)
                    if agent:
                        return agent

        # 3) Skill-based fallback
        keywords = task_type_lower.split("_") + intent.objective.lower().split()
        keywords = [k for k in keywords if len(k) > 3]
        for agent in self._registry.list_agents():
            for skill in agent.skills:
                if any(kw in skill.lower() for kw in keywords):
                    return agent

        # 4) Last resort: any available agent
        agents = self._registry.list_agents()
        return agents[0] if agents else None
