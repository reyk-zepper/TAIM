# Step 6b: Skills Layer — Implementation Design

> Version: 1.0
> Date: 2026-04-13
> Status: Reviewed
> Scope: US-12.3 (Skills as reusable prompt+tool patterns, 5 built-in skills)

---

## 1. Overview

Step 6b adds the **Skills Layer** — reusable prompt+tool patterns that specialize an agent's behavior for a domain.

```
Agent has skills: [web_research, summarization]
    ↓
EXECUTING state
    ↓ load primary skill (agent.skills[0])
SkillRegistry.get("web_research") → Skill object
    ↓ render skill template
Prepend skill instructions to base EXECUTING prompt
    ↓
LLM call (with tools as before)
```

**Deliverables:**
1. `models/skill.py` — Skill model
2. `brain/skill_registry.py` — SkillRegistry (loads YAML, validates against ToolRegistry)
3. 5 built-in skill YAMLs in `taim-vault/system/skills/`
4. `brain/vault.py` — `_ensure_default_skills()` seeding
5. `brain/agent_state_machine.py` — Primary skill prepending in EXECUTING
6. `main.py` — SkillRegistry in lifespan, validate against tools
7. `api/skills.py` — `GET /api/skills`
8. Update agent YAMLs: `coder` and `reviewer` get matching skill first

**Out of scope (Step 7):**
- Multi-skill composition (Context Assembler)
- Dynamic skill selection based on task
- Team Composer skill-aware agent selection (US-12.3 AC5)

---

## 2. Module Architecture

### 2.1 File Layout

```
backend/src/taim/
├── models/
│   └── skill.py                              # NEW: Skill model
├── brain/
│   ├── skill_registry.py                     # NEW: SkillRegistry
│   ├── agent_state_machine.py                # MODIFIED: skill prepending
│   └── vault.py                              # MODIFIED: seed skills
├── api/
│   └── skills.py                             # NEW: GET /api/skills

taim-vault/system/skills/                     # NEW
├── web_research.yaml
├── code_generation.yaml
├── code_review.yaml
├── content_writing.yaml
└── data_analysis.yaml
```

### 2.2 Dependency Graph

```
models/skill.py                    (no TAIM deps)
    ↓
brain/skill_registry.py            (depends on: models/skill, ToolRegistry for validation)
    ↓
brain/agent_state_machine.py       (MODIFIED: takes optional skill_registry)
    ↓
api/skills.py                      (depends on: skill_registry)
main.py                            (lifespan creates SkillRegistry)
```

---

## 3. Data Model (`models/skill.py`)

```python
from __future__ import annotations
from pydantic import BaseModel


class Skill(BaseModel):
    """Reusable prompt+tool pattern for agent specialization."""
    name: str                                  # snake_case, e.g., "web_research"
    description: str                           # Human + LLM-readable
    required_tools: list[str] = []             # Tool names this skill needs
    prompt_template: str                       # Static guidance, supports Jinja2 vars
    output_format: str = "markdown"            # Hint to LLM
```

**Why snake_case for `name`?** Aligns with existing agent YAML `skills` fields (`web_research`, `code_generation`, etc.). No fuzzy matching needed; one canonical naming convention.

---

## 4. SkillRegistry (`brain/skill_registry.py`)

```python
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
```

**Validation behavior:** Skills referencing unregistered tools are kept in the registry but logged as warnings. They remain usable for the prompt aspect — the agent will get the guidance even if some required_tools aren't available. The LLM may attempt the unavailable tool and ToolExecutor will return a clear "not available" error (already implemented in Step 6a).

---

## 5. Built-in Skills (5 YAML files)

### 5.1 `web_research.yaml`
```yaml
name: web_research
description: Search the web, fetch pages, and synthesize findings from multiple sources
required_tools: [web_search, web_fetch, file_write]
output_format: markdown
prompt_template: |
  You are conducting web research on the task below.

  Approach:
  1. Use web_search to identify 3-5 high-quality sources
  2. Use web_fetch to retrieve full content from the most promising
  3. Cross-reference findings — never trust a single source
  4. Cite specific URLs and quote when possible

  Output a structured summary in markdown with:
  - Key findings (bullet points)
  - Sources (URL + 1-line description)
  - Open questions or contradictions found
```

### 5.2 `code_generation.yaml`
```yaml
name: code_generation
description: Write, modify, and explain code with attention to existing conventions
required_tools: [file_read, file_write]
output_format: markdown
prompt_template: |
  You are writing code as part of an existing project.

  Approach:
  1. Read existing files (file_read) to understand conventions before writing
  2. Match the existing style — naming, indentation, idioms
  3. Write minimal, focused code — no speculative abstractions
  4. After writing, briefly explain what you did and why

  When writing files, use file_write with clear file paths.
```

### 5.3 `code_review.yaml`
```yaml
name: code_review
description: Review code for correctness, security, performance, and maintainability
required_tools: [file_read]
output_format: markdown
prompt_template: |
  You are reviewing code. Be specific and constructive.

  Focus areas (in order):
  1. Correctness — does it do what it claims?
  2. Security — input validation, secret handling, injection risks
  3. Maintainability — clarity, naming, structure
  4. Performance — only if obviously problematic

  Output:
  - Critical issues (must fix)
  - Important suggestions (should consider)
  - Minor notes (nice to have)

  Reference specific file:line locations. Avoid vague feedback.
```

### 5.4 `content_writing.yaml`
```yaml
name: content_writing
description: Write structured documents — reports, articles, summaries, emails
required_tools: [file_write]
output_format: markdown
prompt_template: |
  You are writing content for a specific audience and purpose.

  Approach:
  1. Identify the target reader and the action you want them to take
  2. Lead with the most important information
  3. Use plain language — replace jargon with concrete terms
  4. Match the requested tone (formal, casual, technical, marketing)

  Structure: clear headings, short paragraphs, bullet points where lists help.
```

### 5.5 `data_analysis.yaml`
```yaml
name: data_analysis
description: Analyze structured data and synthesize insights with comparisons
required_tools: [file_read]
output_format: markdown
prompt_template: |
  You are analyzing data to produce insights.

  Approach:
  1. Read input data carefully — note structure, types, completeness
  2. Identify patterns, outliers, comparisons that matter for the question
  3. Quantify where possible — exact numbers beat vague claims
  4. Distinguish observations (what the data shows) from inferences (what you conclude)

  Output:
  - Summary (2-3 sentences)
  - Key findings (with numbers)
  - Notable patterns or anomalies
  - Caveats — what the data does NOT tell us
```

---

## 6. AgentStateMachine — Skill Prepending

### 6.1 New constructor parameter

```python
def __init__(
    self,
    ...
    skill_registry: SkillRegistry | None = None,    # NEW, optional
):
    self._skill_registry = skill_registry
```

Bootstrap pattern: `None` is fine, agents work without skills.

### 6.2 Updated `_do_executing`

The change is minimal — wrap the existing prompt loading with skill prepending:

```python
async def _do_executing(self) -> None:
    base_prompt = await self._load_state_prompt(AgentStateEnum.EXECUTING, {
        "task_description": self._task_description,
        "agent_description": self._agent.description,
        "plan": self._state.plan,
        "iteration": str(self._state.iteration),
        "user_preferences": self._user_preferences,
    })

    # NEW: prepend primary skill prompt if available
    skill_prefix = self._render_primary_skill()
    full_prompt = (skill_prefix + "\n\n" + base_prompt) if skill_prefix else base_prompt

    tools = None
    if self._tool_executor and self._agent.tools:
        tools = self._tool_executor.get_tools_for_agent(self._agent.tools)
        if not tools:
            tools = None

    messages: list[dict] = [{"role": "system", "content": full_prompt}]
    # ... rest of tool loop unchanged
```

### 6.3 Skill rendering

```python
def _render_primary_skill(self) -> str:
    """Return the rendered primary skill prompt or empty string if not available."""
    if self._skill_registry is None or not self._agent.skills:
        return ""

    primary_name = self._agent.skills[0]
    skill = self._skill_registry.get(primary_name)
    if skill is None:
        logger.warning(
            "agent.skill_not_found",
            agent=self._agent.name,
            skill=primary_name,
        )
        return ""

    # Render with Jinja2 — supports {{ task_description }} etc.
    template = self._jinja.from_string(skill.prompt_template)
    return template.render(
        task_description=self._task_description,
        agent_description=self._agent.description,
    )
```

For Jinja2: reuse `SandboxedEnvironment` instance. We can lazy-init it on the state machine, or accept it via constructor. Simpler: lazy-init.

---

## 7. Lifespan Integration

In `main.py`, after Tool System initialization (block 11):

```python
    # 12. Skill Registry
    from taim.brain.skill_registry import SkillRegistry

    skill_registry = SkillRegistry(
        system_config.vault.vault_root / "system" / "skills"
    )
    skill_registry.load()
    skill_registry.validate_against_tools(tool_registry)

    app.state.skill_registry = skill_registry
    logger.info("skills.loaded", count=len(skill_registry.list_skills()))
```

Add `get_skill_registry()` to `api/deps.py`.

VaultOps `_ensure_default_skills()` seeds the 5 YAML files. Called from `ensure_vault()` after `_ensure_default_tools()`.

---

## 8. Updated Agent YAMLs

Two agents need their skills reordered so the primary skill matches a built-in skill:

```yaml
# coder.yaml
skills:
  - code_generation       # was: code_writing
  - refactoring
  - code_explanation
```

```yaml
# reviewer.yaml
skills:
  - code_review           # was: quality_assessment
  - quality_assessment
  - content_review
```

The other agents (researcher, writer, analyst) already have matching first skills:
- researcher: `web_research` ✓
- writer: `content_writing` ✓
- analyst: `data_analysis` ✓

Update the constants in vault.py. Note: existing dev vault won't auto-update (idempotent seeding) — we'll re-seed manually.

---

## 9. API Endpoint (`api/skills.py`)

```python
from fastapi import APIRouter, Depends

from taim.api.deps import get_skill_registry
from taim.brain.skill_registry import SkillRegistry

router = APIRouter(prefix="/api/skills")


@router.get("")
async def list_skills(registry: SkillRegistry = Depends(get_skill_registry)) -> dict:
    skills = registry.list_skills()
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "required_tools": s.required_tools,
                "output_format": s.output_format,
            }
            for s in skills
        ],
        "count": len(skills),
    }
```

---

## 10. Critical Review Findings (Applied)

| # | Finding | Resolution |
|---|---------|------------|
| 1 | Skill name vs agent.skills naming inconsistency | Standardize on snake_case everywhere; reorder coder + reviewer agent skills |
| 2 | Skill referencing unavailable tool (web_research → web_search) | Skill loaded + warning logged; remains usable for prompt; ToolExecutor returns "tool not available" if invoked |
| 3 | Multiple skills per agent — which wins? | Primary = `skills[0]`. Step 7 Context Assembler will compose multi-skill prompts |
| 4 | Skill template variable substitution | Jinja2 with limited context: `task_description`, `agent_description`. Step 7 expands to full context |
| 5 | Skill prompt blows up base prompt size | Skill = static guidance ~500 tokens. Acceptable for MVP. Step 7 will gate on token budget |
| 6 | Agent without skills | `agent.skills` empty or no registry → no prepending, normal flow |
| 7 | Skill not in registry | Warning logged, prepending skipped — agent runs with base prompt only |

---

## 11. Expansion Stages

### Step 7 (Orchestrator)
- **Context Assembler**: token-budgeted skill composition (multiple skills, dynamic selection)
- **Team Composer skill-aware selection (US-12.3 AC5)**: only assign agent to role if it has the required skill for that task type
- **Per-task skill override**: user message ("use code_review skill") could override agent's primary

### Step 6d (Web Tools)
- Once `web_search` and `web_fetch` exist, the `web_research` skill becomes fully functional (currently logs warning at startup)

### Phase 2
- Custom user-defined skills (drop YAML in `taim-vault/system/skills/`)
- Skill versioning + git history per skill
- Skill performance tracking (success rate per skill)

---

## 12. Test Strategy

| Test File | Module | Notable Tests |
|-----------|--------|---------------|
| `test_skill_models.py` | models/skill.py | Pydantic validation, defaults |
| `test_skill_registry.py` | brain/skill_registry.py | Load valid/invalid YAML, validate_against_tools, get/list |
| `test_agent_state_machine_skills.py` | brain/agent_state_machine.py | Skill prepended when present, skipped when missing, agent without skills works, no registry works |
| `test_skills_api.py` | api/skills.py | GET /api/skills returns 5 built-in |
| `test_vault.py` (extend) | brain/vault.py | Seeds 5 skill YAMLs |

Coverage target: >85% on new modules.

---

*End of Step 6b Design.*
