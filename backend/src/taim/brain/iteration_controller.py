"""IterationController — smarter review decisions using rules and learnings."""

from __future__ import annotations

import structlog

from taim.brain.rule_engine import RuleEngine
from taim.models.agent import Agent, ReviewResult

logger = structlog.get_logger()

# Minimum quality threshold for each dimension
_MIN_COMPLETENESS = 0.6
_MIN_ACCURACY = 0.7
_MIN_RELEVANCE = 0.5


class IterationController:
    """Decides whether an agent should iterate based on review dimensions and rules."""

    def __init__(
        self,
        rule_engine: RuleEngine | None = None,
    ) -> None:
        self._rule_engine = rule_engine

    def should_iterate(
        self,
        review: ReviewResult,
        iteration: int,
        max_iterations: int,
        agent: Agent,
    ) -> tuple[bool, str]:
        """Decide if the agent should iterate. Returns (should_iterate, reason)."""
        # Hard stop: max iterations reached
        if iteration >= max_iterations:
            return False, f"max_iterations_reached_{max_iterations}"

        # Rule compliance failure is a mandatory iteration trigger
        if not review.rule_compliance:
            return True, "rule_compliance_failed"

        # If the LLM reviewer said quality_ok, trust it (unless dimensions are bad)
        if review.quality_ok:
            # But check dimensions — reviewer might say "ok" while dimensions are low
            if review.completeness < _MIN_COMPLETENESS:
                return True, f"completeness_low_{review.completeness:.1f}"
            if review.accuracy < _MIN_ACCURACY:
                return True, f"accuracy_low_{review.accuracy:.1f}"
            return False, "review_passed"

        # Reviewer said not ok — check if dimensions suggest iteration is worthwhile
        if review.completeness < _MIN_COMPLETENESS:
            return True, f"completeness_{review.completeness:.1f}"
        if review.accuracy < _MIN_ACCURACY:
            return True, f"accuracy_{review.accuracy:.1f}"
        if review.relevance < _MIN_RELEVANCE:
            return True, f"relevance_{review.relevance:.1f}"

        # Generic not-ok — iterate
        return True, "review_failed"

    def build_review_context(self, agent: Agent) -> str:
        """Build additional review context including active rules."""
        if self._rule_engine is None:
            return ""

        rule_set = self._rule_engine.get_active_rules(agent_name=agent.name)
        if not rule_set.mandatory:
            return ""

        lines = [
            "Additionally, verify the result follows these rules:",
        ]
        for rule in rule_set.mandatory:
            for r in rule.rules:
                lines.append(f"  - {r}")
        lines.append('\nInclude "rule_compliance": false in your JSON if any rule was violated.')
        return "\n".join(lines)
