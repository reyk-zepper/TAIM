"""Orchestrator — coordinates Intent → Agent selection → Execution."""

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
from taim.models.agent import AgentStateEnum
from taim.models.chat import IntentResult
from taim.models.orchestration import TaskExecutionResult, TaskPlan, TaskStatus
from taim.models.tool import ToolExecutionEvent
from taim.orchestrator.task_manager import TaskManager
from taim.orchestrator.team_composer import TeamComposer
from taim.orchestrator.tools import ToolExecutor

logger = structlog.get_logger()


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
        router,
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

        # 4. Build task description from intent
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
        except Exception as e:  # noqa: BLE001 — orchestrator must not crash on agent failure
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
        status = (
            TaskStatus.COMPLETED
            if run.final_state == AgentStateEnum.DONE
            else TaskStatus.FAILED
        )
        tokens = run.prompt_tokens + run.completion_tokens
        await self._task_manager.set_status(
            task_id,
            status,
            tokens=tokens,
            cost_eur=run.cost_eur,
        )

        return TaskExecutionResult(
            task_id=task_id,
            status=status,
            agent_name=agent.name,
            result_content=run.result_content,
            tokens_used=tokens,
            cost_eur=run.cost_eur,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    def _build_task_description(self, intent: IntentResult) -> str:
        parts = [intent.objective]
        if intent.parameters:
            param_lines = [f"- {k}: {v}" for k, v in intent.parameters.items()]
            parts.append("Parameters:\n" + "\n".join(param_lines))
        return "\n\n".join(parts)
