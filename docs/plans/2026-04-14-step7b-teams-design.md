# Step 7b: Multi-Agent Teams + Plan Confirmation — Design + Plan

> Version: 1.0
> Date: 2026-04-14
> Status: Reviewed
> Scope: US-4.1 (multi-agent composition), US-4.3 (plan confirmation), US-5.3 (inter-agent result passing), Sequential pattern from US-4.2

---

## 1. Overview

Step 7b evolves tAIm from single-agent to **multi-agent team execution**:

```
User: "Research SaaS competitors and write a report"
    ↓
IntentInterpreter → IntentResult(task_type="research", ...)
    ↓
TeamComposer.compose_team() → [researcher, analyst] (2 agents)
    ↓
plan_proposed WebSocket event → User sees team plan
    ↓
User: "go" (confirmation)
    ↓
Orchestrator.execute_team() → researcher runs → analyst runs (sequential, result passing)
    ↓
agent_completed with final output
```

**Key additions over 7a:**
1. `TeamComposer.compose_team()` — returns multiple agents
2. `OrchestrationPattern.SEQUENTIAL` — run agents in order
3. `plan_proposed` → user confirmation → execution
4. Inter-agent result passing — agent N+1 gets agent N's truncated output
5. Plan modification (max 2 rounds) — user can adjust before execution

---

## 2. Model Changes

### 2.1 New Models (`models/orchestration.py` additions)

```python
class OrchestrationPattern(str, Enum):
    SEQUENTIAL = "sequential"
    # Step 7c: PARALLEL, PIPELINE, HIERARCHICAL


class TeamAgentSlot(BaseModel):
    """One agent assigned to a role in a team."""
    role: str           # e.g., "researcher", "reviewer"
    agent_name: str     # must exist in AgentRegistry
```

### 2.2 Evolve TaskPlan

Replace `agent_name: str` with `agents: list[TeamAgentSlot]`:

```python
class TaskPlan(BaseModel):
    task_id: str
    objective: str
    parameters: dict[str, Any] = {}
    agents: list[TeamAgentSlot]                # was: agent_name: str
    pattern: OrchestrationPattern = OrchestrationPattern.SEQUENTIAL
    estimated_cost_eur: float = 0.0

    @property
    def is_single_agent(self) -> bool:
        return len(self.agents) == 1

    @property
    def primary_agent_name(self) -> str:
        return self.agents[0].agent_name if self.agents else ""
```

Update Orchestrator + TaskManager where they reference `plan.agent_name` → `plan.primary_agent_name` or iterate `plan.agents`.

---

## 3. TeamComposer — `compose_team()`

```python
_TASK_TYPE_TO_TEAM = {
    "research": [("researcher", "researcher"), ("analyst", "analyst")],
    "code_generation": [("coder", "coder"), ("reviewer", "reviewer")],
    "code_review": [("reviewer", "reviewer")],
    "code": [("coder", "coder"), ("reviewer", "reviewer")],
    "writing": [("researcher", "researcher"), ("writer", "writer")],
    "content_writing": [("writer", "writer")],
    "content": [("writer", "writer")],
    "data_analysis": [("analyst", "analyst")],
    "analysis": [("analyst", "analyst"), ("researcher", "researcher")],
}


def compose_team(self, intent: IntentResult) -> list[TeamAgentSlot]:
    """Select multiple agents for a task. Falls back to single if needed."""
    # 1) Explicit suggestion
    if intent.suggested_team:
        slots = []
        for name in intent.suggested_team:
            if self._registry.get_agent(name):
                slots.append(TeamAgentSlot(role=name, agent_name=name))
        if slots:
            return slots

    # 2) Rule-based team
    task_type_lower = (intent.task_type or "").lower()
    for pattern, team_def in _TASK_TYPE_TO_TEAM.items():
        if pattern in task_type_lower:
            slots = []
            for role, agent_name in team_def:
                if self._registry.get_agent(agent_name):
                    slots.append(TeamAgentSlot(role=role, agent_name=agent_name))
            if slots:
                return slots

    # 3) Fallback to single agent
    agent = self.compose_single_agent(intent)
    if agent:
        return [TeamAgentSlot(role="primary", agent_name=agent.name)]
    return []
```

---

## 4. Sequential Orchestration Loop

```python
async def execute_team(
    self,
    plan: TaskPlan,
    intent: IntentResult,
    session_id: str,
    user_preferences: str = "",
    on_agent_event: AgentEventCallback | None = None,
    on_tool_event: ToolEventCallback | None = None,
) -> TaskExecutionResult:
    """Run agents sequentially, passing results between them."""
    start = time.monotonic()
    await self._task_manager.set_status(plan.task_id, TaskStatus.RUNNING)

    base_task_description = self._build_task_description(intent)
    previous_result = ""
    previous_agent = ""
    final_result = ""
    total_cost = 0.0
    final_agent = ""

    for slot in plan.agents:
        agent = self._agent_registry.get_agent(slot.agent_name)
        if not agent:
            continue

        # Build context with previous agent's output
        task_description = base_task_description
        if previous_result:
            truncated = previous_result[:4000]  # ~1000 tokens cap
            task_description += f"\n\nPrevious agent ({previous_agent}) output:\n{truncated}"

        try:
            sm = AgentStateMachine(
                agent=agent,
                router=self._router,
                prompt_loader=self._prompt_loader,
                run_store=self._agent_run_store,
                task_id=plan.task_id,
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
            logger.exception("orchestrator.agent_failed", agent=slot.agent_name)
            await self._task_manager.set_status(plan.task_id, TaskStatus.FAILED)
            return TaskExecutionResult(
                task_id=plan.task_id,
                status=TaskStatus.FAILED,
                agent_name=slot.agent_name,
                error=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            )

        previous_result = run.result_content
        previous_agent = slot.agent_name
        total_cost += run.cost_eur
        final_result = run.result_content
        final_agent = slot.agent_name

        # If agent failed, stop the team
        if run.final_state != AgentStateEnum.DONE:
            await self._task_manager.set_status(plan.task_id, TaskStatus.FAILED)
            return TaskExecutionResult(
                task_id=plan.task_id,
                status=TaskStatus.FAILED,
                agent_name=slot.agent_name,
                result_content=run.result_content,
                cost_eur=total_cost,
                error=f"Agent {slot.agent_name} failed",
                duration_ms=(time.monotonic() - start) * 1000,
            )

    await self._task_manager.set_status(plan.task_id, TaskStatus.COMPLETED, cost_eur=total_cost)

    return TaskExecutionResult(
        task_id=plan.task_id,
        status=TaskStatus.COMPLETED,
        agent_name=final_agent,
        result_content=final_result,
        cost_eur=total_cost,
        duration_ms=(time.monotonic() - start) * 1000,
    )
```

---

## 5. Plan Confirmation Flow in Chat

### 5.1 Session State

Add `pending_plan` tracking to the WebSocket handler:

```python
# Per-session state alongside HotMemory
pending_plans: dict[str, tuple[TaskPlan, IntentResult, int]] = {}
# session_id → (plan, intent, modification_rounds)
```

Store on `app.state.pending_plans` (simple dict, no persistence needed).

### 5.2 Flow

```
Message arrives
    ↓
Is there a pending_plan for this session?
├── YES → Route to plan confirmation handler
│   ├── User confirms ("yes", "go", "do it") → execute pending plan
│   ├── User modifies ("without reviewer", "add writer") → re-compose (max 2 rounds)
│   └── User cancels ("cancel", "no") → clear pending plan
└── NO → Normal interpreter flow
    ├── new_task with >1 agent → compose team, send plan_proposed, store pending_plan
    ├── new_task with 1 agent → single-agent execution (existing 7a path)
    └── other categories → existing handler
```

### 5.3 Plan Proposed Event

```json
{
  "type": "plan_proposed",
  "content": "I've assembled a team for this task:",
  "session_id": "...",
  "plan": {
    "task_id": "...",
    "objective": "...",
    "agents": [
      {"role": "researcher", "agent_name": "researcher"},
      {"role": "analyst", "agent_name": "analyst"}
    ],
    "pattern": "sequential",
    "estimated_cost_eur": 0.0
  }
}
```

### 5.4 Confirmation Detection

Use existing IntentInterpreter Stage 1:
- `confirmation` category → execute
- `stop_command` → cancel
- `follow_up` → modification (re-compose with adjustment)
- `new_task` → treat as new request, clear pending plan

For modification: pass the user's modification message to a simple string analysis (check for "without", "skip", "add", "only"). If Stage 1 confidence < 0.80, interpret deeper.

Simpler for 7b: on non-confirmation, non-stop response → re-compose with user's text as additional context. Don't try to parse adjustments — let the composer's rules handle it.

---

## 6. Critical Review Findings

| # | Finding | Resolution |
|---|---------|------------|
| 1 | TaskPlan backward compatibility | `primary_agent_name` property for single-agent path. Orchestrator.execute() updated to use plan.agents |
| 2 | Plan confirmation adds complexity to chat handler | Isolated in `_handle_pending_plan()` helper. Clear state transitions. |
| 3 | Inter-agent result truncation | 4000 chars (≈1000 tokens). Character-based for simplicity. Full token counting in 7c. |
| 4 | Pending plan lost on server restart | Acceptable for MVP — plans are volatile, user would re-request |
| 5 | Agent failure mid-team | Stop team, return FAILED with partial results from last successful agent |
| 6 | Max 2 modification rounds | After 2, execute latest plan regardless (US-4.3 AC4) |

---

## 7. Implementation Plan

### Task 1: Model evolution + compose_team()

- Modify `models/orchestration.py`: add OrchestrationPattern, TeamAgentSlot, evolve TaskPlan
- Modify `orchestrator/team_composer.py`: add `compose_team()`
- Update `orchestrator/task_manager.py` where it uses `plan.agent_name`
- Update tests for backward compat

### Task 2: Sequential execute_team() in Orchestrator

- Modify `orchestrator/orchestrator.py`: add `execute_team()` with sequential loop + result passing
- Refactor existing `execute()` to use new plan format
- Tests: multi-agent sequential, inter-agent result passing, agent failure stops team

### Task 3: Plan confirmation in chat.py + main.py

- Modify `api/chat.py`: pending_plan tracking, plan_proposed event, confirmation handling
- Modify `main.py`: add `pending_plans` to app.state
- Tests: plan proposed → confirmation → execution, modification round, cancellation

### Task 4: Final verification

---

*End of Step 7b Design + Plan.*
