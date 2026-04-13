"""SessionStore — SQLite persistence for hot memory sessions."""

from __future__ import annotations

import json

import aiosqlite

from taim.models.memory import ChatMessage, HotMemorySession


class SessionStore:
    """SQLite persistence for hot memory sessions."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def persist(self, session: HotMemorySession) -> None:
        """Upsert session_state row with JSON-serialized messages."""
        to_persist = session.messages[-HotMemorySession.MAX_MESSAGES:]
        messages_json = json.dumps(
            [m.model_dump(mode="json") for m in to_persist]
        )
        await self._db.execute(
            """INSERT INTO session_state
               (session_id, user_id, messages, has_summary, updated_at)
               VALUES (?, ?, ?, 0, datetime('now'))
               ON CONFLICT(session_id) DO UPDATE SET
                   messages = excluded.messages,
                   updated_at = excluded.updated_at""",
            (session.session_id, session.user_id, messages_json),
        )
        await self._db.commit()

    async def load(self, session_id: str) -> HotMemorySession | None:
        """Load persisted session state, if any."""
        async with self._db.execute(
            "SELECT user_id, messages FROM session_state WHERE session_id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None

        user_id, messages_json = row
        messages = []
        if messages_json:
            for m in json.loads(messages_json):
                messages.append(ChatMessage(**m))

        return HotMemorySession(
            session_id=session_id,
            user_id=user_id,
            messages=messages,
        )

    async def update_summary(self, session_id: str, summary: str) -> None:
        await self._db.execute(
            """UPDATE session_state
               SET session_summary = ?, has_summary = 1, updated_at = datetime('now')
               WHERE session_id = ?""",
            (summary, session_id),
        )
        await self._db.commit()
