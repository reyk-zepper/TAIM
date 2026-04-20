"""AgentStateMachine — autonomous agent execution through 7 states."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, ValidationError

from taim.brain.agent_run_store import AgentRunStore
from taim.brain.iteration_controller import IterationController
from taim.brain.prompts import PromptLoader
from taim.brain.skill_registry import SkillRegistry
from taim.errors import AllProvidersFailed, PromptNotFoundError
from taim.models.agent import (
    Agent,
    AgentRun,
    AgentState,
    AgentStateEnum,
    ReviewResult,
    StateTransition,
)
from taim.models.router import ModelTierEnum
from taim.models.tool import ToolCall, ToolExecutionEvent

if TYPE_CHECKING:
    from taim.orchestrator.tools import ToolExecutor

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

    _jinja: SandboxedEnvironment = SandboxedEnvironment(undefined=StrictUndefined)

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
        tool_executor: ToolExecutor | None = None,
        tool_context: dict[str, Any] | None = None,
        on_tool_event: Callable[[ToolExecutionEvent], Awaitable[None]] | None = None,
        run_id: str | None = None,
        skill_registry: SkillRegistry | None = None,
        iteration_controller: IterationController | None = None,
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
        self._tool_executor = tool_executor
        self._tool_context = tool_context
        self._on_tool_event = on_tool_event
        self._skill_registry = skill_registry
        self._iteration_controller = iteration_controller
        self._state = AgentState(
            agent_name=agent.name,
            run_id=run_id or str(uuid4()),
        )

    async def run(self) -> AgentRun:
        """Execute through states until DONE or FAILED."""
        await self._transition(AgentStateEnum.PLANNING, "initial")

        try:
            while self._state.current_state not in (
                AgentStateEnum.DONE,
                AgentStateEnum.FAILED,
            ):
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
            await self._transition(
                AgentStateEnum.FAILED,
                f"all_providers_failed: {e.detail}",
            )
        except PromptNotFoundError as e:
            await self._transition(
                AgentStateEnum.FAILED,
                f"missing_prompt: {e.detail}",
            )

        return self._build_run()

    async def _do_planning(self) -> None:
        prompt = await self._load_state_prompt(
            AgentStateEnum.PLANNING,
            {
                "task_description": self._task_description,
                "agent_description": self._agent.description,
                "user_preferences": self._user_preferences,
            },
        )
        response = await self._call_llm([{"role": "system", "content": prompt}])
        self._state.plan = response.content
        self._accumulate_cost(response)
        await self._transition(AgentStateEnum.EXECUTING, "planning_complete")

    def _render_primary_skill(self) -> str:
        """Return rendered primary skill prompt or empty string."""
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
        try:
            template = self._jinja.from_string(skill.prompt_template)
            return template.render(
                task_description=self._task_description,
                agent_description=self._agent.description,
            )
        except Exception:
            logger.exception("agent.skill_render_error", skill=primary_name)
            return ""

    async def _do_executing(self) -> None:
        base_prompt = await self._load_state_prompt(
            AgentStateEnum.EXECUTING,
            {
                "task_description": self._task_description,
                "agent_description": self._agent.description,
                "plan": self._state.plan,
                "iteration": str(self._state.iteration),
                "user_preferences": self._user_preferences,
            },
        )

        skill_prefix = self._render_primary_skill()
        full_prompt = (skill_prefix + "\n\n" + base_prompt) if skill_prefix else base_prompt

        tools = None
        if self._tool_executor and self._agent.tools:
            tools = self._tool_executor.get_tools_for_agent(self._agent.tools)
            if not tools:
                tools = None  # Agent's allowed tools not registered — don't pass empty list

        messages: list[dict] = [{"role": "system", "content": full_prompt}]

        max_tool_loops = 10
        for _ in range(max_tool_loops):
            response = await self._call_llm(messages, tools=tools)
            self._accumulate_cost(response)

            if not response.tool_calls:
                self._state.current_result = response.content
                break

            # Append assistant's tool_calls message
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in response.tool_calls
                    ],
                }
            )

            # Execute each tool call and append results
            for tc_raw in response.tool_calls:
                args_raw = tc_raw["arguments"]
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except json.JSONDecodeError:
                        args = {}
                else:
                    args = args_raw
                call = ToolCall(id=tc_raw["id"], name=tc_raw["name"], arguments=args)

                await self._emit_tool_event(
                    call.name,
                    "running",
                    summary=self._summarize_call(call),
                )
                result = await self._tool_executor.execute(call, self._tool_context or {})
                await self._emit_tool_event(
                    call.name,
                    "completed" if result.success else "failed",
                    duration_ms=result.duration_ms,
                    error=result.error,
                    summary=self._summarize_result(result),
                )

                # Track in state history (lightweight audit)
                self._state.state_history.append(
                    StateTransition(
                        from_state=AgentStateEnum.EXECUTING,
                        to_state=AgentStateEnum.EXECUTING,
                        timestamp=datetime.now(UTC),
                        reason=f"tool:{call.name}:{'ok' if result.success else 'err'}",
                    )
                )

                # Append tool result for LLM
                tool_message_content = result.output if result.success else f"Error: {result.error}"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": tool_message_content,
                    }
                )
        else:
            # Loop exhausted without break — accept whatever current_result holds
            logger.warning("agent.tool_loop_exhausted", run_id=self._state.run_id)
            if not self._state.current_result:
                self._state.current_result = "(tool loop exhausted without final response)"

        await self._transition(AgentStateEnum.REVIEWING, "execution_complete")

    def _summarize_call(self, call: ToolCall) -> str:
        if call.name == "file_read":
            return f"Reading file {call.arguments.get('path', '?')}"
        if call.name == "file_write":
            return f"Writing to {call.arguments.get('path', '?')}"
        if call.name == "vault_memory_read":
            return f"Reading memory: {call.arguments.get('filename', '?')}"
        if call.name == "vault_memory_write":
            return f"Saving memory: {call.arguments.get('title', '?')}"
        return f"Running {call.name}"

    def _summarize_result(self, result) -> str:
        if not result.success:
            return f"Failed: {result.error[:80]}"
        snippet = (result.output or "")[:80].replace("\n", " ")
        return snippet

    async def _emit_tool_event(self, tool_name: str, status: str, **kwargs) -> None:
        if self._on_tool_event is None:
            return
        try:
            await self._on_tool_event(
                ToolExecutionEvent(
                    agent_name=self._agent.name,
                    run_id=self._state.run_id,
                    tool_name=tool_name,
                    status=status,
                    duration_ms=kwargs.get("duration_ms", 0.0),
                    error=kwargs.get("error", ""),
                    summary=kwargs.get("summary", ""),
                )
            )
        except Exception:
            logger.exception("tool_event.emit_error", run_id=self._state.run_id)

    async def _do_reviewing(self) -> None:
        review_context = ""
        if self._iteration_controller:
            review_context = self._iteration_controller.build_review_context(self._agent)

        prompt = await self._load_state_prompt(
            AgentStateEnum.REVIEWING,
            {
                "task_description": self._task_description,
                "current_result": self._state.current_result,
                "review_context": review_context,
            },
        )
        response = await self._call_llm(
            [{"role": "system", "content": prompt}], expected_format="json"
        )
        self._accumulate_cost(response)

        try:
            review = ReviewResult(**json.loads(response.content))
        except (json.JSONDecodeError, ValidationError):
            # Fail-safe: accept current result (don't loop forever)
            await self._transition(
                AgentStateEnum.DONE,
                "review_unparseable_accepted_as_is",
            )
            return

        self._state.review_feedback = review.feedback

        if self._iteration_controller:
            should_iter, reason = self._iteration_controller.should_iterate(
                review,
                self._state.iteration,
                self._agent.max_iterations,
                self._agent,
            )
            if not should_iter:
                await self._transition(AgentStateEnum.DONE, reason)
            else:
                self._state.review_feedback = review.feedback
                await self._transition(AgentStateEnum.ITERATING, reason)
        else:
            # Fallback: original simple logic
            if review.quality_ok:
                await self._transition(AgentStateEnum.DONE, "review_passed")
            elif self._state.iteration >= self._agent.max_iterations:
                await self._transition(
                    AgentStateEnum.DONE,
                    f"max_iterations_reached_{self._agent.max_iterations}",
                )
            else:
                await self._transition(
                    AgentStateEnum.ITERATING,
                    "review_failed_iterating",
                )

    async def _do_iterating(self) -> None:
        self._state.iteration += 1
        prompt = await self._load_state_prompt(
            AgentStateEnum.ITERATING,
            {
                "task_description": self._task_description,
                "current_result": self._state.current_result,
                "review_feedback": self._state.review_feedback,
            },
        )
        response = await self._call_llm([{"role": "system", "content": prompt}])
        self._state.current_result = response.content
        self._accumulate_cost(response)
        await self._transition(
            AgentStateEnum.EXECUTING,
            f"iteration_{self._state.iteration}",
        )

    async def _load_state_prompt(
        self,
        state: AgentStateEnum,
        variables: dict,
    ) -> str:
        state_name = state.value.lower()
        try:
            return self._prompts.load(
                f"agents/{self._agent.name}/{state_name}",
                variables,
            )
        except PromptNotFoundError:
            return self._prompts.load(
                f"agents/default/{state_name}",
                variables,
            )

    async def _call_llm(
        self,
        messages: list[dict] | str,
        expected_format: str | None = None,
        tools: list[dict] | None = None,
    ):
        # If a single prompt string is passed, wrap it for backward compatibility
        if isinstance(messages, str):
            messages = [{"role": "system", "content": messages}]

        tier_str = (
            self._agent.model_preference[0] if self._agent.model_preference else "tier2_standard"
        )
        tier = ModelTierEnum(tier_str)
        return await self._router.complete(
            messages=messages,
            tier=tier,
            expected_format=expected_format,
            tools=tools,
            task_id=self._task_id,
            session_id=self._session_id,
            agent_run_id=self._state.run_id,
        )

    def _accumulate_cost(self, response) -> None:
        self._state.tokens_used += response.prompt_tokens + response.completion_tokens
        # Router tracks USD; convert approximately. Full conversion at display layer.
        self._state.cost_eur += response.cost_usd * 0.92

    async def _transition(self, to_state: AgentStateEnum, reason: str) -> None:
        prev = self._state.current_state if self._state.state_history else None
        ts = datetime.now(UTC)
        self._state.state_history.append(
            StateTransition(
                from_state=prev,
                to_state=to_state,
                timestamp=ts,
                reason=reason,
            )
        )
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
                await self._on_transition(
                    TransitionEvent(
                        run_id=self._state.run_id,
                        agent_name=self._agent.name,
                        from_state=prev,
                        to_state=to_state,
                        iteration=self._state.iteration,
                        reason=reason,
                        timestamp=ts,
                    )
                )
            except Exception:
                logger.exception(
                    "transition_callback.error",
                    run_id=self._state.run_id,
                )

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
