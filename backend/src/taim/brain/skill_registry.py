"""SkillRegistry — loads skill YAMLs and validates against ToolRegistry."""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml
from pydantic import ValidationError

from taim.models.skill import Skill
from taim.orchestrator.tool_registry import ToolRegistry

logger = structlog.get_logger()


class SkillRegistry:
    """In-memory registry of skills loaded from taim-vault/system/skills/."""

    def __init__(self, skills_dir: Path) -> None:
        self._dir = skills_dir
        self._skills: dict[str, Skill] = {}

    def load(self) -> None:
        self._skills.clear()
        if not self._dir.exists():
            logger.warning("skill_registry.dir_missing", path=str(self._dir))
            return

        for yaml_file in sorted(self._dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
                skill = Skill(**data)
                self._skills[skill.name] = skill
            except (yaml.YAMLError, ValidationError) as e:
                logger.warning(
                    "skill_registry.invalid_skill",
                    file=yaml_file.name,
                    error=str(e),
                )
        logger.info("skill_registry.loaded", count=len(self._skills))

    def validate_against_tools(self, tool_registry: ToolRegistry) -> None:
        """Log warnings for skills referencing unregistered tools."""
        for skill in self._skills.values():
            for tool_name in skill.required_tools:
                if tool_registry.get_schema(tool_name) is None:
                    logger.warning(
                        "skill_registry.unknown_tool",
                        skill=skill.name,
                        tool=tool_name,
                    )

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())
