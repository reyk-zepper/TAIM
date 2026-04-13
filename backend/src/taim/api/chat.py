"""WebSocket chat endpoint — wired to IntentInterpreter + Memory System."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from taim.brain.hot_memory import HotMemory
from taim.brain.session_store import SessionStore
from taim.brain.summarizer import Summarizer
from taim.conversation import IntentInterpreter
from taim.models.chat import IntentResult
from taim.models.memory import ChatMessage

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

    try:
        while True:
            data = await websocket.receive_json()
            user_message = (data.get("content") or "").strip()
            if not user_message:
                continue

            hot.append_message(session_id, "user", user_message)
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
