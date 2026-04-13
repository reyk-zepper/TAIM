"""ToolRegistry — loads tool schema definitions from vault YAMLs."""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml
from pydantic import ValidationError

from taim.models.tool import Tool

logger = structlog.get_logger()


class ToolRegistry:
    """Loads tool schema definitions from taim-vault/system/tools/."""

    def __init__(self, tools_dir: Path) -> None:
        self._dir = tools_dir
        self._schemas: dict[str, Tool] = {}

    def load(self) -> None:
        self._schemas.clear()
        if not self._dir.exists():
            logger.warning("tool_registry.dir_missing", path=str(self._dir))
            return

        for yaml_file in sorted(self._dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
                tool = Tool(**data)
                self._schemas[tool.name] = tool
            except (yaml.YAMLError, ValidationError) as e:
                logger.warning(
                    "tool_registry.invalid_schema",
                    file=yaml_file.name,
                    error=str(e),
                )
        logger.info("tool_registry.loaded", count=len(self._schemas))

    def get_schema(self, name: str) -> Tool | None:
        return self._schemas.get(name)

    def list_schemas(self) -> list[Tool]:
        return list(self._schemas.values())
