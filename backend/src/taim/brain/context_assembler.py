"""ContextAssembler — builds token-budgeted context for agents (AD-4)."""

from __future__ import annotations

import structlog
import tiktoken

from taim.brain.few_shot_store import FewShotStore
from taim.brain.memory import MemoryManager
from taim.brain.rule_engine import RuleEngine
from taim.models.agent import Agent
from taim.models.chat import TaskConstraints

logger = structlog.get_logger()

_TIER_BUDGETS = {
    "tier1_premium": 4000,
    "tier2_standard": 2000,
    "tier3_economy": 800,
}

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens using cl100k_base encoding."""
    return len(_ENCODING.encode(text))


class ContextAssembler:
    """Builds token-budgeted context for agent execution (AD-4).

    Priority order:
    1. Constraints (mandatory if present)
    2. Relevant memory entries (scored by keyword/tag matching)
    3. Previous agent results (if team execution, truncated)
    """

    def __init__(
        self,
        memory: MemoryManager | None = None,
        rule_engine: RuleEngine | None = None,
        few_shot_store: FewShotStore | None = None,
    ) -> None:
        self._memory = memory
        self._rule_engine = rule_engine
        self._few_shot_store = few_shot_store

    async def assemble(
        self,
        agent: Agent,
        task_description: str,
        user: str = "default",
        constraints: TaskConstraints | None = None,
        previous_results: list[tuple[str, str]] | None = None,
    ) -> str:
        """Build prioritized context within token budget.

        Returns assembled context string.
        """
        tier = agent.model_preference[0] if agent.model_preference else "tier2_standard"
        budget = _TIER_BUDGETS.get(tier, 2000)
        used = 0
        parts: list[str] = []

        # 0. Active rules (highest priority)
        if self._rule_engine:
            rule_set = self._rule_engine.get_active_rules(
                agent_name=agent.name,
            )
            rules_text = self._rule_engine.compile_for_context(rule_set)
            if rules_text:
                tokens = count_tokens(rules_text)
                if used + tokens <= budget:
                    parts.append(rules_text)
                    used += tokens

        # 1. Constraints
        if constraints:
            constraint_text = self._format_constraints(constraints)
            if constraint_text:
                tokens = count_tokens(constraint_text)
                if used + tokens <= budget:
                    parts.append(constraint_text)
                    used += tokens

        # 2. Relevant memory entries
        if self._memory:
            keywords = self._extract_keywords(task_description, agent)
            try:
                relevant = await self._memory.find_relevant(keywords, user=user)
                for entry_ref in relevant:
                    entry = await self._memory.read_entry(entry_ref.filename, user=user)
                    if not entry:
                        continue
                    entry_text = f"[Memory: {entry.title}]\n{entry.content}"
                    tokens = count_tokens(entry_text)
                    if used + tokens > budget:
                        break
                    parts.append(entry_text)
                    used += tokens
            except Exception:
                logger.exception("context_assembler.memory_error")

        # 2.5 Few-shot examples (between memory and team context)
        if self._few_shot_store and agent.skills:
            try:
                task_type_hint = task_description.split()[0].lower() if task_description else ""
                examples = await self._few_shot_store.find_examples(
                    task_type=task_type_hint,
                    agent_name=agent.name,
                )
                for i, example in enumerate(examples):
                    example_text = f"[Example {i + 1}]\n{example}"
                    tokens = count_tokens(example_text)
                    if used + tokens > budget:
                        break
                    parts.append(example_text)
                    used += tokens
            except Exception:
                logger.exception("context_assembler.few_shot_error")

        # 3. Previous agent results (team context)
        if previous_results:
            for agent_name, result in previous_results:
                truncated = result[:4000]
                result_text = f"[Previous: {agent_name}]\n{truncated}"
                tokens = count_tokens(result_text)
                if used + tokens > budget:
                    break
                parts.append(result_text)
                used += tokens

        context = "\n\n".join(parts)
        logger.debug(
            "context.assembled",
            agent=agent.name,
            tier=tier,
            budget=budget,
            used=used,
            parts=len(parts),
        )
        return context

    def _format_constraints(self, constraints: TaskConstraints) -> str:
        lines = []
        if constraints.time_limit_seconds:
            minutes = constraints.time_limit_seconds / 60
            lines.append(f"Time limit: {minutes:.0f} minutes")
        if constraints.budget_eur:
            lines.append(f"Budget limit: €{constraints.budget_eur:.2f}")
        if constraints.specific_agents:
            lines.append(f"Required agents: {', '.join(constraints.specific_agents)}")
        return "[Constraints]\n" + "\n".join(lines) if lines else ""

    def _extract_keywords(self, task_description: str, agent: Agent) -> list[str]:
        """Extract keywords from task + agent for memory retrieval."""
        words = task_description.lower().split()
        words.extend(s.lower() for s in agent.skills)
        return list({w for w in words if len(w) > 3})[:20]
