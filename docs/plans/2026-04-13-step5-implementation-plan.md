# Step 5: Agent Registry & State Machine — Implementation Plan

> **For agentic workers:** Follow superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the agent layer — registry, 7-state machine, SQLite persistence, 5 built-in agents, REST endpoints.

**Architecture:** Autonomous AgentStateMachine per run, driven by Router + per-state prompts with fallback. Design: `docs/plans/2026-04-13-step5-agent-registry-design.md`.

**Tech Stack:** Python 3.11+, FastAPI, LiteLLM via Router, aiosqlite, PyYAML.

---

## File Structure

### Files to Create
```
backend/src/taim/models/agent.py
backend/src/taim/brain/agent_registry.py
backend/src/taim/brain/agent_run_store.py
backend/src/taim/brain/agent_state_machine.py
backend/src/taim/api/agents.py
taim-vault/agents/{researcher,coder,reviewer,writer,analyst}.yaml
taim-vault/system/prompts/agents/default/{planning,executing,reviewing,iterating}.yaml
taim-vault/system/prompts/agents/researcher/executing.yaml
tests/backend/test_agent_models.py
tests/backend/test_agent_registry.py
tests/backend/test_agent_run_store.py
tests/backend/test_agent_state_machine.py
tests/backend/test_agents_api.py
```

### Files to Modify
```
backend/src/taim/brain/vault.py        # Seed 5 agents + 5 state prompts
backend/src/taim/main.py               # Register AgentRegistry, AgentRunStore in lifespan
backend/src/taim/api/deps.py           # get_registry(), get_run_store()
tests/backend/test_vault.py            # Extended for new seeded files
```

---

## Task 1: Agent Data Models

**Files:** `backend/src/taim/models/agent.py`, `tests/backend/test_agent_models.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for agent data models."""

from datetime import datetime, timezone

from taim.models.agent import (
    Agent, AgentRun, AgentState, AgentStateEnum, ReviewResult, StateTransition,
)


class TestAgentStateEnum:
    def test_all_states(self) -> None:
        assert AgentStateEnum.PLANNING == "PLANNING"
        assert AgentStateEnum.EXECUTING == "EXECUTING"
        assert AgentStateEnum.REVIEWING == "REVIEWING"
        assert AgentStateEnum.ITERATING == "ITERATING"
        assert AgentStateEnum.WAITING == "WAITING"
        assert AgentStateEnum.DONE == "DONE"
        assert AgentStateEnum.FAILED == "FAILED"


class TestAgent:
    def test_minimal(self) -> None:
        a = Agent(
            name="researcher", description="Research",
            model_preference=["tier2_standard"], skills=["web_research"],
        )
        assert a.max_iterations == 3
        assert a.tools == []
        assert a.requires_approval_for == []


class TestStateTransition:
    def test_minimal(self) -> None:
        t = StateTransition(
            from_state=AgentStateEnum.PLANNING,
            to_state=AgentStateEnum.EXECUTING,
            timestamp=datetime.now(timezone.utc),
        )
        assert t.reason == ""

    def test_initial_transition_has_no_from_state(self) -> None:
        t = StateTransition(
            from_state=None,
            to_state=AgentStateEnum.PLANNING,
            timestamp=datetime.now(timezone.utc),
        )
        assert t.from_state is None


class TestAgentState:
    def test_defaults(self) -> None:
        s = AgentState(agent_name="researcher", run_id="run-1")
        assert s.current_state == AgentStateEnum.PLANNING
        assert s.iteration == 0
        assert s.state_history == []


class TestAgentRun:
    def test_minimal(self) -> None:
        r = AgentRun(
            run_id="run-1", agent_name="researcher", task_id="task-1",
            final_state=AgentStateEnum.DONE,
        )
        assert r.team_id == ""
        assert r.failover_occurred is False


class TestReviewResult:
    def test_quality_ok(self) -> None:
        r = ReviewResult(quality_ok=True, feedback="Looks good")
        assert r.quality_ok is True
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement models/agent.py**

```python
"""Data models for agents and their execution state."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class AgentStateEnum(str, Enum):
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    REVIEWING = "REVIEWING"
    ITERATING = "ITERATING"
    WAITING = "WAITING"
    DONE = "DONE"
    FAILED = "FAILED"


class Agent(BaseModel):
    """Agent definition loaded from taim-vault/agents/{name}.yaml."""

    name: str
    description: str
    model_preference: list[str]
    skills: list[str]
    tools: list[str] = []
    max_iterations: int = 3
    requires_approval_for: list[str] = []


class StateTransition(BaseModel):
    """One transition in the state history."""

    from_state: AgentStateEnum | None
    to_state: AgentStateEnum
    timestamp: datetime
    reason: str = ""


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

- [ ] **Step 4: Run → PASS** (6 tests)
- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/models/agent.py tests/backend/test_agent_models.py
git commit -m "feat: add agent data models (states, runs, transitions)"
```

---

## Task 2: AgentRegistry + Default Agents

**Files:**
- Create: `backend/src/taim/brain/agent_registry.py`
- Create: 5 agent YAML files in `taim-vault/agents/`
- Modify: `backend/src/taim/brain/vault.py` (seed agents)
- Create: `tests/backend/test_agent_registry.py`

- [ ] **Step 1: Create 5 agent YAML files in `taim-vault/agents/`**

`researcher.yaml`:
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
tools: []
max_iterations: 3
requires_approval_for: []
```

`coder.yaml`:
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

`reviewer.yaml`:
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

`writer.yaml`:
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

`analyst.yaml`:
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

- [ ] **Step 2: Add `_ensure_default_agents()` to `vault.py`**

Add constants with the YAML content of each of the 5 agents (copy from Step 1 files). Add method:

```python
    def _ensure_default_agents(self) -> None:
        """Write default agent YAML files only if they don't exist."""
        defaults = {
            "researcher.yaml": _DEFAULT_AGENT_RESEARCHER,
            "coder.yaml": _DEFAULT_AGENT_CODER,
            "reviewer.yaml": _DEFAULT_AGENT_REVIEWER,
            "writer.yaml": _DEFAULT_AGENT_WRITER,
            "analyst.yaml": _DEFAULT_AGENT_ANALYST,
        }
        for filename, content in defaults.items():
            path = self.vault_config.agents_dir / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")
```

Call `self._ensure_default_agents()` at the end of `ensure_vault()`, after prompts.

- [ ] **Step 3: Write registry tests**

```python
"""Tests for AgentRegistry."""

from pathlib import Path

import pytest

from taim.brain.agent_registry import AgentRegistry


class TestLoad:
    def test_loads_valid_agents(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "a.yaml").write_text(
            "name: a\ndescription: A\nmodel_preference: [tier2_standard]\nskills: [s1]\n"
        )
        registry = AgentRegistry(agents_dir)
        registry.load()
        assert registry.get_agent("a") is not None
        assert len(registry.list_agents()) == 1

    def test_skips_invalid_yaml(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "bad.yaml").write_text("not: valid: yaml: [")
        (agents_dir / "good.yaml").write_text(
            "name: good\ndescription: Good\nmodel_preference: [tier2_standard]\nskills: []\n"
        )
        registry = AgentRegistry(agents_dir)
        registry.load()
        assert registry.get_agent("good") is not None
        assert registry.get_agent("bad") is None

    def test_missing_dir(self, tmp_path: Path) -> None:
        registry = AgentRegistry(tmp_path / "nonexistent")
        registry.load()
        assert registry.list_agents() == []


class TestQuery:
    def _setup(self, tmp_path: Path) -> AgentRegistry:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "r.yaml").write_text(
            "name: r\ndescription: R\nmodel_preference: [tier2_standard]\nskills: [research, summarization]\n"
        )
        (agents_dir / "c.yaml").write_text(
            "name: c\ndescription: C\nmodel_preference: [tier1_premium]\nskills: [coding]\n"
        )
        registry = AgentRegistry(agents_dir)
        registry.load()
        return registry

    def test_get_by_name(self, tmp_path: Path) -> None:
        registry = self._setup(tmp_path)
        assert registry.get_agent("r").name == "r"
        assert registry.get_agent("nonexistent") is None

    def test_find_by_skill(self, tmp_path: Path) -> None:
        registry = self._setup(tmp_path)
        results = registry.find_by_skill("research")
        assert len(results) == 1
        assert results[0].name == "r"

    def test_find_by_skill_case_insensitive(self, tmp_path: Path) -> None:
        registry = self._setup(tmp_path)
        assert len(registry.find_by_skill("RESEARCH")) == 1


class TestReload:
    def test_reload_picks_up_new_file(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        registry = AgentRegistry(agents_dir)
        registry.load()
        assert registry.list_agents() == []

        (agents_dir / "new.yaml").write_text(
            "name: new\ndescription: New\nmodel_preference: [tier2_standard]\nskills: []\n"
        )
        registry.reload()
        assert registry.get_agent("new") is not None
```

- [ ] **Step 4: Implement `brain/agent_registry.py`**

(Full code from design doc Section 4.)

- [ ] **Step 5: Run → PASS** (7 tests)

- [ ] **Step 6: Verify vault seeds agents**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest ../tests/backend/test_vault.py -v
```

If tests fail because the vault test expects the new seeded files, extend `test_vault.py`:
```python
class TestDefaultAgents:
    def test_creates_five_agents(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        for name in ["researcher", "coder", "reviewer", "writer", "analyst"]:
            assert (ops.vault_config.agents_dir / f"{name}.yaml").exists()
```

- [ ] **Step 7: Commit**

```bash
git add backend/src/taim/brain/agent_registry.py backend/src/taim/brain/vault.py taim-vault/agents/ tests/backend/test_agent_registry.py tests/backend/test_vault.py
git commit -m "feat: add AgentRegistry with 5 built-in agents seeded by VaultOps"
```

---

## Task 3: Default State Prompts + Researcher Override

**Files:**
- Create: 4 default prompts in `taim-vault/system/prompts/agents/default/`
- Create: `taim-vault/system/prompts/agents/researcher/executing.yaml`
- Modify: `backend/src/taim/brain/vault.py` (seed state prompts)

- [ ] **Step 1: Create the 5 prompt YAML files**

(Full content from design doc Section 8.)

- [ ] **Step 2: Add `_ensure_default_state_prompts()` to vault.py**

Store the YAML strings as constants. Handle nested directory structure:

```python
    def _ensure_default_state_prompts(self) -> None:
        """Seed default per-state prompts and researcher override."""
        default_dir = self.vault_config.prompts_dir / "agents" / "default"
        researcher_dir = self.vault_config.prompts_dir / "agents" / "researcher"
        default_dir.mkdir(parents=True, exist_ok=True)
        researcher_dir.mkdir(parents=True, exist_ok=True)

        defaults = {
            default_dir / "planning.yaml": _DEFAULT_STATE_PROMPT_PLANNING,
            default_dir / "executing.yaml": _DEFAULT_STATE_PROMPT_EXECUTING,
            default_dir / "reviewing.yaml": _DEFAULT_STATE_PROMPT_REVIEWING,
            default_dir / "iterating.yaml": _DEFAULT_STATE_PROMPT_ITERATING,
            researcher_dir / "executing.yaml": _RESEARCHER_EXECUTING_OVERRIDE,
        }
        for path, content in defaults.items():
            if not path.exists():
                path.write_text(content, encoding="utf-8")
```

Call from `ensure_vault()` after `_ensure_default_agents()`.

- [ ] **Step 3: Extend test_vault.py**

```python
class TestDefaultStatePrompts:
    def test_creates_default_state_prompts(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        default_dir = ops.vault_config.prompts_dir / "agents" / "default"
        for state in ["planning", "executing", "reviewing", "iterating"]:
            assert (default_dir / f"{state}.yaml").exists()

    def test_creates_researcher_override(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        assert (ops.vault_config.prompts_dir / "agents" / "researcher" / "executing.yaml").exists()
```

- [ ] **Step 4: Verify prompts load via PromptLoader**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run python -c "
from taim.brain.prompts import PromptLoader
from pathlib import Path
pl = PromptLoader(Path('../taim-vault/system/prompts'))
print(pl.load('agents/default/planning', {
    'task_description': 'test task',
    'agent_description': 'test agent',
    'user_preferences': '(none)',
})[:100])
"
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/brain/vault.py taim-vault/system/prompts/agents/ tests/backend/test_vault.py
git commit -m "feat: seed default per-state prompts and researcher override"
```

---

## Task 4: AgentRunStore

**Files:** `backend/src/taim/brain/agent_run_store.py`, `tests/backend/test_agent_run_store.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for AgentRunStore."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.agent_run_store import AgentRunStore
from taim.brain.database import init_database
from taim.models.agent import AgentState, AgentStateEnum, StateTransition


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    db = await init_database(tmp_path / "taim.db")
    s = AgentRunStore(db)
    yield s
    await db.close()


def _make_state(run_id: str = "r1", state: AgentStateEnum = AgentStateEnum.EXECUTING) -> AgentState:
    return AgentState(
        agent_name="researcher",
        run_id=run_id,
        current_state=state,
        iteration=1,
        cost_eur=0.05,
        state_history=[
            StateTransition(
                from_state=None,
                to_state=AgentStateEnum.PLANNING,
                timestamp=datetime.now(timezone.utc),
            ),
        ],
    )


@pytest.mark.asyncio
class TestUpsert:
    async def test_inserts(self, store: AgentRunStore) -> None:
        state = _make_state()
        await store.upsert(state, agent_name="researcher", task_id="task-1")
        async with store._db.execute("SELECT COUNT(*) FROM agent_runs") as cur:
            assert (await cur.fetchone())[0] == 1

    async def test_updates_on_conflict(self, store: AgentRunStore) -> None:
        state = _make_state()
        await store.upsert(state, agent_name="researcher", task_id="task-1")
        state.current_state = AgentStateEnum.DONE
        await store.upsert(state, agent_name="researcher", task_id="task-1")
        async with store._db.execute(
            "SELECT final_state FROM agent_runs WHERE run_id = ?", ("r1",)
        ) as cur:
            row = await cur.fetchone()
        assert row[0] == "DONE"

    async def test_sets_completed_at_on_terminal(self, store: AgentRunStore) -> None:
        state = _make_state()
        await store.upsert(state, agent_name="researcher", task_id="task-1")
        state.current_state = AgentStateEnum.DONE
        await store.upsert(state, agent_name="researcher", task_id="task-1")
        async with store._db.execute(
            "SELECT completed_at FROM agent_runs WHERE run_id = ?", ("r1",)
        ) as cur:
            row = await cur.fetchone()
        assert row[0] is not None


@pytest.mark.asyncio
class TestLoadActiveRuns:
    async def test_returns_non_terminal_only(self, store: AgentRunStore) -> None:
        # One running, one done, one failed
        await store.upsert(_make_state("r-run", AgentStateEnum.EXECUTING), "a", "t1")
        await store.upsert(_make_state("r-done", AgentStateEnum.DONE), "a", "t1")
        await store.upsert(_make_state("r-fail", AgentStateEnum.FAILED), "a", "t1")

        active = await store.load_active_runs()
        run_ids = {r["run_id"] for r in active}
        assert "r-run" in run_ids
        assert "r-done" not in run_ids
        assert "r-fail" not in run_ids
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement brain/agent_run_store.py**

(From design doc Section 6.)

- [ ] **Step 4: Run → PASS** (~5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/brain/agent_run_store.py tests/backend/test_agent_run_store.py
git commit -m "feat: add AgentRunStore for agent_runs SQLite persistence"
```

---

## Task 5: AgentStateMachine

**Files:** `backend/src/taim/brain/agent_state_machine.py`, `tests/backend/test_agent_state_machine.py`

This is the largest task. The state machine orchestrates all 7 states with prompt loading, Router calls, and SQLite serialization.

### 5.1 Implementation

```python
"""AgentStateMachine — autonomous agent execution through 7 states."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from uuid import uuid4

import structlog
from pydantic import BaseModel, ValidationError

from taim.brain.agent_run_store import AgentRunStore
from taim.brain.prompts import PromptLoader
from taim.errors import AllProvidersFailed, PromptNotFoundError
from taim.models.agent import (
    Agent, AgentRun, AgentState, AgentStateEnum, ReviewResult, StateTransition,
)
from taim.models.router import ModelTierEnum

logger = structlog.get_logger()


class TransitionEvent(BaseModel):
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
        router,
        prompt_loader: PromptLoader,
        run_store: AgentRunStore,
        task_id: str,
        task_description: str,
        session_id: str | None = None,
        team_id: str = "",
        user_preferences: str = "",
        on_transition: Callable[[TransitionEvent], Awaitable[None]] | None = None,
        run_id: str | None = None,
    ) -> None:
        self._agent = agent
        self._router = router
        self._prompts = prompt_loader
        self._store = run_store
        self._task_id = task_id
        self._task_description = task_description
        self._session_id = session_id
        self._team_id = team_id
        self._user_preferences = user_preferences or "(no preferences yet)"
        self._on_transition = on_transition
        self._state = AgentState(agent_name=agent.name, run_id=run_id or str(uuid4()))

    async def run(self) -> AgentRun:
        """Execute through states until DONE or FAILED."""
        await self._transition(AgentStateEnum.PLANNING, "initial")

        try:
            while self._state.current_state not in (AgentStateEnum.DONE, AgentStateEnum.FAILED):
                if self._state.current_state == AgentStateEnum.PLANNING:
                    await self._do_planning()
                elif self._state.current_state == AgentStateEnum.EXECUTING:
                    await self._do_executing()
                elif self._state.current_state == AgentStateEnum.REVIEWING:
                    await self._do_reviewing()
                elif self._state.current_state == AgentStateEnum.ITERATING:
                    await self._do_iterating()
                elif self._state.current_state == AgentStateEnum.WAITING:
                    # Step 8+ will handle approval flow
                    break
        except AllProvidersFailed as e:
            await self._transition(AgentStateEnum.FAILED, f"all_providers_failed: {e.detail}")
        except PromptNotFoundError as e:
            await self._transition(AgentStateEnum.FAILED, f"missing_prompt: {e.detail}")

        return self._build_run()

    async def _do_planning(self) -> None:
        prompt = await self._load_state_prompt(AgentStateEnum.PLANNING, {
            "task_description": self._task_description,
            "agent_description": self._agent.description,
            "user_preferences": self._user_preferences,
        })
        response = await self._call_llm(prompt)
        self._state.plan = response.content
        self._accumulate_cost(response)
        await self._transition(AgentStateEnum.EXECUTING, "planning_complete")

    async def _do_executing(self) -> None:
        prompt = await self._load_state_prompt(AgentStateEnum.EXECUTING, {
            "task_description": self._task_description,
            "agent_description": self._agent.description,
            "plan": self._state.plan,
            "iteration": str(self._state.iteration),
            "user_preferences": self._user_preferences,
        })
        response = await self._call_llm(prompt)
        self._state.current_result = response.content
        self._accumulate_cost(response)
        await self._transition(AgentStateEnum.REVIEWING, "execution_complete")

    async def _do_reviewing(self) -> None:
        prompt = await self._load_state_prompt(AgentStateEnum.REVIEWING, {
            "task_description": self._task_description,
            "current_result": self._state.current_result,
        })
        response = await self._call_llm(prompt, expected_format="json")
        self._accumulate_cost(response)

        try:
            review = ReviewResult(**json.loads(response.content))
        except (json.JSONDecodeError, ValidationError):
            # Fail-safe: accept current result (don't loop forever)
            await self._transition(AgentStateEnum.DONE, "review_unparseable_accepted_as_is")
            return

        self._state.review_feedback = review.feedback

        if review.quality_ok:
            await self._transition(AgentStateEnum.DONE, "review_passed")
        elif self._state.iteration >= self._agent.max_iterations:
            await self._transition(AgentStateEnum.DONE, f"max_iterations_reached_{self._agent.max_iterations}")
        else:
            await self._transition(AgentStateEnum.ITERATING, "review_failed_iterating")

    async def _do_iterating(self) -> None:
        self._state.iteration += 1
        prompt = await self._load_state_prompt(AgentStateEnum.ITERATING, {
            "task_description": self._task_description,
            "current_result": self._state.current_result,
            "review_feedback": self._state.review_feedback,
        })
        response = await self._call_llm(prompt)
        self._state.current_result = response.content
        self._accumulate_cost(response)
        await self._transition(AgentStateEnum.EXECUTING, f"iteration_{self._state.iteration}")

    async def _load_state_prompt(
        self, state: AgentStateEnum, variables: dict,
    ) -> str:
        state_name = state.value.lower()
        try:
            return self._prompts.load(f"agents/{self._agent.name}/{state_name}", variables)
        except PromptNotFoundError:
            return self._prompts.load(f"agents/default/{state_name}", variables)

    async def _call_llm(self, prompt: str, expected_format: str | None = None):
        tier_str = self._agent.model_preference[0] if self._agent.model_preference else "tier2_standard"
        tier = ModelTierEnum(tier_str)
        return await self._router.complete(
            messages=[{"role": "system", "content": prompt}],
            tier=tier,
            expected_format=expected_format,
            task_id=self._task_id,
            session_id=self._session_id,
            agent_run_id=self._state.run_id,
        )

    def _accumulate_cost(self, response) -> None:
        self._state.tokens_used += response.prompt_tokens + response.completion_tokens
        # Router tracks USD; we convert approximately. Full conversion is in display layer.
        self._state.cost_eur += response.cost_usd * 0.92

    async def _transition(self, to_state: AgentStateEnum, reason: str) -> None:
        prev = self._state.current_state if self._state.state_history else None
        ts = datetime.now(timezone.utc)
        self._state.state_history.append(StateTransition(
            from_state=prev,
            to_state=to_state,
            timestamp=ts,
            reason=reason,
        ))
        self._state.current_state = to_state

        await self._store.upsert(
            self._state,
            agent_name=self._agent.name,
            task_id=self._task_id,
            team_id=self._team_id,
            session_id=self._session_id,
        )

        if self._on_transition:
            try:
                await self._on_transition(TransitionEvent(
                    run_id=self._state.run_id,
                    agent_name=self._agent.name,
                    from_state=prev,
                    to_state=to_state,
                    iteration=self._state.iteration,
                    reason=reason,
                    timestamp=ts,
                ))
            except Exception:
                logger.exception("transition_callback.error", run_id=self._state.run_id)

    def _build_run(self) -> AgentRun:
        return AgentRun(
            run_id=self._state.run_id,
            agent_name=self._agent.name,
            task_id=self._task_id,
            team_id=self._team_id,
            session_id=self._session_id,
            final_state=self._state.current_state,
            state_history=self._state.state_history,
            cost_eur=self._state.cost_eur,
            result_content=self._state.current_result,
        )
```

### 5.2 Tests

```python
"""Tests for AgentStateMachine."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.agent_registry import AgentRegistry
from taim.brain.agent_run_store import AgentRunStore
from taim.brain.agent_state_machine import AgentStateMachine, TransitionEvent
from taim.brain.database import init_database
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.models.agent import Agent, AgentStateEnum

from conftest import MockRouter, make_response


def _make_agent(name: str = "researcher", max_iter: int = 2) -> Agent:
    return Agent(
        name=name,
        description=f"Test {name}",
        model_preference=["tier2_standard"],
        skills=[],
        max_iterations=max_iter,
    )


@pytest_asyncio.fixture
async def setup(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    db = await init_database(ops.vault_config.db_path)
    store = AgentRunStore(db)
    yield ops, loader, store
    await db.close()


@pytest.mark.asyncio
class TestHappyPath:
    async def test_planning_to_done(self, setup) -> None:
        _, loader, store = setup
        router = MockRouter([
            make_response("The plan is X"),                                             # PLANNING
            make_response("Execution result"),                                          # EXECUTING
            make_response('{"quality_ok": true, "feedback": "Good"}'),                  # REVIEWING
        ])
        sm = AgentStateMachine(
            agent=_make_agent(),
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="task-1",
            task_description="Research X",
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
        assert run.result_content == "Execution result"
        assert len(run.state_history) == 4  # initial+PLANNING, EXECUTING, REVIEWING, DONE

    async def test_transition_events(self, setup) -> None:
        _, loader, store = setup
        events: list[TransitionEvent] = []
        async def capture(e: TransitionEvent) -> None:
            events.append(e)
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": ""}'),
        ])
        sm = AgentStateMachine(
            agent=_make_agent(), router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
            on_transition=capture,
        )
        await sm.run()
        states = [e.to_state for e in events]
        assert states == [
            AgentStateEnum.PLANNING, AgentStateEnum.EXECUTING,
            AgentStateEnum.REVIEWING, AgentStateEnum.DONE,
        ]


@pytest.mark.asyncio
class TestIterationLoop:
    async def test_reviewing_to_iterating_to_executing(self, setup) -> None:
        _, loader, store = setup
        router = MockRouter([
            make_response("plan"),                                                      # PLANNING
            make_response("first result"),                                              # EXECUTING
            make_response('{"quality_ok": false, "feedback": "needs more detail"}'),    # REVIEWING
            make_response("improved result"),                                           # ITERATING
            make_response("re-executed result"),                                        # EXECUTING again
            make_response('{"quality_ok": true, "feedback": "better"}'),                # REVIEWING again
        ])
        sm = AgentStateMachine(
            agent=_make_agent(max_iter=3),
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
        assert run.result_content == "re-executed result"

    async def test_max_iterations_stops(self, setup) -> None:
        _, loader, store = setup
        # Always fail review. With max_iter=1, should hit DONE after 1 iteration
        router = MockRouter([
            make_response("plan"),
            make_response("r1"),
            make_response('{"quality_ok": false, "feedback": "bad"}'),
            make_response("r2"),         # iteration
            make_response("r3"),         # executing again
            make_response('{"quality_ok": false, "feedback": "still bad"}'),  # hits max
        ])
        sm = AgentStateMachine(
            agent=_make_agent(max_iter=1),
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
        # Last transition reason should indicate max_iterations
        assert "max_iterations" in run.state_history[-1].reason


@pytest.mark.asyncio
class TestFailure:
    async def test_all_providers_failed_transitions_to_failed(self, setup) -> None:
        from taim.errors import AllProvidersFailed
        _, loader, store = setup
        router = MockRouter([AllProvidersFailed(user_message="fail", detail="d")])
        sm = AgentStateMachine(
            agent=_make_agent(),
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.FAILED

    async def test_unparseable_review_accepts_result(self, setup) -> None:
        _, loader, store = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response("totally not json"),   # REVIEWING returns junk
        ])
        sm = AgentStateMachine(
            agent=_make_agent(),
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
        )
        run = await sm.run()
        # Fail-safe: accepted as-is
        assert run.final_state == AgentStateEnum.DONE


@pytest.mark.asyncio
class TestPromptFallback:
    async def test_uses_researcher_override_if_present(self, setup) -> None:
        """researcher/executing.yaml exists (seeded). The override should be loaded."""
        _, loader, store = setup
        # Manual test: load the override prompt directly and verify content
        override = loader.load("agents/researcher/executing", {
            "task_description": "x", "agent_description": "y", "plan": "p",
            "iteration": "0", "user_preferences": "(none)",
        })
        assert "Verify sources" in override or "researcher" in override.lower()

    async def test_falls_back_to_default_for_unknown_agent(self, setup) -> None:
        _, loader, store = setup
        # agent name "nonexistent" doesn't have a custom prompt dir; should fall back
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = Agent(
            name="nonexistent",
            description="No override",
            model_preference=["tier2_standard"],
            skills=[],
        )
        sm = AgentStateMachine(
            agent=agent,
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
```

- [ ] **Step 3: Run → FAIL**

- [ ] **Step 4: Implement agent_state_machine.py** (code above)

- [ ] **Step 5: Run → PASS** (8-9 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/src/taim/brain/agent_state_machine.py tests/backend/test_agent_state_machine.py
git commit -m "feat: add autonomous AgentStateMachine with 7 states and prompt fallback"
```

---

## Task 6: API Endpoints

**Files:**
- Create: `backend/src/taim/api/agents.py`
- Modify: `backend/src/taim/api/deps.py`
- Modify: `backend/src/taim/main.py` (lifespan + include_router)
- Create: `tests/backend/test_agents_api.py`

- [ ] **Step 1: Add get_registry() + get_agent_run_store() to deps.py**

Append to `backend/src/taim/api/deps.py`:
```python
from taim.brain.agent_registry import AgentRegistry
from taim.brain.agent_run_store import AgentRunStore


def get_registry(request: Request) -> AgentRegistry:
    """Inject the AgentRegistry singleton."""
    return request.app.state.agent_registry


def get_agent_run_store(request: Request) -> AgentRunStore:
    """Inject the AgentRunStore singleton."""
    return request.app.state.agent_run_store
```

- [ ] **Step 2: Create api/agents.py**

```python
"""Agent REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from taim.api.deps import get_registry
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
async def get_agent(
    agent_name: str,
    registry: AgentRegistry = Depends(get_registry),
) -> Agent:
    agent = registry.get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return agent
```

- [ ] **Step 3: Update main.py lifespan + create_app**

In lifespan, after Memory System initialization:
```python
    # 10. Agent Registry + Run Store
    from taim.brain.agent_registry import AgentRegistry
    from taim.brain.agent_run_store import AgentRunStore

    registry = AgentRegistry(system_config.vault.agents_dir)
    registry.load()
    run_store_agents = AgentRunStore(db)

    app.state.agent_registry = registry
    app.state.agent_run_store = run_store_agents
```

In `create_app()`, add:
```python
    from taim.api.agents import router as agents_router
    app.include_router(agents_router)
```

- [ ] **Step 4: Write API tests**

```python
"""Tests for /api/agents endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taim.api.agents import router as agents_router
from taim.brain.agent_registry import AgentRegistry
from taim.brain.vault import VaultOps


@pytest_asyncio.fixture
async def client(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    registry = AgentRegistry(ops.vault_config.agents_dir)
    registry.load()

    app = FastAPI()
    app.include_router(agents_router)
    app.state.agent_registry = registry

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
class TestListAgents:
    async def test_returns_all_agents(self, client) -> None:
        resp = await client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5
        names = {a["name"] for a in data["agents"]}
        assert names == {"researcher", "coder", "reviewer", "writer", "analyst"}


@pytest.mark.asyncio
class TestGetAgent:
    async def test_returns_specific_agent(self, client) -> None:
        resp = await client.get("/api/agents/researcher")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "researcher"
        assert "web_research" in data["skills"]

    async def test_404_for_unknown(self, client) -> None:
        resp = await client.get("/api/agents/nonexistent")
        assert resp.status_code == 404
```

- [ ] **Step 5: Run full suite + lint**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v
cd /Users/reykz/repositorys/TAIM/backend && uv run ruff check src/ && uv run ruff format src/
```

- [ ] **Step 6: Manual smoke test**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run uvicorn taim.main:app --host localhost --port 8003 > /tmp/taim-step5.log 2>&1 &
sleep 3
curl -s http://localhost:8003/api/agents | python3 -m json.tool
kill %1 2>/dev/null
cat /tmp/taim-step5.log | head -10
```
Expected: `taim.started`, 5 agents returned from `/api/agents`.

- [ ] **Step 7: Commit**

```bash
git add backend/src/taim/api/agents.py backend/src/taim/api/deps.py backend/src/taim/main.py tests/backend/test_agents_api.py
git commit -m "feat: wire AgentRegistry into FastAPI with /api/agents endpoints"
```

---

## Task 7: Final Verification

- [ ] **Step 1: Full suite + coverage**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest --cov=taim --cov-report=term-missing 2>&1 | tail -30
```

- [ ] **Step 2: Lint check**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run ruff check src/ && uv run ruff format --check src/
```

Fix/commit if needed.

---

## Summary

| Task | Module | Tests | Steps |
|------|--------|-------|-------|
| 1 | models/agent.py | test_agent_models.py | 5 |
| 2 | brain/agent_registry.py + 5 agents | test_agent_registry.py | 7 |
| 3 | 5 state prompts | test_vault.py (extend) | 5 |
| 4 | brain/agent_run_store.py | test_agent_run_store.py | 5 |
| 5 | brain/agent_state_machine.py | test_agent_state_machine.py | 6 |
| 6 | api/agents.py + deps + lifespan | test_agents_api.py | 7 |
| 7 | Verification | — | 2 |
| **Total** | **7 new modules** | **5 test files** | **37 steps** |

Parallelizable: Tasks 4 (run store) and 3 (prompts) are independent after Task 2.
