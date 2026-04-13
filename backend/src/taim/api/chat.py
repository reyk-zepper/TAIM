"""WebSocket chat endpoint — wired to IntentInterpreter."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from taim.conversation import IntentInterpreter
from taim.models.chat import IntentResult

logger = structlog.get_logger()
router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """Receive user messages, run through interpreter, send back responses."""
    await websocket.accept()
    interpreter: IntentInterpreter = websocket.app.state.interpreter

    history: list[dict] = []  # In-memory per-session, formalized in Step 4

    try:
        while True:
            data = await websocket.receive_json()
            user_message = (data.get("content") or "").strip()
            if not user_message:
                continue

            history.append({"role": "user", "content": user_message})
            await websocket.send_json({"type": "thinking", "session_id": session_id})

            try:
                result = await interpreter.interpret(
                    message=user_message,
                    session_id=session_id,
                    recent_context=history[:-1],
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
                result.direct_response or result.followup_question or _summarize(result.intent)
            )
            history.append({"role": "assistant", "content": response_text})

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


def _summarize(intent: IntentResult | None) -> str:
    if intent is None:
        return "Got it."
    return f"I understood: {intent.objective}"
