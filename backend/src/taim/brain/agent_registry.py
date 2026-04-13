"""AgentRegistry — loads agent YAML definitions from the vault."""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml
from pydantic import ValidationError

from taim.models.agent import Agent

logger = structlog.get_logger()


class AgentRegistry:
    """In-memory registry of agent definitions loaded from taim-vault/agents/."""

    def __init__(self, agents_dir: Path) -> None:
        self._agents_dir = agents_dir
        self._agents: dict[str, Agent] = {}

    def load(self) -> None:
        """Scan agents_dir and load all valid YAML agent definitions."""
        self._agents.clear()
        if not self._agents_dir.exists():
            logger.warning("registry.agents_dir_missing", path=str(self._agents_dir))
            return

        for yaml_file in sorted(self._agents_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
                agent = Agent(**data)
                self._agents[agent.name] = agent
            except (yaml.YAMLError, ValidationError) as e:
                logger.warning(
                    "registry.invalid_agent",
                    file=yaml_file.name,
                    error=str(e),
                )
        logger.info("registry.loaded", count=len(self._agents))

    def reload(self) -> None:
        """Manual reload (US-3.2 AC5 P1 sub-feature). File watcher is future work."""
        self.load()

    def get_agent(self, name: str) -> Agent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[Agent]:
        return list(self._agents.values())

    def find_by_skill(self, skill: str) -> list[Agent]:
        skill_lower = skill.lower()
        return [a for a in self._agents.values() if skill_lower in [s.lower() for s in a.skills]]
