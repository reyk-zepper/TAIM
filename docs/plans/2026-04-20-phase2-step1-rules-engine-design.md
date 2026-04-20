# Phase 2, Step 1: Rules Engine — Design

> Version: 1.0
> Date: 2026-04-20
> Status: Reviewed
> Phase: 2 — Intelligence

---

## 1. Overview

The Rules Engine gives tAIm configurable constraints that ALL agent outputs must respect. Rules come from two sources:

1. **Onboarding-captured rules** — already stored as memory entries (`compliance-rules.md`)
2. **YAML-defined rules** — power users drop YAML files in `taim-vault/rules/`

Rules are injected into the Context Assembler as **highest priority after task description** — before memory, before examples, before team context. An agent cannot ignore a rule because it's always in its context.

```
Before Rules Engine:
  Context = [constraints] + [memory] + [team context]

After Rules Engine:
  Context = [ACTIVE RULES] + [constraints] + [memory] + [team context]
```

## 2. Rule Types

```yaml
# taim-vault/rules/compliance/gdpr.yaml
name: gdpr-compliance
description: GDPR data protection rules
type: compliance        # compliance | behavior | output
severity: mandatory     # mandatory (always enforced) | advisory (warn if violated)
scope: global           # global | agent:{name} | task_type:{type}
rules:
  - Never include personal customer data in outputs
  - Never store PII outside the vault
  - Always anonymize names in examples
  - If asked to process customer data, remind user of GDPR requirements
```

```yaml
# taim-vault/rules/behavior/style.yaml
name: formal-style
description: Communication style rules
type: behavior
severity: advisory
scope: global
rules:
  - Use formal "Sie" in German texts
  - Prefer active voice over passive
  - Keep sentences under 25 words
```

## 3. Data Model (`models/rule.py`)

```python
from enum import Enum
from pydantic import BaseModel


class RuleType(str, Enum):
    COMPLIANCE = "compliance"
    BEHAVIOR = "behavior"
    OUTPUT = "output"


class RuleSeverity(str, Enum):
    MANDATORY = "mandatory"
    ADVISORY = "advisory"


class RuleScope(str, Enum):
    GLOBAL = "global"
    # Future: AGENT_SPECIFIC = "agent:{name}", TASK_TYPE = "task_type:{type}"


class Rule(BaseModel):
    name: str
    description: str
    type: RuleType = RuleType.COMPLIANCE
    severity: RuleSeverity = RuleSeverity.MANDATORY
    scope: str = "global"
    rules: list[str]                  # Individual rule statements


class RuleSet(BaseModel):
    """All active rules, compiled for injection."""
    mandatory: list[Rule] = []
    advisory: list[Rule] = []
```

## 4. RuleEngine (`brain/rule_engine.py`)

```python
class RuleEngine:
    """Loads rules from vault YAML + memory, compiles for context injection."""

    def __init__(self, rules_dir: Path, memory: MemoryManager | None = None):
        self._rules_dir = rules_dir
        self._memory = memory
        self._rules: list[Rule] = []

    def load(self) -> None:
        """Scan rules/ directory recursively for YAML files."""
        ...

    async def load_memory_rules(self, user: str = "default") -> None:
        """Load rules from onboarding-captured memory entries."""
        # Read compliance-rules.md from memory
        # Parse into Rule objects
        ...

    def get_active_rules(self, agent_name: str | None = None, task_type: str | None = None) -> RuleSet:
        """Return rules applicable to the current context."""
        ...

    def compile_for_context(self, rule_set: RuleSet) -> str:
        """Format rules as a string for context injection."""
        lines = ["[RULES — you MUST follow these]\n"]
        for rule in rule_set.mandatory:
            for r in rule.rules:
                lines.append(f"• {r}")
        if rule_set.advisory:
            lines.append("\n[GUIDELINES — follow when possible]")
            for rule in rule_set.advisory:
                for r in rule.rules:
                    lines.append(f"• {r}")
        return "\n".join(lines)
```

## 5. Context Assembler Integration

In `brain/context_assembler.py`, add rules as **priority 0** (before constraints):

```python
async def assemble(self, agent, task_description, ...):
    # 0. Active rules (NEW — highest priority)
    if self._rule_engine:
        rule_set = self._rule_engine.get_active_rules(
            agent_name=agent.name,
            task_type=task_type,
        )
        rules_text = self._rule_engine.compile_for_context(rule_set)
        if rules_text:
            tokens = count_tokens(rules_text)
            if used + tokens <= budget:
                parts.append(rules_text)
                used += tokens

    # 1. Constraints (existing)
    # 2. Memory (existing)
    # 3. Team context (existing)
```

## 6. Built-in Default Rules

Seed via VaultOps:

```yaml
# taim-vault/rules/compliance/default.yaml
name: default-safety
description: Default safety and quality rules
type: compliance
severity: mandatory
scope: global
rules:
  - Never fabricate sources or citations — if you don't have real data, say so
  - Never execute destructive operations without explicit user confirmation
  - Always respect user-specified time and budget limits
  - If unsure about a task requirement, ask rather than guess
```

## 7. API

- `GET /api/rules` — list all active rules with type/severity/scope
- `POST /api/rules/reload` — reload from vault (for power users editing YAML)

## 8. Implementation Tasks

### Task 1: Rule models + RuleEngine + Tests
### Task 2: Context Assembler integration + Vault seeding + API + Verify

---

*End of Phase 2 Step 1 Design.*
