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
        self._state = AgentState(
            agent_name=agent.name,
            run_id=run_id or str(uuid4()),
        )

    async def run(self) -> AgentRun:
        """Execute through states until DONE or FAILED."""
        await self._transition(AgentStateEnum.PLANNING, "initial")

        try:
            while self._state.current_state not in (
                AgentStateEnum.DONE, AgentStateEnum.FAILED,
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
            await self._transition(
                AgentStateEnum.DONE, "review_unparseable_accepted_as_is",
            )
            return

        self._state.review_feedback = review.feedback

        if review.quality_ok:
            await self._transition(AgentStateEnum.DONE, "review_passed")
        elif self._state.iteration >= self._agent.max_iterations:
            await self._transition(
                AgentStateEnum.DONE,
                f"max_iterations_reached_{self._agent.max_iterations}",
            )
        else:
            await self._transition(
                AgentStateEnum.ITERATING, "review_failed_iterating",
            )

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
        await self._transition(
            AgentStateEnum.EXECUTING, f"iteration_{self._state.iteration}",
        )

    async def _load_state_prompt(
        self,
        state: AgentStateEnum,
        variables: dict,
    ) -> str:
        state_name = state.value.lower()
        try:
            return self._prompts.load(
                f"agents/{self._agent.name}/{state_name}", variables,
            )
        except PromptNotFoundError:
            return self._prompts.load(
                f"agents/default/{state_name}", variables,
            )

    async def _call_llm(self, prompt: str, expected_format: str | None = None):
        tier_str = (
            self._agent.model_preference[0]
            if self._agent.model_preference
            else "tier2_standard"
        )
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
        self._state.tokens_used += (
            response.prompt_tokens + response.completion_tokens
        )
        # Router tracks USD; convert approximately. Full conversion at display layer.
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
