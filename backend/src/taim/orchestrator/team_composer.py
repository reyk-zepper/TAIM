"""TeamComposer — rule-based agent selection for Step 7a/7b."""

from __future__ import annotations

from taim.brain.agent_registry import AgentRegistry
from taim.models.agent import Agent
from taim.models.chat import IntentResult
from taim.models.orchestration import TeamAgentSlot

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

# Rule-based mapping: task_type substring → team definition (role, agent_name) pairs
_TASK_TYPE_TO_TEAM: dict[str, list[tuple[str, str]]] = {
    "code_review": [("reviewer", "reviewer")],
    "code_generation": [("coder", "coder"), ("reviewer", "reviewer")],
    "code": [("coder", "coder"), ("reviewer", "reviewer")],
    "data_analysis": [("analyst", "analyst")],
    "content_writing": [("writer", "writer")],
    "content": [("writer", "writer")],
    "writing": [("researcher", "researcher"), ("writer", "writer")],
    "research": [("researcher", "researcher"), ("analyst", "analyst")],
    "analysis": [("analyst", "analyst"), ("researcher", "researcher")],
}


class TeamComposer:
    """Selects agents for a task. Rule-based in 7a/7b; LLM-based in 7c."""

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

    def compose_team(self, intent: IntentResult) -> list[TeamAgentSlot]:
        """Select multiple agents for a task. Falls back to single if needed."""
        # 1) Explicit suggestion
        if intent.suggested_team:
            slots = []
            for name in intent.suggested_team:
                if self._registry.get_agent(name):
                    slots.append(TeamAgentSlot(role=name, agent_name=name))
            if slots:
                return slots

        # 2) Rule-based team by task_type
        task_type_lower = (intent.task_type or "").lower()
        for pattern, team_def in _TASK_TYPE_TO_TEAM.items():
            if pattern in task_type_lower:
                slots = []
                for role, agent_name in team_def:
                    if self._registry.get_agent(agent_name):
                        slots.append(TeamAgentSlot(role=role, agent_name=agent_name))
                if slots:
                    return slots

        # 3) Fallback to single agent
        agent = self.compose_single_agent(intent)
        if agent:
            return [TeamAgentSlot(role="primary", agent_name=agent.name)]
        return []
