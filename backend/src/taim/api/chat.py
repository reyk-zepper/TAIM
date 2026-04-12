"""WebSocket chat endpoint — stub for Step 1."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket stub — echoes connection confirmation. Full chat in Step 3."""
    await websocket.accept()
    try:
        while True:
            await websocket.receive_json()
            await websocket.send_json({
                "type": "system",
                "content": f"Connected to session {session_id}. Full chat in Step 3.",
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    except WebSocketDisconnect:
        pass
