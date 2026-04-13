# Step 7a: Orchestrator — Implementation Plan

> **Note:** This is part 1 of 3 for Step 7 (product scope unchanged — just PR sizing).

**Goal:** First end-to-end loop — user message → intent → orchestrator → single agent runs → result streamed back.

**Architecture:** Rule-based TeamComposer + TaskManager + minimal Orchestrator. Design: `docs/plans/2026-04-13-step7a-orchestrator-design.md`.

---

## File Structure

### Files to Create
```
backend/src/taim/models/orchestration.py
backend/src/taim/orchestrator/team_composer.py
backend/src/taim/orchestrator/task_manager.py
backend/src/taim/orchestrator/orchestrator.py
backend/src/taim/api/tasks.py
tests/backend/test_orchestration_models.py
tests/backend/test_team_composer.py
tests/backend/test_task_manager.py
tests/backend/test_orchestrator.py
tests/backend/test_tasks_api.py
tests/backend/test_chat_orchestration.py
```

### Files to Modify
```
backend/src/taim/main.py        # Orchestrator in lifespan + tasks router
backend/src/taim/api/deps.py    # get_orchestrator, get_task_manager
backend/src/taim/api/chat.py    # Wire orchestrator for NEW_TASK intents
```

---

## Task 1: Orchestration Models

**Files:** `backend/src/taim/models/orchestration.py`, `tests/backend/test_orchestration_models.py`

```python
# models/orchestration.py
from __future__ import annotations
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
    task_id: str
    objective: str
    parameters: dict[str, Any] = {}
    agent_name: str


class TaskExecutionResult(BaseModel):
    task_id: str
    status: TaskStatus
    agent_name: str
    result_content: str = ""
    tokens_used: int = 0
    cost_eur: float = 0.0
    duration_ms: float = 0.0
    error: str = ""
```

Tests: enum values, defaults for TaskPlan + TaskExecutionResult.

Steps: Write tests → FAIL → implement → PASS → commit.

## Task 2: TeamComposer

**Files:** `backend/src/taim/orchestrator/team_composer.py`, `tests/backend/test_team_composer.py`

Full implementation from design Section 4.

Tests:
- suggested_team wins when provided
- task_type "research" → researcher
- task_type "code_review" → reviewer (matches "code_review" pattern)
- skill-based fallback
- no agents in registry → returns None
- unknown task_type → skill-based or first agent

## Task 3: TaskManager

**Files:** `backend/src/taim/orchestrator/task_manager.py`, `tests/backend/test_task_manager.py`

Full implementation from design Section 5.

Tests:
- create inserts row with pending status
- set_status updates status + completed_at for terminal
- update_agent_states writes JSON
- list_recent returns in reverse chrono order with limit

## Task 4: Orchestrator

**Files:** `backend/src/taim/orchestrator/orchestrator.py`, `tests/backend/test_orchestrator.py`

Full implementation from design Section 6.

Tests (using MockRouter + tmp_vault + AgentStateMachine real):
- Happy path: intent → agent picked → runs → COMPLETED
- No agent found (empty registry) → FAILED with error
- Agent transitions forwarded via on_agent_event callback
- Tool events forwarded via on_tool_event callback
- Task status updated through lifecycle (pending → running → completed)
- Metrics stored (tokens, cost_eur)

## Task 5: Tasks API

**Files:** `backend/src/taim/api/tasks.py`, `tests/backend/test_tasks_api.py`

```python
# api/tasks.py
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

Tests: GET /api/tasks returns {tasks: [], count: 0} when empty, returns created tasks.

## Task 6: deps.py additions

Append to `backend/src/taim/api/deps.py`:
```python
from taim.orchestrator.orchestrator import Orchestrator
from taim.orchestrator.task_manager import TaskManager


def get_task_manager(request: Request) -> TaskManager:
    return request.app.state.task_manager


def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator
```

## Task 7: main.py lifespan + chat integration

### Step 7.1: Add block 13 in lifespan (after SkillRegistry)

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

### Step 7.2: Register tasks router in create_app()

```python
    from taim.api.tasks import router as tasks_router
    app.include_router(tasks_router)
```

### Step 7.3: Modify `api/chat.py` to wire orchestrator for new_task

Read the current file. In the WebSocket loop, after `result = await interpreter.interpret(...)` and the existing response construction, add orchestrator invocation for new_task intents.

The key modification: after getting the InterpreterResult, check if it's a new_task and the orchestrator is available. If so, forward to orchestrator and send agent events instead of the generic `intent` response.

```python
            # After existing interpret + response_text construction:
            # (The existing code sends `intent`/`system` + persists)

            # BUT: for actionable new_task intents, override with orchestrator execution
            orchestrator = getattr(websocket.app.state, "orchestrator", None)
            if (
                orchestrator is not None
                and result.intent is not None
                and result.classification.category == IntentCategory.NEW_TASK
                and not result.needs_followup
            ):
                # Don't send the generic intent response — replace with orchestrator flow
                # (Undo the append of response_text; send agent_started instead)
                # NOTE: need to refactor so generic intent event is skipped
                ...
```

Careful refactor: the existing code already sent response_text to hot memory + websocket. We need to branch EARLIER. Move the orchestrator check BEFORE the generic response send.

Revised flow:
```python
            try:
                result = await interpreter.interpret(...)
            except Exception:
                ...error...
                continue

            orchestrator = getattr(websocket.app.state, "orchestrator", None)
            memory_manager = getattr(websocket.app.state, "memory", None)

            # Branch: orchestrator path for new_task
            if (
                orchestrator is not None
                and result.intent is not None
                and result.classification.category == IntentCategory.NEW_TASK
                and not result.needs_followup
            ):
                await _run_orchestrator(
                    websocket, orchestrator, memory_manager, hot, store,
                    session_id, result.intent, result.classification,
                )
                continue

            # Non-orchestrator path: generic intent/system response (existing code)
            response_text = (
                result.direct_response
                or result.followup_question
                or _summarize_intent(result.intent)
            )
            hot.append_message(session_id, "assistant", response_text)
            await store.persist(hot.get_or_create(session_id))
            ...
```

Add `_run_orchestrator` helper that does:
1. Send `agent_started` event
2. Set up callbacks that forward agent_state + tool_execution events
3. Call `orchestrator.execute(intent, session_id, user_preferences, on_agent_event, on_tool_event)`
4. Send `agent_completed` or `error` event with final content
5. Append final content to hot memory + persist

### Step 7.4: Integration tests (`test_chat_orchestration.py`)

Use TestClient with a mocked MockRouter producing canned responses for:
1. Intent classification (new_task with confidence >=0.80, needs_deep=True)
2. Intent understanding (returns IntentResult)
3. Agent planning + executing + reviewing sequence

Test verifies websocket receives: thinking → agent_started → agent_state (multiple) → agent_completed with result_content.

## Task 8: Final verification

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest --cov=taim --cov-report=term-missing | tail -20
cd /Users/reykz/repositorys/TAIM/backend && uv run ruff check src/ && uv run ruff format src/
```

Smoke test:
```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run uvicorn taim.main:app --host localhost --port 8006 > /tmp/taim-step7a.log 2>&1 &
sleep 3
curl -s http://localhost:8006/api/tasks | python3 -m json.tool
cat /tmp/taim-step7a.log | grep -E "orchestrator|task" | head
kill %1
```

Expected: `orchestrator.ready` in logs, `/api/tasks` returns empty list.

---

## Summary

| Task | Module | Tests | Steps |
|------|--------|-------|-------|
| 1 | models/orchestration.py | test_orchestration_models.py | 5 |
| 2 | team_composer.py | test_team_composer.py | 5 |
| 3 | task_manager.py | test_task_manager.py | 5 |
| 4 | orchestrator.py | test_orchestrator.py | 6 |
| 5 | api/tasks.py | test_tasks_api.py | 4 |
| 6 | deps.py + main.py + chat.py | test_chat_orchestration.py | 7 |
| 7 | Verification | — | 3 |
| **Total** | **5 new modules** | **6 test files** | **35 steps** |
