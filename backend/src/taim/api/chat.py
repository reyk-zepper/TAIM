"""WebSocket chat endpoint — wired to IntentInterpreter + Memory System."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from taim.brain.agent_state_machine import TransitionEvent
from taim.brain.hot_memory import HotMemory
from taim.brain.session_store import SessionStore
from taim.brain.summarizer import Summarizer
from taim.conversation import IntentInterpreter
from taim.conversation.onboarding import OnboardingState
from taim.models.chat import IntentCategory, IntentResult
from taim.models.memory import ChatMessage
from taim.models.orchestration import TaskPlan, TaskStatus
from taim.models.tool import ToolExecutionEvent

logger = structlog.get_logger()
router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """Receive user messages, run through interpreter, send back responses."""
    await websocket.accept()
    interpreter: IntentInterpreter = websocket.app.state.interpreter
    hot: HotMemory = websocket.app.state.hot_memory
    store: SessionStore = websocket.app.state.session_store
    summarizer: Summarizer | None = getattr(websocket.app.state, "summarizer", None)

    # Restore from SQLite if session exists, else create fresh
    existing = await store.load(session_id)
    if existing:
        hot.rebuild(existing)
    else:
        hot.get_or_create(session_id)

    # Onboarding check on first connect
    onboarding_flow = getattr(websocket.app.state, "onboarding_flow", None)
    onboarding_sessions = getattr(websocket.app.state, "onboarding_sessions", {})
    if onboarding_flow and await onboarding_flow.is_needed():
        state = OnboardingState()
        onboarding_sessions[session_id] = state
        welcome = onboarding_flow.get_welcome_message()
        await websocket.send_json(
            {
                "type": "onboarding",
                "content": welcome,
                "step": "welcome",
                "session_id": session_id,
            }
        )

    try:
        while True:
            data = await websocket.receive_json()
            user_message = (data.get("content") or "").strip()
            if not user_message:
                continue

            hot.append_message(session_id, "user", user_message)

            # Handle onboarding responses
            if session_id in onboarding_sessions:
                ob_state = onboarding_sessions[session_id]
                response = await onboarding_flow.handle_response(ob_state, user_message)
                hot.append_message(session_id, "assistant", response)
                await store.persist(hot.get_or_create(session_id))
                await websocket.send_json(
                    {
                        "type": "onboarding",
                        "content": response,
                        "step": ob_state.step.value,
                        "session_id": session_id,
                    }
                )
                if ob_state.is_complete:
                    del onboarding_sessions[session_id]
                continue

            # Check for pending plan confirmation BEFORE interpreter call
            pending_plans = getattr(websocket.app.state, "pending_plans", {})
            if session_id in pending_plans:
                await _handle_plan_confirmation(
                    websocket=websocket,
                    hot=hot,
                    store=store,
                    session_id=session_id,
                    user_message=user_message,
                    pending_plans=pending_plans,
                    interpreter=interpreter,
                )
                continue

            await websocket.send_json({"type": "thinking", "session_id": session_id})

            session = hot.get_or_create(session_id)
            recent = [{"role": m.role, "content": m.content} for m in session.messages[:-1][-5:]]

            try:
                result = await interpreter.interpret(
                    message=user_message,
                    session_id=session_id,
                    recent_context=recent,
                )
            except Exception:
                logger.exception("interpreter.error", session=session_id)
                await websocket.send_json(
                    {
                        "type": "error",
                        "content": "I had trouble understanding that. Could you rephrase?",
                        "session_id": session_id,
                    }
                )
                continue

            # Branch: run orchestrator for actionable new_task intents
            orchestrator = getattr(websocket.app.state, "orchestrator", None)
            memory_manager = getattr(websocket.app.state, "memory", None)
            composer = getattr(websocket.app.state, "team_composer", None)
            pending_plans = getattr(websocket.app.state, "pending_plans", {})

            if (
                orchestrator is not None
                and composer is not None
                and result.intent is not None
                and result.classification.category == IntentCategory.NEW_TASK
                and not result.needs_followup
            ):
                # Compose team — prefer SwatBuilder (LLM-assisted) over rule-based fallback
                swat_builder = getattr(websocket.app.state, "swat_builder", None)
                if swat_builder:
                    slots = await swat_builder.build_team(result.intent)
                else:
                    slots = composer.compose_team(result.intent)

                if not slots:
                    hot.append_message(
                        session_id,
                        "assistant",
                        "I couldn't find any suitable agents for this task.",
                    )
                    await store.persist(hot.get_or_create(session_id))
                    await websocket.send_json(
                        {
                            "type": "error",
                            "content": "No suitable agents available.",
                            "session_id": session_id,
                        }
                    )
                    continue

                task_id = str(uuid4())
                plan = TaskPlan(
                    task_id=task_id,
                    objective=result.intent.objective,
                    parameters=result.intent.parameters,
                    agents=slots,
                )

                if plan.is_single_agent:
                    # Single agent: execute directly (no confirmation needed)
                    await _run_orchestrated_task(
                        websocket=websocket,
                        orchestrator=orchestrator,
                        memory_manager=memory_manager,
                        hot=hot,
                        store=store,
                        session_id=session_id,
                        intent=result.intent,
                        classification=result.classification,
                    )
                    continue

                # Multi-agent: propose plan and wait for confirmation
                agent_names = ", ".join(s.agent_name for s in slots)
                await websocket.send_json(
                    {
                        "type": "plan_proposed",
                        "content": (
                            f"I've assembled a team for this: {agent_names}. "
                            "They'll work sequentially. Confirm to start, or suggest changes."
                        ),
                        "session_id": session_id,
                        "plan": plan.model_dump(),
                    }
                )
                pending_plans[session_id] = (plan, result.intent, 0)  # (plan, intent, round)
                hot.append_message(
                    session_id,
                    "assistant",
                    f"Team proposed: {agent_names}. Waiting for confirmation.",
                )
                await store.persist(hot.get_or_create(session_id))
                continue

            response_text = (
                result.direct_response
                or result.followup_question
                or _summarize_intent(result.intent)
            )
            hot.append_message(session_id, "assistant", response_text)

            await store.persist(hot.get_or_create(session_id))

            if summarizer is not None and hot.should_summarize(session_id):
                old_messages = hot.trim_after_summary(session_id, keep_last_n=10)
                asyncio.create_task(_summarize_async(summarizer, store, session_id, old_messages))

            await websocket.send_json(
                {
                    "type": "system" if result.direct_response else "intent",
                    "content": response_text,
                    "category": result.classification.category.value,
                    "confidence": result.classification.confidence,
                    "intent": result.intent.model_dump() if result.intent else None,
                    "session_id": session_id,
                }
            )
    except WebSocketDisconnect:
        pass


def _summarize_intent(intent: IntentResult | None) -> str:
    if intent is None:
        return "Got it."
    return f"I understood: {intent.objective}"


async def _summarize_async(
    summarizer: Summarizer,
    store: SessionStore,
    session_id: str,
    old_messages: list[ChatMessage],
) -> None:
    """Fire-and-forget summarization — failure logged but doesn't break chat."""
    try:
        summary = await summarizer.summarize_and_store(session_id, old_messages)
        await store.update_summary(session_id, summary)
    except Exception:
        logger.exception("summarizer.error", session=session_id)


async def _run_orchestrated_task(
    websocket: WebSocket,
    orchestrator,
    memory_manager,
    hot: HotMemory,
    store: SessionStore,
    session_id: str,
    intent,
    classification,
) -> None:
    """Execute a new_task intent via the Orchestrator and stream events."""
    await websocket.send_json(
        {
            "type": "agent_started",
            "content": f"Working on: {intent.objective}",
            "category": classification.category.value,
            "session_id": session_id,
        }
    )

    async def fwd_agent_event(event: TransitionEvent) -> None:
        await websocket.send_json(
            {
                "type": "agent_state",
                "agent_name": event.agent_name,
                "from_state": event.from_state.value if event.from_state else None,
                "to_state": event.to_state.value,
                "iteration": event.iteration,
                "reason": event.reason,
                "session_id": session_id,
            }
        )

    async def fwd_tool_event(event: ToolExecutionEvent) -> None:
        await websocket.send_json(
            {
                "type": "tool_execution",
                "content": event.summary,
                "agent_name": event.agent_name,
                "tool_name": event.tool_name,
                "tool_status": event.status,
                "duration_ms": event.duration_ms,
                "session_id": session_id,
            }
        )

    user_prefs = ""
    if memory_manager is not None:
        try:
            user_prefs = await memory_manager.get_preferences_text()
        except Exception:
            logger.exception("chat.preferences_load_failed", session=session_id)

    try:
        result = await orchestrator.execute(
            intent=intent,
            session_id=session_id,
            user_preferences=user_prefs,
            on_agent_event=fwd_agent_event,
            on_tool_event=fwd_tool_event,
        )
    except Exception:
        logger.exception("chat.orchestrator_error", session=session_id)
        await websocket.send_json(
            {
                "type": "error",
                "content": "Something went wrong running the agent.",
                "session_id": session_id,
            }
        )
        return

    final_text = result.result_content or result.error or "Done."
    hot.append_message(session_id, "assistant", final_text)
    await store.persist(hot.get_or_create(session_id))

    await websocket.send_json(
        {
            "type": "agent_completed" if result.status == TaskStatus.COMPLETED else "error",
            "content": final_text,
            "agent_name": result.agent_name,
            "tokens_used": result.tokens_used,
            "cost_eur": result.cost_eur,
            "duration_ms": result.duration_ms,
            "session_id": session_id,
        }
    )


async def _handle_plan_confirmation(
    websocket: WebSocket,
    hot: HotMemory,
    store: SessionStore,
    session_id: str,
    user_message: str,
    pending_plans: dict,
    interpreter: IntentInterpreter,
) -> None:
    """Handle user response to a pending plan_proposed event."""
    plan, intent, rounds = pending_plans[session_id]

    # Classify the user's response
    try:
        classification_result = await interpreter.interpret(
            message=user_message,
            session_id=session_id,
            recent_context=[],
        )
        category = classification_result.classification.category
    except Exception:
        category = IntentCategory.CONFIRMATION  # On error, treat as confirmation

    if category == IntentCategory.CONFIRMATION:
        # Execute the plan
        del pending_plans[session_id]
        orchestrator = websocket.app.state.orchestrator
        memory_manager = getattr(websocket.app.state, "memory", None)

        await websocket.send_json(
            {
                "type": "agent_started",
                "content": f"Starting team: {', '.join(s.agent_name for s in plan.agents)}",
                "session_id": session_id,
            }
        )

        user_prefs = ""
        if memory_manager:
            try:
                user_prefs = await memory_manager.get_preferences_text()
            except Exception:
                pass

        async def fwd_agent(event: TransitionEvent) -> None:
            await websocket.send_json(
                {
                    "type": "agent_state",
                    "agent_name": event.agent_name,
                    "to_state": event.to_state.value,
                    "iteration": event.iteration,
                    "reason": event.reason,
                    "session_id": session_id,
                }
            )

        async def fwd_tool(event: ToolExecutionEvent) -> None:
            await websocket.send_json(
                {
                    "type": "tool_execution",
                    "content": event.summary,
                    "agent_name": event.agent_name,
                    "tool_name": event.tool_name,
                    "tool_status": event.status,
                    "session_id": session_id,
                }
            )

        # Create task_state row first
        await orchestrator._task_manager.create(plan)

        try:
            result = await orchestrator.execute_team(
                plan=plan,
                intent=intent,
                session_id=session_id,
                user_preferences=user_prefs,
                on_agent_event=fwd_agent,
                on_tool_event=fwd_tool,
            )
        except Exception:
            logger.exception("chat.team_execution_error", session=session_id)
            await websocket.send_json(
                {
                    "type": "error",
                    "content": "Something went wrong running the team.",
                    "session_id": session_id,
                }
            )
            return

        final_text = result.result_content or result.error or "Done."
        hot.append_message(session_id, "assistant", final_text)
        await store.persist(hot.get_or_create(session_id))

        await websocket.send_json(
            {
                "type": "agent_completed" if result.status == TaskStatus.COMPLETED else "error",
                "content": final_text,
                "agent_name": result.agent_name,
                "cost_eur": result.cost_eur,
                "duration_ms": result.duration_ms,
                "session_id": session_id,
            }
        )

    elif category == IntentCategory.STOP_COMMAND:
        # Cancel plan
        del pending_plans[session_id]
        hot.append_message(session_id, "assistant", "Plan cancelled.")
        await store.persist(hot.get_or_create(session_id))
        await websocket.send_json(
            {
                "type": "system",
                "content": "Plan cancelled.",
                "session_id": session_id,
            }
        )

    elif rounds < 2:
        # Modification round — re-compose
        # Pass user's modification as additional context
        # For 7b: simplified — just re-compose with same intent
        # The user's feedback is noted but rule-based composer may produce same result
        pending_plans[session_id] = (plan, intent, rounds + 1)
        hot.append_message(
            session_id,
            "assistant",
            "I'll adjust the plan. For now, the same team applies. Confirm to proceed.",
        )
        await store.persist(hot.get_or_create(session_id))
        team_names = ", ".join(s.agent_name for s in plan.agents)
        await websocket.send_json(
            {
                "type": "plan_proposed",
                "content": (
                    f"Adjusted plan (round {rounds + 2}/3): {team_names}. Confirm to start."
                ),
                "session_id": session_id,
                "plan": plan.model_dump(),
            }
        )

    else:
        # Max rounds reached — execute anyway (US-4.3 AC4)
        del pending_plans[session_id]
        hot.append_message(
            session_id,
            "assistant",
            "Maximum plan revisions reached. Executing current plan.",
        )
        await store.persist(hot.get_or_create(session_id))

        orchestrator = websocket.app.state.orchestrator
        await orchestrator._task_manager.create(plan)
        try:
            result = await orchestrator.execute_team(
                plan=plan,
                intent=intent,
                session_id=session_id,
            )
        except Exception:
            await websocket.send_json(
                {
                    "type": "error",
                    "content": "Execution failed.",
                    "session_id": session_id,
                }
            )
            return

        final_text = result.result_content or result.error or "Done."
        hot.append_message(session_id, "assistant", final_text)
        await store.persist(hot.get_or_create(session_id))
        await websocket.send_json(
            {
                "type": "agent_completed" if result.status == TaskStatus.COMPLETED else "error",
                "content": final_text,
                "session_id": session_id,
            }
        )
