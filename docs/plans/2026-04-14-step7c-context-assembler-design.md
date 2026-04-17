# Step 7c: Context Assembler — Design + Plan

> Version: 1.0
> Date: 2026-04-14
> Status: Reviewed
> Scope: US-5.2 (token-budgeted context assembly), US-4.2 pattern enum expansion

---

## 1. Overview

Step 7c adds the **Context Assembler** — the component that builds quality, budget-aware context for each agent by combining memory, constraints, and team context.

```
Before 7c: agent gets raw task_description + user_preferences text
After 7c:  agent gets assembled context within token budget:
           task_description (always)
           + constraints (if any)
           + relevant memory entries (scored by keyword/tag matching)
           + previous agent results (if team execution)
           all within the tier's token budget
```

**Deliverables:**
1. `brain/context_assembler.py` — ContextAssembler class
2. Wire into Orchestrator: both `execute()` and `execute_team()` use assembled context
3. Pattern enum expansion: PARALLEL, PIPELINE, HIERARCHICAL in OrchestrationPattern (enum only, no implementation — Sequential is MVP)
4. Tests for context assembly, budget enforcement, memory integration

**Not implementing in 7c:**
- Parallel/Pipeline/Hierarchical orchestration loop (Sequential covers MVP)
- LLM-based team composition (rule-based covers 80%)
- Few-shot examples from prompt cache (Phase 2)

---

## 2. Context Assembler (`brain/context_assembler.py`)

```python
"""ContextAssembler — builds token-budgeted context for agents."""

from __future__ import annotations

import tiktoken

import structlog

from taim.brain.memory import MemoryManager
from taim.models.agent import Agent
from taim.models.chat import TaskConstraints

logger = structlog.get_logger()

# Token budgets per tier (AD-4)
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
    """Builds token-budgeted context for agent execution (AD-4)."""

    def __init__(self, memory: MemoryManager | None = None) -> None:
        self._memory = memory

    async def assemble(
        self,
        agent: Agent,
        task_description: str,
        user: str = "default",
        constraints: TaskConstraints | None = None,
        previous_results: list[tuple[str, str]] | None = None,  # [(agent_name, result)]
    ) -> str:
        """Build prioritized context within token budget.

        Priority order (AD-4):
        1. Constraints (mandatory if present)
        2. Relevant memory entries (scored by keyword/tag matching)
        3. Previous agent results (if team execution, truncated)

        Returns assembled context string to pass as user_preferences.
        """
        tier = agent.model_preference[0] if agent.model_preference else "tier2_standard"
        budget = _TIER_BUDGETS.get(tier, 2000)
        used = 0
        parts: list[str] = []

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

        # 3. Previous agent results (team context)
        if previous_results:
            for agent_name, result in previous_results:
                truncated = result[:4000]  # ~1000 tokens hard cap
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
        # Add agent skills as keywords
        words.extend(s.lower() for s in agent.skills)
        # Filter short words and deduplicate
        return list({w for w in words if len(w) > 3})[:20]
```

---

## 3. Orchestrator Integration

### 3.1 Update `execute()` (single-agent)

Replace raw `user_preferences` with assembled context:

```python
# Before: user_preferences from chat handler
# After:
context = await self._context_assembler.assemble(
    agent=agent,
    task_description=task_description,
    constraints=intent.constraints if hasattr(intent, 'constraints') else None,
)
# Pass assembled context as user_preferences
sm = AgentStateMachine(
    ...
    user_preferences=context or user_preferences,  # fallback to raw if assembler returns empty
    ...
)
```

### 3.2 Update `execute_team()` (sequential)

Replace the raw `previous_result[:4000]` truncation with Context Assembler:

```python
previous_results: list[tuple[str, str]] = []

for slot in plan.agents:
    context = await self._context_assembler.assemble(
        agent=agent,
        task_description=base_task_description,
        constraints=intent.constraints if hasattr(intent, 'constraints') else None,
        previous_results=previous_results,
    )
    sm = AgentStateMachine(
        ...
        user_preferences=context,
        ...
    )
    run = await sm.run()
    previous_results.append((slot.agent_name, run.result_content))
```

### 3.3 Orchestrator constructor update

```python
def __init__(
    self,
    ...
    context_assembler: ContextAssembler | None = None,
):
    self._context_assembler = context_assembler or ContextAssembler()
```

---

## 4. Pattern Enum Expansion

Add to `models/orchestration.py`:

```python
class OrchestrationPattern(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"           # Phase 2 implementation
    PIPELINE = "pipeline"           # Phase 2 implementation
    HIERARCHICAL = "hierarchical"   # Phase 2 implementation
```

No orchestration loop changes — sequential remains the only implemented pattern. The enum allows agent/team YAML files to reference future patterns without code changes.

---

## 5. Tests

| Test File | Tests |
|-----------|-------|
| `test_context_assembler.py` | Budget enforcement, memory retrieval, constraints formatting, previous results, empty memory, keyword extraction, budget overflow stops |
| `test_orchestrator.py` (extend) | Verify assembled context flows to agent, memory entries in context |

---

## 6. Implementation Tasks

### Task 1: ContextAssembler + Tests

- Create `brain/context_assembler.py`
- Create `tests/backend/test_context_assembler.py`
- Test: budget limits, memory integration, constraints, previous results, empty cases

### Task 2: Wire into Orchestrator + Pattern Enum + Verify

- Update `orchestrator/orchestrator.py`: use ContextAssembler in execute() and execute_team()
- Update `models/orchestration.py`: expand OrchestrationPattern enum
- Update `main.py`: create ContextAssembler in lifespan
- Run tests + lint + smoke test

---

*End of Step 7c Design.*
