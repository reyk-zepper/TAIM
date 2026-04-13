# Step 4: Memory System — Implementation Design

> Version: 1.0
> Date: 2026-04-13
> Status: Reviewed — critical review applied
> Scope: US-7.2 (Warm Memory), US-7.3 (Hot Memory), US-7.4 (INDEX.md), US-1.5 (Session Continuity)

---

## 1. Overview

Step 4 builds the **Three-Temperature Memory Architecture** (AD-5):

```
Hot Memory  (RAM, per-session)   — last 20 messages + task context + team state
    ↓ (when > 20 messages)
Summarization (Tier 3 LLM call, fire-and-forget)
    ↓
Warm Memory (Markdown files)     — user preferences, session summaries, patterns
    ↓
INDEX.md    (lightweight catalog) — tag/keyword matching for retrieval
```

**Session continuity:** Hot memory is persisted to SQLite `session_state` after every message. Server restart → reconnect → load from SQLite → rebuild hot memory.

**Deliverables:**
1. `models/memory.py` — MemoryEntry, MemoryIndex, MemoryIndexEntry, HotMemorySession
2. `brain/memory.py` — MemoryManager (warm memory + INDEX.md operations)
3. `brain/hot_memory.py` — HotMemory (in-memory session state)
4. `brain/session_store.py` — SessionStore (SQLite persistence)
5. `brain/summarizer.py` — Session summarization via Tier 3 LLM
6. `taim-vault/system/prompts/session-summarizer.yaml`
7. Lifespan integration: MemoryManager → IntentInterpreter (replaces `memory=None`)
8. WebSocket update: `api/chat.py` uses HotMemory + SessionStore

**Architectural Decision:** MemoryManager is a separate class, not methods on VaultOps. Single responsibility.

---

## 2. Module Architecture

### 2.1 File Layout

```
backend/src/taim/
├── models/
│   └── memory.py                # Memory data models (5 classes)
├── brain/
│   ├── memory.py                # MemoryManager (facade, implements MemoryReader)
│   ├── hot_memory.py            # HotMemory (in-memory per-session)
│   ├── session_store.py         # SessionStore (SQLite session_state I/O)
│   └── summarizer.py            # Summarizer (Tier 3 LLM summarization)
├── api/
│   └── chat.py                  # Updated: hot memory + session persistence

taim-vault/system/prompts/
└── session-summarizer.yaml      # Tier 3 summarization prompt
```

### 2.2 Dependency Graph

```
models/memory.py              (no TAIM deps)
    ↓
brain/memory.py               (depends on: models/memory, VaultOps paths, python-frontmatter)
brain/hot_memory.py           (depends on: models/memory)
brain/session_store.py        (depends on: models/memory, aiosqlite)
brain/summarizer.py           (depends on: memory, LLMRouter, PromptLoader)
    ↓
api/chat.py                   (composes hot memory + session store + summarizer + interpreter)
main.py                       (lifespan creates and wires all)
```

No circular dependencies.

---

## 3. Data Models (`models/memory.py`)

```python
from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """A Markdown memory note with YAML frontmatter."""
    title: str
    category: str                     # e.g., "user-profile", "preferences", "session-summary"
    tags: list[str] = []
    created: date
    updated: date
    content: str                      # Markdown body (without frontmatter)
    confidence: float = 1.0
    source: str = "session"           # "session", "onboarding", "learned"


class MemoryIndexEntry(BaseModel):
    """One line in INDEX.md."""
    filename: str
    summary: str
    tags: list[str]
    updated: date


class MemoryIndex(BaseModel):
    """Parsed INDEX.md."""
    entries: list[MemoryIndexEntry] = []


class ChatMessage(BaseModel):
    """Message in hot memory / session history."""
    role: str                         # "user", "assistant", "system"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HotMemorySession(BaseModel):
    """Per-session in-memory state."""
    session_id: str
    user_id: str = "default"
    messages: list[ChatMessage] = []
    task_context: dict = {}
    team_state: dict = {}             # Populated in Step 7

    MAX_MESSAGES = 20
```

---

## 4. MemoryManager (`brain/memory.py`)

**Responsibility:** Warm memory filesystem operations. Writing and reading Markdown notes, maintaining INDEX.md, tag/keyword matching.

```python
import asyncio
import re
from pathlib import Path
from datetime import date

import frontmatter  # python-frontmatter

from taim.models.memory import MemoryEntry, MemoryIndex, MemoryIndexEntry


class MemoryManager:
    """Filesystem operations for warm memory. Implements MemoryReader protocol."""

    # One lock per user to prevent concurrent INDEX.md corruption
    _locks: dict[str, asyncio.Lock] = {}

    def __init__(self, users_dir: Path) -> None:
        self._users_dir = users_dir

    # --- Protocol: MemoryReader ---
    async def get_preferences_text(self, user: str = "default") -> str:
        """Return the content of preferences.md if it exists, else empty string."""
        path = self._user_memory_dir(user) / "preferences.md"
        if not path.exists():
            return ""
        post = frontmatter.load(str(path))
        return post.content.strip()

    # --- Write ---
    async def write_entry(
        self,
        entry: MemoryEntry,
        filename: str,
        user: str = "default",
    ) -> Path:
        """Write a MemoryEntry to Markdown+frontmatter and update INDEX.md."""
        async with self._lock(user):
            mem_dir = self._user_memory_dir(user)
            mem_dir.mkdir(parents=True, exist_ok=True)

            path = mem_dir / filename
            post = frontmatter.Post(
                entry.content,
                title=entry.title,
                category=entry.category,
                tags=entry.tags,
                created=entry.created.isoformat(),
                updated=entry.updated.isoformat(),
                confidence=entry.confidence,
                source=entry.source,
            )
            path.write_text(frontmatter.dumps(post), encoding="utf-8")

            await self._update_index(user)
            return path

    # --- Read ---
    async def read_entry(self, filename: str, user: str = "default") -> MemoryEntry | None:
        """Read a Markdown memory file into a MemoryEntry."""
        path = self._user_memory_dir(user) / filename
        if not path.exists():
            return None
        post = frontmatter.load(str(path))
        return MemoryEntry(
            title=post.get("title", filename),
            category=post.get("category", "unknown"),
            tags=post.get("tags", []),
            created=date.fromisoformat(str(post.get("created", date.today().isoformat()))),
            updated=date.fromisoformat(str(post.get("updated", date.today().isoformat()))),
            content=post.content,
            confidence=float(post.get("confidence", 1.0)),
            source=post.get("source", "session"),
        )

    # --- INDEX.md ---
    async def scan_index(self, user: str = "default") -> MemoryIndex:
        """Parse the user's INDEX.md into a MemoryIndex."""
        index_path = self._user_dir(user) / "INDEX.md"
        if not index_path.exists():
            return MemoryIndex()

        entries: list[MemoryIndexEntry] = []
        # Format: - [name](filename.md) — summary (tags: t1, t2) — YYYY-MM-DD
        pattern = re.compile(
            r"^- \[(?P<name>[^\]]+)\]\((?P<filename>[^)]+)\) — (?P<summary>.+?) \(tags: (?P<tags>[^)]*)\) — (?P<date>\d{4}-\d{2}-\d{2})$"
        )
        for line in index_path.read_text(encoding="utf-8").splitlines():
            m = pattern.match(line.strip())
            if not m:
                continue
            tags = [t.strip() for t in m.group("tags").split(",") if t.strip()]
            entries.append(MemoryIndexEntry(
                filename=m.group("filename"),
                summary=m.group("summary"),
                tags=tags,
                updated=date.fromisoformat(m.group("date")),
            ))
        return MemoryIndex(entries=entries)

    async def find_relevant(
        self,
        keywords: list[str],
        user: str = "default",
        max_entries: int = 10,
    ) -> list[MemoryIndexEntry]:
        """Tag/keyword match against INDEX.md. Pure Python, no LLM."""
        index = await self.scan_index(user)
        kw_lower = {k.lower() for k in keywords}
        scored: list[tuple[int, MemoryIndexEntry]] = []
        for entry in index.entries:
            score = sum(1 for t in entry.tags if t.lower() in kw_lower)
            score += sum(1 for k in kw_lower if k in entry.summary.lower())
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:max_entries]]

    # --- Internals ---
    async def _update_index(self, user: str) -> None:
        """Regenerate INDEX.md from all Markdown files in the user's memory dir."""
        mem_dir = self._user_memory_dir(user)
        if not mem_dir.exists():
            return
        lines = ["# Memory Index", "", "## Entries", ""]
        for md_file in sorted(mem_dir.glob("*.md")):
            try:
                post = frontmatter.load(str(md_file))
            except Exception:
                continue
            title = post.get("title", md_file.stem)
            summary = self._first_sentence(post.content)
            tags = ", ".join(post.get("tags", []))
            updated = post.get("updated", date.today().isoformat())
            lines.append(
                f"- [{md_file.stem}]({md_file.name}) — {summary} (tags: {tags}) — {updated}"
            )
        index_path = self._user_dir(user) / "INDEX.md"
        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _user_dir(self, user: str) -> Path:
        return self._users_dir / user

    def _user_memory_dir(self, user: str) -> Path:
        return self._user_dir(user) / "memory"

    def _lock(self, user: str) -> asyncio.Lock:
        if user not in self._locks:
            self._locks[user] = asyncio.Lock()
        return self._locks[user]

    @staticmethod
    def _first_sentence(content: str) -> str:
        """Extract first sentence (up to ~120 chars) for INDEX summary."""
        stripped = content.strip().split("\n", 1)[0].strip()
        if len(stripped) > 120:
            stripped = stripped[:117] + "..."
        return stripped or "(no summary)"
```

### Protocol Compatibility

Step 3's `MemoryReader` protocol has `get_preferences_text()`. MemoryManager implements this (user defaults to "default"). The interpreter is constructed with `memory=memory_manager`, which satisfies the protocol.

---

## 5. HotMemory (`brain/hot_memory.py`)

**Responsibility:** In-memory dict keyed by session_id. Last 20 messages per session.

```python
class HotMemory:
    """In-memory per-session state. Survives within one server process."""

    def __init__(self) -> None:
        self._sessions: dict[str, HotMemorySession] = {}

    def get_or_create(self, session_id: str, user_id: str = "default") -> HotMemorySession:
        if session_id not in self._sessions:
            self._sessions[session_id] = HotMemorySession(session_id=session_id, user_id=user_id)
        return self._sessions[session_id]

    def append_message(self, session_id: str, role: str, content: str) -> None:
        session = self.get_or_create(session_id)
        session.messages.append(ChatMessage(role=role, content=content))
        # Don't trim here — trim happens after summarization

    def get_messages(self, session_id: str, last_n: int | None = None) -> list[ChatMessage]:
        session = self._sessions.get(session_id)
        if not session:
            return []
        msgs = session.messages
        if last_n:
            return msgs[-last_n:]
        return msgs

    def should_summarize(self, session_id: str) -> bool:
        """Return True if session has more than MAX_MESSAGES and needs summarization."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        return len(session.messages) > HotMemorySession.MAX_MESSAGES

    def trim_after_summary(self, session_id: str, keep_last_n: int = 10) -> list[ChatMessage]:
        """Remove oldest messages except the last N. Returns the removed messages."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        removed = session.messages[:-keep_last_n]
        session.messages = session.messages[-keep_last_n:]
        return removed

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def rebuild(self, session: HotMemorySession) -> None:
        """Restore a session from persistence."""
        self._sessions[session.session_id] = session
```

---

## 6. SessionStore (`brain/session_store.py`)

**Responsibility:** Read/write session state to SQLite. Survives server restart.

```python
import json
import aiosqlite

from taim.models.memory import ChatMessage, HotMemorySession


class SessionStore:
    """SQLite persistence for hot memory sessions."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def persist(self, session: HotMemorySession) -> None:
        """Upsert session_state row with JSON-serialized messages."""
        messages_json = json.dumps([m.model_dump(mode="json") for m in session.messages[-HotMemorySession.MAX_MESSAGES:]])
        await self._db.execute(
            """INSERT INTO session_state (session_id, user_id, messages, has_summary, updated_at)
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
            "SELECT user_id, messages, session_summary, has_summary FROM session_state WHERE session_id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None

        user_id, messages_json, session_summary, has_summary = row
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
            "UPDATE session_state SET session_summary = ?, has_summary = 1, updated_at = datetime('now') WHERE session_id = ?",
            (summary, session_id),
        )
        await self._db.commit()
```

---

## 7. Summarizer (`brain/summarizer.py`)

**Responsibility:** When hot memory exceeds 20 messages, summarize the oldest via Tier 3 and store as warm memory.

```python
import structlog
from datetime import date

from taim.brain.memory import MemoryManager
from taim.brain.prompts import PromptLoader
from taim.models.memory import ChatMessage, MemoryEntry
from taim.models.router import ModelTierEnum

logger = structlog.get_logger()


class Summarizer:
    """Summarizes aging hot memory into warm memory entries."""

    def __init__(
        self,
        router,
        prompt_loader: PromptLoader,
        memory_manager: MemoryManager,
    ) -> None:
        self._router = router
        self._prompts = prompt_loader
        self._memory = memory_manager

    async def summarize_and_store(
        self,
        session_id: str,
        messages: list[ChatMessage],
        user: str = "default",
    ) -> str:
        """Generate a summary of messages, store as warm memory, return summary text."""
        transcript = "\n".join(f"{m.role}: {m.content}" for m in messages)
        prompt = self._prompts.load(
            "session-summarizer",
            {"transcript": transcript},
        )

        response = await self._router.complete(
            messages=[{"role": "system", "content": prompt}],
            tier=ModelTierEnum.TIER3_ECONOMY,
            session_id=session_id,
        )
        summary = response.content.strip()

        # Store as warm memory entry
        today = date.today()
        entry = MemoryEntry(
            title=f"Session Summary {today.isoformat()}",
            category="session-summary",
            tags=["session", "summary", session_id],
            created=today,
            updated=today,
            content=summary,
            source="session",
        )
        filename = f"session-{session_id}-summary.md"
        await self._memory.write_entry(entry, filename, user=user)

        logger.info(
            "memory.summarized",
            session_id=session_id,
            message_count=len(messages),
            summary_len=len(summary),
        )
        return summary
```

---

## 8. Prompt (`taim-vault/system/prompts/session-summarizer.yaml`)

```yaml
name: session-summarizer
version: 1
description: "Summarize an older chat transcript into a compact warm-memory entry"
model_tier: tier3_economy
variables:
  - transcript
template: |
  You are tAIm's session summarizer. Compress the following chat transcript into a concise summary (3-5 sentences max).

  Focus on:
  - What the user was trying to achieve
  - Key decisions made
  - Outcomes or partial results
  - Anything the user will need to remember later

  Do NOT include trivial exchanges (greetings, confirmations).

  Transcript:
  {{ transcript }}

  Respond with plain text (no markdown, no JSON, no headers).
```

---

## 9. WebSocket Integration (`api/chat.py`)

Replace the local `history: list[dict]` with HotMemory + SessionStore.

```python
@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    interpreter: IntentInterpreter = websocket.app.state.interpreter
    hot: HotMemory = websocket.app.state.hot_memory
    store: SessionStore = websocket.app.state.session_store
    summarizer: Summarizer = websocket.app.state.summarizer

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

            # Context from hot memory
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
                await websocket.send_json({
                    "type": "error",
                    "content": "I had trouble understanding that. Could you rephrase?",
                    "session_id": session_id,
                })
                continue

            response_text = result.direct_response or result.followup_question or _summarize(result.intent)
            hot.append_message(session_id, "assistant", response_text)

            # Persist after each exchange
            await store.persist(hot.get_or_create(session_id))

            # Fire-and-forget summarization when hot exceeds limit
            if hot.should_summarize(session_id):
                old_messages = hot.trim_after_summary(session_id, keep_last_n=10)
                asyncio.create_task(
                    _summarize_async(summarizer, store, session_id, old_messages)
                )

            await websocket.send_json({
                "type": "system" if result.direct_response else "intent",
                "content": response_text,
                "category": result.classification.category.value,
                "confidence": result.classification.confidence,
                "intent": result.intent.model_dump() if result.intent else None,
                "session_id": session_id,
            })
    except WebSocketDisconnect:
        pass


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
```

---

## 10. Lifespan Integration

In `main.py`, after the IntentInterpreter section:

```python
    # 8. Memory System
    from taim.brain.memory import MemoryManager
    from taim.brain.hot_memory import HotMemory
    from taim.brain.session_store import SessionStore
    from taim.brain.summarizer import Summarizer

    memory_manager = MemoryManager(system_config.vault.users_dir)
    hot_memory = HotMemory()
    session_store = SessionStore(db)
    summarizer = Summarizer(llm_router, prompt_loader, memory_manager)

    app.state.hot_memory = hot_memory
    app.state.session_store = session_store
    app.state.summarizer = summarizer
    app.state.memory = memory_manager

    # 9. Intent Interpreter — now with real memory
    interpreter = IntentInterpreter(
        router=llm_router,
        prompt_loader=prompt_loader,
        memory=memory_manager,      # was None
        orchestrator=None,           # Step 7 still
    )
    app.state.interpreter = interpreter
```

Note: IntentInterpreter construction moves AFTER memory manager creation.

Update `brain/vault.py` to seed `session-summarizer.yaml` via `_ensure_default_prompts`.

---

## 11. Critical Review Findings (Applied)

| # | Finding | Resolution |
|---|---------|------------|
| 1 | MemoryManager as separate class, not extending VaultOps | Approved by user — MemoryManager owns memory concerns |
| 2 | Session persistence per-message (not per-disconnect) | `store.persist()` on every message; survives crash |
| 3 | Summarization blocks user | Fire-and-forget via `asyncio.create_task`; failures logged, don't break chat |
| 4 | Concurrent INDEX.md writes corrupt file | `asyncio.Lock` per user namespace |
| 5 | MemoryEntry uses python-frontmatter | Already in dependencies (Step 1) |
| 6 | "default" user hardcoded | Explicit parameter everywhere, default="default". Proper user management is Phase 2 |
| 7 | find_relevant uses simple scoring | Pure Python tag/keyword matching, no LLM. Meets NFR-11 (<200ms for 500 entries) |
| 8 | HotMemory.MAX_MESSAGES = 20, summarize keeps last 10 | Matches AD-11 (sliding window) |
| 9 | session-summarizer.yaml seeded via VaultOps | Consistent with Step 3 pattern |

---

## 12. Test Strategy

| Test File | Module | Notable Tests |
|-----------|--------|---------------|
| `test_memory_models.py` | models/memory.py | Frontmatter roundtrip, INDEX parsing |
| `test_memory_manager.py` | brain/memory.py | write_entry + INDEX update, read, scan, find_relevant, get_preferences_text (MemoryReader) |
| `test_hot_memory.py` | brain/hot_memory.py | append, trim, should_summarize, rebuild |
| `test_session_store.py` | brain/session_store.py | Roundtrip, upsert, summary update |
| `test_summarizer.py` | brain/summarizer.py | Summary flow with MockRouter, warm memory write |
| `test_chat_websocket_memory.py` | api/chat.py | Hot memory persists, rebuild on reconnect, summarization triggered |

Coverage target: >80% (NFR-16).

---

*End of Step 4 Memory System Design.*
