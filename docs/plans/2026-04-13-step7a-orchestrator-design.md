# Step 7a: Orchestrator — Minimal End-to-End — Implementation Design

> Version: 1.0
> Date: 2026-04-13
> Status: Reviewed
> Scope: Subset of Step 7 for reviewability. Single-agent end-to-end execution.
>
> **Important:** This is a PR-sizing partition, NOT a product scope reduction. Full Step 7 scope (US-4.1, US-4.2, US-4.3, US-4.5, US-5.2, US-5.3, US-5.4) will be delivered across 7a/7b/7c. All features remain in the product plan.

---

## 1. Overview

Step 7a builds the **first functioning end-to-end loop**: user types a request → IntentInterpreter extracts task → Orchestrator picks an agent → AgentStateMachine runs → result streams back via WebSocket.

```
WebSocket chat
    ↓ user message
IntentInterpreter (existing)
    ↓ IntentResult { task_type, objective, ... }
Orchestrator (NEW)
    ↓ rule-based agent selection
TaskManager (NEW)
    ↓ create task_state row
AgentStateMachine (existing, wired with ToolExecutor + SkillRegistry)
    ↓ runs + emits TransitionEvent + ToolExecutionEvent
WebSocket → client (agent_started, agent_state, tool_execution, agent_completed)
```

**What 7a delivers:**
- Rule-based Team Composer (task_type → primary agent) — no LLM composition yet
- TaskManager: task_state lifecycle (pending → running → completed/failed)
- Minimal Orchestrator: instantiates one AgentStateMachine per task
- WebSocket event forwarding: agent_started, agent_state, agent_completed, tool_execution
- Chat endpoint integration: IntentInterpreter `new_task` category triggers Orchestrator
- Basic task context passing (objective + parameters → agent)

**What 7b will add:**
- Multi-agent teams (Sequential pattern)
- Plan confirmation flow (plan_proposed + approval)
- Inter-agent result passing

**What 7c will add:**
- Context Assembler (token-budgeted, memory-aware)
- Parallel, Pipeline, Hierarchical patterns
- Pattern auto-selection
- LLM-based Team Composer (smarter agent selection)

All three deliver complete Step 7 scope.

---

## 2. Module Architecture

### 2.1 File Layout

```
backend/src/taim/
├── orchestrator/                              # EXISTS from Step 6a
│   ├── team_composer.py                       # NEW: rule-based composition
│   ├── task_manager.py                        # NEW: task_state lifecycle
│   └── orchestrator.py                        # NEW: main coordinator
├── models/
│   └── orchestration.py                       # NEW: TaskPlan, TaskExecutionResult
├── api/
│   └── chat.py                                # MODIFIED: wire orchestrator after IntentInterpreter
├── main.py                                    # MODIFIED: lifespan wires Orchestrator
```

### 2.2 Dependency Graph

```
models/orchestration.py                        (no TAIM deps)
    ↓
orchestrator/team_composer.py                  (depends on: AgentRegistry, IntentResult)
orchestrator/task_manager.py                   (depends on: aiosqlite, task_state schema)
    ↓
orchestrator/orchestrator.py                   (composes: Composer + TaskManager + AgentStateMachine factory)
    ↓
api/chat.py                                    (uses Orchestrator after interpreter returns new_task)
main.py                                        (lifespan creates Orchestrator)
```

---

## 3. Data Models (`models/orchestration.py`)

```python
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class TaskPlan(BaseModel):
    """What the Orchestrator decides to execute. Step 7a: single-agent only."""
    task_id: str
    objective: str
    parameters: dict[str, Any] = {}
    agent_name: str                            # single agent for 7a
    # Step 7b will add: agents: list[TeamAgentSlot], pattern: OrchestrationPattern


class TaskExecutionResult(BaseModel):
    """Final outcome of orchestrator run."""
    task_id: str
    status: TaskStatus
    agent_name: str
    result_content: str = ""
    tokens_used: int = 0
    cost_eur: float = 0.0
    duration_ms: float = 0.0
    error: str = ""
```

---

## 4. Team Composer (`orchestrator/team_composer.py`)

**Responsibility:** Given an `IntentResult`, pick the primary agent. Rule-based for 7a.

```python
from taim.brain.agent_registry import AgentRegistry
from taim.models.agent import Agent
from taim.models.chat import IntentResult


# Rule-based mapping: task_type → agent priority list
_TASK_TYPE_TO_AGENTS = {
    "research": ["researcher", "analyst"],
    "code": ["coder", "reviewer"],
    "code_review": ["reviewer", "coder"],
    "code_generation": ["coder"],
    "writing": ["writer", "researcher"],
    "content": ["writer"],
    "content_writing": ["writer"],
    "analysis": ["analyst", "researcher"],
    "data_analysis": ["analyst"],
}


class TeamComposer:
    """Selects agents for a task. Rule-based in 7a; LLM-based in 7c."""

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    def compose_single_agent(self, intent: IntentResult) -> Agent | None:
        """Return the best matching single agent for this task.
        Returns None if no suitable agent found."""
        # 1) Explicit suggestion from intent
        for name in intent.suggested_team or []:
            agent = self._registry.get_agent(name)
            if agent:
                return agent

        # 2) Rule-based by task_type
        task_type_lower = (intent.task_type or "").lower()
        for pattern, candidates in _TASK_TYPE_TO_AGENTS.items():
            if pattern in task_type_lower:
                for candidate in candidates:
                    agent = self._registry.get_agent(candidate)
                    if agent:
                        return agent

        # 3) Skill-based fallback: find agent with relevant skill
        keywords = task_type_lower.split("_") + intent.objective.lower().split()
        for agent in self._registry.list_agents():
            for skill in agent.skills:
                if any(kw in skill.lower() for kw in keywords if len(kw) > 3):
                    return agent

        # 4) Last resort: any available agent
        agents = self._registry.list_agents()
        return agents[0] if agents else None
```

**Step 7b will add:** `compose_team(intent) -> TeamPlan` with multiple agents + pattern.
**Step 7c will add:** LLM-based composition using `team-composer.yaml` prompt.

---

## 5. Task Manager (`orchestrator/task_manager.py`)

**Responsibility:** Create, update, query task_state SQLite rows.

```python
import json
from datetime import datetime, timezone

import aiosqlite

from taim.models.orchestration import TaskPlan, TaskStatus


class TaskManager:
    """Lifecycle management for task_state SQLite rows."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(self, plan: TaskPlan, team_id: str = "") -> None:
        agent_states_json = json.dumps({plan.agent_name: "pending"})
        await self._db.execute(
            """INSERT INTO task_state
               (task_id, team_id, status, objective, agent_states, token_total, cost_total_eur)
               VALUES (?, ?, 'pending', ?, ?, 0, 0.0)""",
            (plan.task_id, team_id, plan.objective, agent_states_json),
        )
        await self._db.commit()

    async def set_status(
        self,
        task_id: str,
        status: TaskStatus,
        tokens: int | None = None,
        cost_eur: float | None = None,
    ) -> None:
        fields = ["status = ?", "updated_at = datetime('now')"]
        params: list = [status.value]

        if tokens is not None:
            fields.append("token_total = ?")
            params.append(tokens)
        if cost_eur is not None:
            fields.append("cost_total_eur = ?")
            params.append(cost_eur)
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED):
            fields.append("completed_at = datetime('now')")

        params.append(task_id)
        await self._db.execute(
            f"UPDATE task_state SET {', '.join(fields)} WHERE task_id = ?",
            params,
        )
        await self._db.commit()

    async def update_agent_states(
        self,
        task_id: str,
        agent_states: dict[str, str],
    ) -> None:
        await self._db.execute(
            "UPDATE task_state SET agent_states = ?, updated_at = datetime('now') WHERE task_id = ?",
            (json.dumps(agent_states), task_id),
        )
        await self._db.commit()

    async def list_recent(self, limit: int = 20) -> list[dict]:
        async with self._db.execute(
            """SELECT task_id, team_id, status, objective, token_total, cost_total_eur,
                      created_at, completed_at
               FROM task_state
               ORDER BY created_at DESC
               LIMIT ?""",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {
                "task_id": r[0], "team_id": r[1], "status": r[2],
                "objective": r[3], "token_total": r[4], "cost_total_eur": r[5],
                "created_at": r[6], "completed_at": r[7],
            }
            for r in rows
        ]
```

---

## 6. Orchestrator (`orchestrator/orchestrator.py`)

**Responsibility:** Main coordinator. Takes IntentResult → composes plan → creates task → runs agent → returns result.

```python
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import structlog

from taim.brain.agent_registry import AgentRegistry
from taim.brain.agent_run_store import AgentRunStore
from taim.brain.agent_state_machine import AgentStateMachine, TransitionEvent
from taim.brain.prompts import PromptLoader
from taim.brain.skill_registry import SkillRegistry
from taim.models.chat import IntentResult
from taim.models.orchestration import TaskPlan, TaskExecutionResult, TaskStatus
from taim.models.tool import ToolExecutionEvent
from taim.orchestrator.task_manager import TaskManager
from taim.orchestrator.team_composer import TeamComposer
from taim.orchestrator.tools import ToolExecutor

logger = structlog.get_logger()


# Callback signatures for WebSocket forwarding
AgentEventCallback = Callable[[TransitionEvent], Awaitable[None]]
ToolEventCallback = Callable[[ToolExecutionEvent], Awaitable[None]]


class Orchestrator:
    """Minimal end-to-end orchestrator: Intent → Single Agent → Result."""

    def __init__(
        self,
        composer: TeamComposer,
        task_manager: TaskManager,
        agent_registry: AgentRegistry,
        agent_run_store: AgentRunStore,
        prompt_loader: PromptLoader,
        router,                                 # LLMRouter
        tool_executor: ToolExecutor | None = None,
        tool_context: dict[str, Any] | None = None,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self._composer = composer
        self._task_manager = task_manager
        self._agent_registry = agent_registry
        self._agent_run_store = agent_run_store
        self._prompt_loader = prompt_loader
        self._router = router
        self._tool_executor = tool_executor
        self._tool_context = tool_context or {}
        self._skill_registry = skill_registry

    async def execute(
        self,
        intent: IntentResult,
        session_id: str,
        user_preferences: str = "",
        on_agent_event: AgentEventCallback | None = None,
        on_tool_event: ToolEventCallback | None = None,
    ) -> TaskExecutionResult:
        """Execute a task end-to-end. Returns final result or failure."""
        task_id = str(uuid4())
        start = time.monotonic()

        # 1. Compose: pick agent
        agent = self._composer.compose_single_agent(intent)
        if agent is None:
            return TaskExecutionResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                agent_name="",
                error="No suitable agent available for this task type.",
            )

        # 2. Build plan
        plan = TaskPlan(
            task_id=task_id,
            objective=intent.objective,
            parameters=intent.parameters,
            agent_name=agent.name,
        )

        # 3. Create task_state row
        await self._task_manager.create(plan)
        await self._task_manager.set_status(task_id, TaskStatus.RUNNING)

        # 4. Build task description combining objective + parameters
        task_description = self._build_task_description(intent)

        # 5. Run the agent via state machine
        try:
            sm = AgentStateMachine(
                agent=agent,
                router=self._router,
                prompt_loader=self._prompt_loader,
                run_store=self._agent_run_store,
                task_id=task_id,
                task_description=task_description,
                session_id=session_id,
                user_preferences=user_preferences,
                on_transition=on_agent_event,
                tool_executor=self._tool_executor,
                tool_context=self._tool_context,
                on_tool_event=on_tool_event,
                skill_registry=self._skill_registry,
            )
            run = await sm.run()
        except Exception as e:
            logger.exception("orchestrator.agent_crashed", task_id=task_id)
            await self._task_manager.set_status(task_id, TaskStatus.FAILED)
            return TaskExecutionResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                agent_name=agent.name,
                error=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            )

        # 6. Map agent outcome → task status
        from taim.models.agent import AgentStateEnum
        status = (
            TaskStatus.COMPLETED if run.final_state == AgentStateEnum.DONE
            else TaskStatus.FAILED
        )
        cost_eur_int = int(run.cost_eur * 10000) / 10000  # precision
        await self._task_manager.set_status(
            task_id,
            status,
            tokens=run.prompt_tokens + run.completion_tokens,
            cost_eur=cost_eur_int,
        )

        return TaskExecutionResult(
            task_id=task_id,
            status=status,
            agent_name=agent.name,
            result_content=run.result_content,
            tokens_used=run.prompt_tokens + run.completion_tokens,
            cost_eur=run.cost_eur,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    def _build_task_description(self, intent: IntentResult) -> str:
        parts = [intent.objective]
        if intent.parameters:
            param_lines = [f"- {k}: {v}" for k, v in intent.parameters.items()]
            parts.append("Parameters:\n" + "\n".join(param_lines))
        return "\n\n".join(parts)
```

---

## 7. WebSocket Integration (`api/chat.py`)

The chat endpoint currently calls `interpreter.interpret()` and sends back `intent`/`system` events. Step 7a extends it: when intent is `NEW_TASK`, invoke the Orchestrator and forward its events.

### 7.1 New Event Types

- `agent_started`: agent began work
- `agent_state`: state machine transitioned
- `agent_completed`: agent finished (success or failure)
- `tool_execution`: tool call running/completed/failed
- `task_completed`: final task result with summary + metrics

### 7.2 Flow

```python
# On NEW_TASK intent (and orchestrator is available):
if (
    result.intent is not None
    and result.classification.category == IntentCategory.NEW_TASK
    and not result.needs_followup
    and orchestrator is not None
):
    await websocket.send_json({"type": "agent_started", ...})

    async def fwd_agent_event(event: TransitionEvent) -> None:
        await websocket.send_json({
            "type": "agent_state",
            "agent_name": event.agent_name,
            "from_state": event.from_state.value if event.from_state else None,
            "to_state": event.to_state.value,
            "iteration": event.iteration,
            "reason": event.reason,
            "session_id": session_id,
        })

    async def fwd_tool_event(event: ToolExecutionEvent) -> None:
        await websocket.send_json({
            "type": "tool_execution",
            "content": event.summary,
            "agent_name": event.agent_name,
            "tool_name": event.tool_name,
            "tool_status": event.status,
            "duration_ms": event.duration_ms,
            "session_id": session_id,
        })

    user_prefs = ""
    if memory_manager is not None:
        user_prefs = await memory_manager.get_preferences_text()

    task_result = await orchestrator.execute(
        intent=result.intent,
        session_id=session_id,
        user_preferences=user_prefs,
        on_agent_event=fwd_agent_event,
        on_tool_event=fwd_tool_event,
    )

    await websocket.send_json({
        "type": "agent_completed" if task_result.status == TaskStatus.COMPLETED else "error",
        "content": task_result.result_content or task_result.error,
        "agent_name": task_result.agent_name,
        "tokens_used": task_result.tokens_used,
        "cost_eur": task_result.cost_eur,
        "duration_ms": task_result.duration_ms,
        "session_id": session_id,
    })

    # Append to hot memory as assistant response
    hot.append_message(session_id, "assistant", task_result.result_content or task_result.error)
    await store.persist(hot.get_or_create(session_id))
    continue  # skip the generic intent response below
```

The existing flow (followups, non-new-task intents) is preserved.

---

## 8. Lifespan Integration (`main.py`)

After SkillRegistry (block 12), add:

```python
    # 13. Orchestrator
    from taim.orchestrator.orchestrator import Orchestrator
    from taim.orchestrator.task_manager import TaskManager
    from taim.orchestrator.team_composer import TeamComposer

    task_manager = TaskManager(db)
    team_composer = TeamComposer(registry)

    orchestrator = Orchestrator(
        composer=team_composer,
        task_manager=task_manager,
        agent_registry=registry,
        agent_run_store=agent_run_store,
        prompt_loader=prompt_loader,
        router=llm_router,
        tool_executor=tool_executor,
        tool_context=app.state.tool_context,
        skill_registry=skill_registry,
    )

    app.state.task_manager = task_manager
    app.state.team_composer = team_composer
    app.state.orchestrator = orchestrator

    logger.info("orchestrator.ready")
```

---

## 9. REST API: `GET /api/tasks`

Add `backend/src/taim/api/tasks.py`:

```python
from fastapi import APIRouter, Depends, Query

from taim.api.deps import get_task_manager
from taim.orchestrator.task_manager import TaskManager

router = APIRouter(prefix="/api/tasks")


@router.get("")
async def list_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    manager: TaskManager = Depends(get_task_manager),
) -> dict:
    tasks = await manager.list_recent(limit=limit)
    return {"tasks": tasks, "count": len(tasks)}
```

Register in `create_app()`. Add `get_task_manager()` + `get_orchestrator()` to `deps.py`.

---

## 10. Critical Review Findings

| # | Finding | Resolution |
|---|---------|------------|
| 1 | Rule-based composition too rigid? | Documented as Step 7a placeholder. Step 7c replaces with LLM-based. Rules cover 80% of PRD acceptance criteria for 7a. |
| 2 | No plan confirmation for single-agent | PRD US-4.2 AC4: "Single-agent tasks skip team orchestration entirely and execute the agent directly." Explicit design decision, not cutting corner. |
| 3 | Orchestrator ctor has many deps | 8 params but all reasonable — composer, task_manager, registry, run_store, prompt_loader, router, tool_executor, skill_registry. Grouped by source (brain/router/orchestrator). Acceptable for MVP. |
| 4 | Agent crashes → task FAILED without retry | State machine already handles Router failover internally. Orchestrator-level retry is future optimization. |
| 5 | No support yet for memory-aware context | Memory gets loaded for `user_preferences` text only. Full Context Assembler is 7c. |
| 6 | Interpreter still None-checked | Orchestrator is injected via lifespan; WebSocket falls back gracefully if not present (should not happen in prod). |
| 7 | Chat endpoint `continue` skips intent event | After orchestrator execute, we want `agent_completed` instead of the generic `intent` event. Mutually exclusive. |
| 8 | Token totals from sum of prompt+completion, USD→EUR | Stored as cost_eur directly from AgentState (agent_state_machine.py uses 0.92 rate). Consistent. |

---

## 11. Expansion Stages

### Step 7b (next)
- `TeamComposer.compose_team(intent) -> TeamPlan` with multiple agents
- `OrchestrationPattern` enum in models
- Sequential orchestration loop (run agent, collect output, pass to next)
- `plan_proposed` WebSocket event + `approval` client message
- Plan modification rounds (max 2)
- Inter-agent result passing (previous_result in task context)
- Update Orchestrator.execute to handle teams

### Step 7c (final)
- Full Context Assembler class with token budget + memory retrieval
- Pattern implementations: Parallel (asyncio.gather), Pipeline, Hierarchical
- Pattern auto-selection (based on task_type analysis)
- LLM-based TeamComposer using `team-composer.yaml` prompt
- Agent output truncation (1000 token limit when passed as context)

### Step 8
- Heartbeat Manager on top of task_state table
- Auto-resume active runs on startup
- Budget warnings (80% of limit)

---

## 12. Test Strategy

| Test File | Module | Notable Tests |
|-----------|--------|---------------|
| `test_orchestration_models.py` | models/orchestration.py | TaskPlan, TaskExecutionResult |
| `test_team_composer.py` | team_composer.py | Suggested team wins, task_type mapping, skill fallback, empty registry |
| `test_task_manager.py` | task_manager.py | Create, set_status, update_agent_states, list_recent |
| `test_orchestrator.py` | orchestrator.py | Happy path (intent → agent → result), no agent found, agent fails, events forwarded |
| `test_tasks_api.py` | api/tasks.py | GET /api/tasks returns list |
| `test_chat_orchestration.py` | api/chat.py | new_task triggers orchestrator, agent events sent, task_completed emitted |

Coverage target: >85% on new modules.

---

*End of Step 7a Design.*
