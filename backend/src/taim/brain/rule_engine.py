"""RuleEngine — loads rules from vault YAML + memory, compiles for context injection."""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml
from pydantic import ValidationError

from taim.brain.memory import MemoryManager
from taim.models.rule import Rule, RuleSet, RuleSeverity

logger = structlog.get_logger()


class RuleEngine:
    """Loads rules from vault YAML + memory, compiles for context injection."""

    def __init__(
        self,
        rules_dir: Path,
        memory: MemoryManager | None = None,
    ) -> None:
        self._rules_dir = rules_dir
        self._memory = memory
        self._rules: list[Rule] = []

    def load(self) -> None:
        """Scan rules/ directory recursively for YAML files."""
        self._rules.clear()
        if not self._rules_dir.exists():
            logger.info("rule_engine.no_rules_dir", path=str(self._rules_dir))
            return

        for yaml_file in sorted(self._rules_dir.rglob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
                rule = Rule(**data)
                self._rules.append(rule)
            except (yaml.YAMLError, ValidationError) as e:
                logger.warning(
                    "rule_engine.invalid_rule",
                    file=str(yaml_file),
                    error=str(e),
                )
        logger.info("rule_engine.loaded", count=len(self._rules))

    async def load_memory_rules(self, user: str = "default") -> None:
        """Load rules from onboarding-captured memory entries."""
        if self._memory is None:
            return

        entry = await self._memory.read_entry("compliance-rules.md", user=user)
        if entry is None:
            return

        # Parse memory entry content into individual rule statements
        lines = [
            line.strip().lstrip("•-").strip()
            for line in entry.content.strip().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not lines:
            return

        memory_rule = Rule(
            name="onboarding-rules",
            description="Rules captured during onboarding",
            type="compliance",
            severity="mandatory",
            scope="global",
            rules=lines,
        )

        # Avoid duplicates
        existing_names = {r.name for r in self._rules}
        if memory_rule.name not in existing_names:
            self._rules.append(memory_rule)
            logger.info("rule_engine.memory_rules_loaded", count=len(lines))

    def get_active_rules(
        self,
        agent_name: str | None = None,
        task_type: str | None = None,
    ) -> RuleSet:
        """Return rules applicable to the current context."""
        mandatory = []
        advisory = []

        for rule in self._rules:
            # Scope filtering
            if rule.scope == "global":
                pass  # Always applies
            elif rule.scope.startswith("agent:") and agent_name:
                if rule.scope.split(":", 1)[1] != agent_name:
                    continue
            elif rule.scope.startswith("task_type:") and task_type:
                if rule.scope.split(":", 1)[1] != task_type:
                    continue
            else:
                # Scoped rule but no matching context provided — skip
                if rule.scope != "global":
                    continue

            if rule.severity == RuleSeverity.MANDATORY:
                mandatory.append(rule)
            else:
                advisory.append(rule)

        return RuleSet(mandatory=mandatory, advisory=advisory)

    def compile_for_context(self, rule_set: RuleSet) -> str:
        """Format rules as a string for context injection."""
        if not rule_set.mandatory and not rule_set.advisory:
            return ""

        lines: list[str] = []
        if rule_set.mandatory:
            lines.append("[RULES — you MUST follow these]")
            for rule in rule_set.mandatory:
                for r in rule.rules:
                    lines.append(f"• {r}")

        if rule_set.advisory:
            if lines:
                lines.append("")
            lines.append("[GUIDELINES — follow when possible]")
            for rule in rule_set.advisory:
                for r in rule.rules:
                    lines.append(f"• {r}")

        return "\n".join(lines)

    def list_rules(self) -> list[Rule]:
        return list(self._rules)
