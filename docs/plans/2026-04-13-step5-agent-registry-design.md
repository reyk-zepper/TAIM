# Step 5: Agent Registry & State Machine — Implementation Design

> Version: 1.0
> Date: 2026-04-13
> Status: Reviewed — critical review applied
> Scope: US-3.1, US-3.2, US-3.4, US-5.1 (all P0)

---

## 1. Overview

Step 5 builds the foundation of agent execution:

```
AgentRegistry (5 built-in agents)
    ↓ queried by
AgentStateMachine (autonomous runner)
    ↓ drives through states
PLANNING → EXECUTING → REVIEWING → [ITERATING →] EXECUTING → DONE
    ↓ each transition serialized to
SQLite (agent_runs table, crash-resumable)
```

**Architecture (AD-3):** Each agent runs as an **explicit state machine**, not a simple async loop. Debuggable, controllable, resumable, observable.

**Deliverables:**
1. `models/agent.py` — AgentStateEnum, Agent, AgentState, AgentRun, StateTransition
2. `brain/agent_registry.py` — AgentRegistry (load + query YAML files)
3. `brain/agent_state_machine.py` — AgentStateMachine (autonomous `run()` through 7 states)
4. `brain/agent_run_store.py` — Persistence for agent_runs table (resume-ready)
5. 5 built-in agent YAML definitions in `taim-vault/agents/`
6. 4 default state prompts in `taim-vault/system/prompts/agents/default/`
7. 1 override example: `taim-vault/system/prompts/agents/researcher/executing.yaml`
8. `api/agents.py` — REST endpoints `GET /api/agents`, `GET /api/agents/{name}`
9. Lifespan integration (Registry in app.state)

**Autonomous Unit:** The AgentStateMachine owns the full per-agent execution loop. The Orchestrator (Step 7) creates instances and coordinates multiple agents; it does NOT drive individual transitions.

---

## 2. Module Architecture

### 2.1 File Layout

```
backend/src/taim/
├── models/
│   └── agent.py                           # Agent models (6 classes)
├── brain/
│   ├── agent_registry.py                  # AgentRegistry
│   ├── agent_state_machine.py             # AgentStateMachine (autonomous)
│   └── agent_run_store.py                 # SQLite persistence for agent_runs
├── api/
│   └── agents.py                          # GET /api/agents, GET /api/agents/{name}

taim-vault/
├── agents/
│   ├── researcher.yaml
│   ├── coder.yaml
│   ├── reviewer.yaml
│   ├── writer.yaml
│   └── analyst.yaml
└── system/prompts/agents/
    ├── default/
    │   ├── planning.yaml
    │   ├── executing.yaml
    │   ├── reviewing.yaml
    │   └── iterating.yaml
    └── researcher/
        └── executing.yaml                 # Override example
```

### 2.2 Dependency Graph

```
models/agent.py                          (no TAIM deps)
    ↓
brain/agent_registry.py                  (depends on: models/agent, VaultOps)
brain/agent_run_store.py                 (depends on: models/agent, aiosqlite)
    ↓
brain/agent_state_machine.py             (depends on: models/agent, Router, PromptLoader, agent_run_store)
    ↓
api/agents.py                            (depends on: agent_registry)
main.py                                  (lifespan creates Registry, vault seeds prompts)
```

---

## 3. Data Models (`models/agent.py`)

```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class AgentStateEnum(str, Enum):
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    REVIEWING = "REVIEWING"
    ITERATING = "ITERATING"
    WAITING = "WAITING"       # Approval gate (Step 8+ full flow)
    DONE = "DONE"
    FAILED = "FAILED"


class Agent(BaseModel):
    """Agent definition loaded from taim-vault/agents/{name}.yaml."""
    name: str
    description: str
    model_preference: list[str]                        # ["tier1_premium", "tier2_standard"]
    skills: list[str]                                  # ["web_research", "data_analysis"]
    tools: list[str] = []                              # Populated in Step 6
    max_iterations: int = 3
    requires_approval_for: list[str] = []              # ["file_deletion", ...]


class StateTransition(BaseModel):
    """One transition in the state history."""
    from_state: AgentStateEnum | None                  # None for initial
    to_state: AgentStateEnum
    timestamp: datetime
    reason: str = ""                                   # "planning complete", "review failed", etc.


class AgentState(BaseModel):
    """Runtime state snapshot for an agent run."""
    agent_name: str
    run_id: str
    current_state: AgentStateEnum = AgentStateEnum.PLANNING
    iteration: int = 0
    tokens_used: int = 0
    cost_eur: float = 0.0
    state_history: list[StateTransition] = []
    plan: str = ""
    current_result: str = ""
    review_feedback: str = ""


class AgentRun(BaseModel):
    """Completed execution record (for agent_runs SQLite table)."""
    run_id: str
    agent_name: str
    task_id: str
    team_id: str = ""
    session_id: str | None = None
    final_state: AgentStateEnum
    state_history: list[StateTransition] = []
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_eur: float = 0.0
    provider: str | None = None
    model_used: str | None = None
    failover_occurred: bool = False
    result_content: str = ""


class ReviewResult(BaseModel):
    """Structured output from REVIEWING state prompt."""
    quality_ok: bool
    feedback: str
```

---

## 4. AgentRegistry (`brain/agent_registry.py`)

**Responsibility:** Load all agent YAML files at startup, provide query API.

```python
import yaml
from pathlib import Path

import structlog
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
        """Manual reload (US-3.2 AC5 P1 sub-feature). File watcher is a future expansion."""
        self.load()

    def get_agent(self, name: str) -> Agent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[Agent]:
        return list(self._agents.values())

    def find_by_skill(self, skill: str) -> list[Agent]:
        skill_lower = skill.lower()
        return [a for a in self._agents.values() if skill_lower in [s.lower() for s in a.skills]]
```

**Invalid YAML behavior:** Log warning, skip file. Server startup is not blocked (US-3.2 AC3).

---

## 5. AgentStateMachine (`brain/agent_state_machine.py`)

**Responsibility:** Autonomous execution of one agent through 7 states.

### 5.1 Core Interface

```python
class TransitionEvent(BaseModel):
    """Emitted on every state transition for observers (Orchestrator wires WebSocket)."""
    run_id: str
    agent_name: str
    from_state: AgentStateEnum | None
    to_state: AgentStateEnum
    iteration: int
    reason: str
    timestamp: datetime


class AgentStateMachine:
    """Autonomous agent execution state machine."""

    def __init__(
        self,
        agent: Agent,
        router,                                     # LLMRouter
        prompt_loader: PromptLoader,
        run_store: AgentRunStore,
        task_id: str,
        task_description: str,
        session_id: str | None = None,
        team_id: str = "",
        user_preferences: str = "",
        on_transition: Callable[[TransitionEvent], Awaitable[None]] | None = None,
    ) -> None: ...

    async def run(self) -> AgentRun:
        """Run through states until DONE or FAILED. Returns completion record."""

    async def serialize(self) -> None:
        """Persist current state to SQLite (called after every transition)."""

    @classmethod
    async def deserialize(cls, run_id: str, ...) -> "AgentStateMachine":
        """Rebuild from SQLite (for crash recovery). Full auto-resume is Step 8."""
```

### 5.2 State Flow

```
initial → PLANNING:
  1. Load prompt (agents/{name}/planning.yaml or default)
  2. Router.complete(tier=from agent.model_preference)
  3. Store plan in state.plan
  4. Transition → EXECUTING

PLANNING → EXECUTING:
  1. Load executing prompt with {task_description, plan, iteration, user_preferences}
  2. Router.complete
  3. Store result in state.current_result
  4. Transition → REVIEWING

EXECUTING → REVIEWING:
  1. Load reviewing prompt with {task_description, current_result} (expected_format=json)
  2. Router.complete → ReviewResult
  3. If quality_ok OR iteration >= max_iterations → DONE
  4. Else → ITERATING

REVIEWING → ITERATING:
  1. iteration += 1
  2. Load iterating prompt with {task_description, current_result, review_feedback}
  3. Router.complete → improved result
  4. Transition → EXECUTING (loop back for re-review)

Any state → FAILED:
  - On AllProvidersFailed from Router
  - On PromptNotFoundError for both agent-specific and default fallback
  - On malformed review output after retry

Any state → WAITING (Step 8+):
  - Approval-required action detected (US-3.5, not in Step 5 scope)
```

### 5.3 Prompt Loading with Fallback

```python
async def _load_state_prompt(
    self,
    state: AgentStateEnum,
    variables: dict,
) -> str:
    """Try agent-specific prompt first, fall back to default (US-5.1 AC1+2)."""
    state_name = state.value.lower()
    try:
        return self._prompts.load(f"agents/{self._agent.name}/{state_name}", variables)
    except PromptNotFoundError:
        try:
            return self._prompts.load(f"agents/default/{state_name}", variables)
        except PromptNotFoundError as e:
            # US-5.1 AC4 — transition to FAILED
            raise PromptNotFoundError(f"agents/default/{state_name}", e.path) from e
```

### 5.4 Tier Resolution

`agent.model_preference` is an ordered list like `["tier1_premium", "tier2_standard"]`. The state machine passes the first tier to the Router. Router's failover (Step 2) handles within-tier failures — if tier1 fails entirely, the state machine tries tier2 on the next state. For MVP: use the first tier throughout a run. Smarter tier escalation is future work.

### 5.5 Error Handling

- `AllProvidersFailed` → transition to FAILED, store error in state_history reason
- `PromptNotFoundError` (no default fallback) → FAILED
- JSON parse error on REVIEWING → retry via Router's bad-format flow (Step 2). If that fails, treat as quality_ok=True (don't loop forever).

### 5.6 Transition Event Callback

```python
if self._on_transition:
    await self._on_transition(TransitionEvent(
        run_id=self._state.run_id,
        agent_name=self._agent.name,
        from_state=prev_state,
        to_state=new_state,
        iteration=self._state.iteration,
        reason=reason,
        timestamp=datetime.now(timezone.utc),
    ))
```

State machine does NOT know about WebSocket. The Orchestrator (Step 7) passes a callback that forwards events.

---

## 6. AgentRunStore (`brain/agent_run_store.py`)

**Responsibility:** Persist AgentState to `agent_runs` SQLite table. Load for resumption.

```python
import json
import aiosqlite

from taim.models.agent import AgentRun, AgentState, AgentStateEnum, StateTransition


class AgentRunStore:
    """SQLite persistence for agent runs."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def upsert(self, state: AgentState, agent_name: str, task_id: str, team_id: str = "", session_id: str | None = None) -> None:
        """Persist current state. Called after every transition."""
        history_json = json.dumps([t.model_dump(mode="json") for t in state.state_history])
        await self._db.execute(
            """INSERT INTO agent_runs
               (run_id, agent_name, task_id, team_id, session_id,
                state_history, final_state, prompt_tokens, completion_tokens,
                cost_eur, failover_occurred, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, 0, datetime('now'))
               ON CONFLICT(run_id) DO UPDATE SET
                   state_history = excluded.state_history,
                   final_state = excluded.final_state,
                   cost_eur = excluded.cost_eur,
                   completed_at = CASE WHEN excluded.final_state IN ('DONE', 'FAILED')
                                       THEN datetime('now') ELSE completed_at END""",
            (state.run_id, agent_name, task_id, team_id, session_id,
             history_json, state.current_state.value, state.cost_eur),
        )
        await self._db.commit()

    async def load_active_runs(self) -> list[dict]:
        """Return runs where final_state is not terminal — for resume logic in Step 8."""
        async with self._db.execute(
            """SELECT run_id, agent_name, task_id, team_id, session_id, state_history, final_state
               FROM agent_runs
               WHERE final_state NOT IN ('DONE', 'FAILED')"""
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {
                "run_id": r[0],
                "agent_name": r[1],
                "task_id": r[2],
                "team_id": r[3],
                "session_id": r[4],
                "state_history": json.loads(r[5]) if r[5] else [],
                "final_state": r[6],
            }
            for r in rows
        ]
```

---

## 7. Built-in Agents

Five YAML files in `taim-vault/agents/`. All seeded by VaultOps on first init (`_ensure_default_agents()`).

### researcher.yaml
```yaml
name: researcher
description: Researches topics using web sources and summarizes findings
model_preference:
  - tier2_standard
  - tier3_economy
skills:
  - web_research
  - summarization
  - source_evaluation
tools: []                    # Populated in Step 6 (web_search, web_fetch)
max_iterations: 3
requires_approval_for: []
```

### coder.yaml
```yaml
name: coder
description: Writes, edits, and explains code
model_preference:
  - tier1_premium
  - tier2_standard
skills:
  - code_writing
  - refactoring
  - code_explanation
tools: []
max_iterations: 3
requires_approval_for:
  - file_deletion
  - external_communication
```

### reviewer.yaml
```yaml
name: reviewer
description: Reviews work products for quality, completeness, and correctness
model_preference:
  - tier1_premium
skills:
  - quality_assessment
  - code_review
  - content_review
tools: []
max_iterations: 2
requires_approval_for: []
```

### writer.yaml
```yaml
name: writer
description: Creates written content — articles, emails, documentation
model_preference:
  - tier2_standard
skills:
  - content_writing
  - editing
  - tone_adaptation
tools: []
max_iterations: 3
requires_approval_for:
  - external_communication
```

### analyst.yaml
```yaml
name: analyst
description: Analyzes data and synthesizes insights
model_preference:
  - tier1_premium
  - tier2_standard
skills:
  - data_analysis
  - pattern_recognition
  - insight_synthesis
tools: []
max_iterations: 3
requires_approval_for: []
```

---

## 8. Default State Prompts

Four files in `taim-vault/system/prompts/agents/default/`. Seeded by VaultOps.

### planning.yaml
```yaml
name: agents/default/planning
version: 1
description: Default PLANNING prompt — agent analyzes task and proposes an approach
model_tier: tier2_standard
variables:
  - task_description
  - agent_description
  - user_preferences
template: |
  You are a {{ agent_description }}.

  Your task: {{ task_description }}

  User preferences:
  {{ user_preferences }}

  Think through how you will approach this task. Output a concise plan (3-6 bullet points).
  Do not execute yet. Just plan.
```

### executing.yaml
```yaml
name: agents/default/executing
version: 1
description: Default EXECUTING prompt — agent carries out the plan
model_tier: tier2_standard
variables:
  - task_description
  - agent_description
  - plan
  - iteration
  - user_preferences
template: |
  You are a {{ agent_description }}.

  Task: {{ task_description }}

  Your plan:
  {{ plan }}

  Iteration: {{ iteration }}

  User preferences:
  {{ user_preferences }}

  Execute the plan and produce the result.
```

### reviewing.yaml
```yaml
name: agents/default/reviewing
version: 1
description: Default REVIEWING prompt — agent self-assesses its output
model_tier: tier2_standard
variables:
  - task_description
  - current_result
template: |
  You are a critical reviewer. Assess the following result against the task.

  Task: {{ task_description }}

  Result:
  {{ current_result }}

  Respond with JSON only:
  {
    "quality_ok": <true | false>,
    "feedback": "<specific feedback — what is good, what needs improvement>"
  }

  quality_ok=true only if the result fully satisfies the task.
```

### iterating.yaml
```yaml
name: agents/default/iterating
version: 1
description: Default ITERATING prompt — agent improves based on review feedback
model_tier: tier2_standard
variables:
  - task_description
  - current_result
  - review_feedback
template: |
  Improve the following result based on the review feedback.

  Task: {{ task_description }}

  Previous result:
  {{ current_result }}

  Reviewer feedback:
  {{ review_feedback }}

  Produce an improved result that addresses the feedback.
```

### researcher/executing.yaml (override example)
```yaml
name: agents/researcher/executing
version: 1
description: Researcher-specific EXECUTING prompt — emphasizes source verification
model_tier: tier2_standard
variables:
  - task_description
  - agent_description
  - plan
  - iteration
  - user_preferences
template: |
  You are a researcher. Verify sources, prefer primary data, and cite specifics.

  Task: {{ task_description }}

  Your plan:
  {{ plan }}

  Iteration: {{ iteration }}

  User preferences:
  {{ user_preferences }}

  Execute the plan. Cite sources. Avoid speculation.
```

---

## 9. API Endpoints (`api/agents.py`)

```python
from fastapi import APIRouter, Depends, HTTPException

from taim.api.deps import get_registry    # new DI
from taim.brain.agent_registry import AgentRegistry
from taim.models.agent import Agent

router = APIRouter(prefix="/api/agents")


@router.get("")
async def list_agents(registry: AgentRegistry = Depends(get_registry)) -> dict:
    agents = registry.list_agents()
    return {
        "agents": [
            {"name": a.name, "description": a.description, "skills": a.skills}
            for a in agents
        ],
        "count": len(agents),
    }


@router.get("/{agent_name}")
async def get_agent(agent_name: str, registry: AgentRegistry = Depends(get_registry)) -> Agent:
    agent = registry.get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return agent
```

---

## 10. Lifespan Integration

In `main.py`, after Memory System initialization:

```python
    # 10. Agent Registry
    from taim.brain.agent_registry import AgentRegistry
    from taim.brain.agent_run_store import AgentRunStore

    registry = AgentRegistry(system_config.vault.agents_dir)
    registry.load()
    run_store = AgentRunStore(db)

    app.state.agent_registry = registry
    app.state.agent_run_store = run_store
```

Add `get_registry()` to `api/deps.py`. Add `api/agents.router` to `create_app()`.

VaultOps `_ensure_default_prompts()` extended to seed the 5 state prompt YAMLs and 5 agent YAMLs.

---

## 11. Expansion Stages (Deferred Work)

The following items are intentionally deferred. Each is tracked for the step where it lands.

### Deferred to Step 6 (Tool Execution, Skills, MCP)
- **Agent `tools` field populated** — Step 6 builds tool framework. All built-in agents will get appropriate tools (researcher → web_search/web_fetch, coder → file_read/write, etc.)
- **Per-state prompt overrides for other 4 agents** (coder, reviewer, writer, analyst) — only researcher gets a custom `executing.yaml` in Step 5. Others use defaults. Step 6 adds specialized prompts as needed for tool-using patterns.

### Deferred to Step 7 (Team Composer & Orchestrator)
- **Context Assembler (US-5.2)** — token-budgeted assembly from memory, agent state, task. Step 5 accepts context as-is from caller.
- **Inter-agent result passing** — agent A's output becomes agent B's input. Requires Orchestrator.
- **Team-level composition** — which agents for which task. State machine executes one agent at a time.
- **Approval gate execution flow (US-3.5)** — WAITING state exists in enum and can be entered, but the question/approval/timeout flow is not wired up until Orchestrator can coordinate with WebSocket.

### Deferred to Step 8 (Heartbeat Manager & Token Tracking)
- **Auto-resume on startup (US-3.4 AC4)** — `AgentRunStore.load_active_runs()` is built in Step 5. Wiring it into the lifespan to auto-resume is Step 8 when Heartbeat runs the monitoring loop.
- **Per-agent timeout enforcement** — `agent_timeout` from ProductConfig is not yet checked. Step 8 Heartbeat enforces wall-clock timeouts.
- **Smarter tier escalation** — currently uses `model_preference[0]` throughout. Escalation on low-quality detection (AD-10) is future work.

### Deferred to Step 10+ (Dashboard)
- **WebSocket event forwarding** — `TransitionEvent` callbacks exist in Step 5. The Orchestrator will forward these to WebSocket in Step 7. Dashboard subscribes in Step 10.

### Deferred to Step 11 (CLI & Polish)
- **`taim agent list` CLI (US-3.3 AC4)** — registry query is available; CLI wrapper comes with all CLI work.
- **Full custom agent YAML documentation** — inline comments in built-in agent files are written now. Formal docs in Step 11.

### P1 Features Intentionally Not Implemented in Step 5
- **US-3.3 Custom Agent via YAML** (P1) — mechanism works (Registry loads any .yaml), but CLI command and explicit-selection-via-chat are P1 polish.
- **US-3.5 Approval Gate full flow** (P1) — WAITING state is in the enum; activation logic is Step 7+.
- **US-3.2 AC5 File watcher reload** — manual `registry.reload()` is provided. File system watching adds complexity (watchdog dependency) — not needed for MVP.

---

## 12. Critical Review Findings (Applied)

| # | Finding | Resolution |
|---|---------|------------|
| 1 | State machine must emit events but not know about WebSocket | `on_transition` callback parameter; Orchestrator (Step 7) supplies the WebSocket-forwarding callback |
| 2 | REVIEWING needs JSON output | Uses Router's `expected_format="json"`, parses into `ReviewResult` model |
| 3 | Prompt fallback logic | Try `agents/{name}/{state}`, fall back to `agents/default/{state}`, else FAILED |
| 4 | Malformed review output could infinite-loop | Router retries once (bad_format strategy). If still invalid, treat as `quality_ok=True` (fail-safe: result as-is) |
| 5 | SQLite write per transition = many writes | Acceptable: typical run has ~5 transitions, <10ms per write. Batching is future optimization |
| 6 | Invalid agent YAML shouldn't crash server | Logged as warning, file skipped — server starts regardless (US-3.2 AC3) |
| 7 | `model_preference` as strings, not enum | Matches PRD data model. Strings validated against ModelTierEnum values at runtime |
| 8 | Five agents ship by default | Seeded via `VaultOps._ensure_default_agents()`, same pattern as configs/prompts |
| 9 | Only researcher gets custom prompt | Proves override mechanism; other agents use defaults. Step 6 adds more overrides as tool-use patterns emerge |

---

## 13. Test Strategy

| Test File | Module | Notable Tests |
|-----------|--------|---------------|
| `test_agent_models.py` | models/agent.py | Enum values, Pydantic validation |
| `test_agent_registry.py` | brain/agent_registry.py | Load valid/invalid YAML, query, reload |
| `test_agent_run_store.py` | brain/agent_run_store.py | Upsert roundtrip, load_active_runs filters terminal |
| `test_agent_state_machine.py` | brain/agent_state_machine.py | Full flow PLANNING→EXECUTING→REVIEWING→DONE, iteration loop, max_iterations, failover to FAILED, prompt fallback |
| `test_agents_api.py` | api/agents.py | GET list, GET by name, 404 |
| `test_vault.py` (extend) | brain/vault.py | Seeds agents + state prompts |

Coverage target: >80%.

---

*End of Step 5 Design.*
