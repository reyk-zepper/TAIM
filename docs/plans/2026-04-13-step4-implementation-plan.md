# Step 4: Memory System — Implementation Plan

> **For agentic workers:** Follow superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the Three-Temperature Memory (Hot/Warm/Cold-ready) with INDEX.md retrieval, session persistence, and auto-summarization.

**Architecture:** MemoryManager (warm) + HotMemory (in-memory) + SessionStore (SQLite) + Summarizer (Tier 3 LLM). Design: `docs/plans/2026-04-13-step4-memory-design.md`.

**Tech Stack:** Python 3.11+, python-frontmatter, aiosqlite, LiteLLM via Router, asyncio.

---

## File Structure

### Files to Create
```
backend/src/taim/models/memory.py
backend/src/taim/brain/memory.py
backend/src/taim/brain/hot_memory.py
backend/src/taim/brain/session_store.py
backend/src/taim/brain/summarizer.py
taim-vault/system/prompts/session-summarizer.yaml
tests/backend/test_memory_models.py
tests/backend/test_memory_manager.py
tests/backend/test_hot_memory.py
tests/backend/test_session_store.py
tests/backend/test_summarizer.py
```

### Files to Modify
```
backend/src/taim/brain/vault.py      # Seed session-summarizer.yaml
backend/src/taim/main.py             # Wire memory into lifespan + interpreter
backend/src/taim/api/chat.py         # Replace local history with HotMemory + SessionStore
tests/backend/test_chat_websocket.py # Extended for memory integration
```

---

## Task 1: Memory Data Models

**Files:** `backend/src/taim/models/memory.py`, `tests/backend/test_memory_models.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/backend/test_memory_models.py
"""Tests for memory data models."""

from datetime import date, datetime

from taim.models.memory import (
    ChatMessage, HotMemorySession, MemoryEntry, MemoryIndex, MemoryIndexEntry,
)


class TestMemoryEntry:
    def test_minimal(self) -> None:
        today = date.today()
        e = MemoryEntry(
            title="Test", category="user-profile",
            created=today, updated=today, content="body",
        )
        assert e.tags == []
        assert e.confidence == 1.0
        assert e.source == "session"


class TestMemoryIndexEntry:
    def test_minimal(self) -> None:
        e = MemoryIndexEntry(
            filename="prefs.md",
            summary="User prefs",
            tags=["preferences"],
            updated=date.today(),
        )
        assert e.filename == "prefs.md"


class TestMemoryIndex:
    def test_empty(self) -> None:
        idx = MemoryIndex()
        assert idx.entries == []


class TestChatMessage:
    def test_has_timestamp(self) -> None:
        m = ChatMessage(role="user", content="hello")
        assert isinstance(m.timestamp, datetime)


class TestHotMemorySession:
    def test_defaults(self) -> None:
        s = HotMemorySession(session_id="s1")
        assert s.user_id == "default"
        assert s.messages == []
        assert s.task_context == {}

    def test_max_messages_constant(self) -> None:
        assert HotMemorySession.MAX_MESSAGES == 20
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement models/memory.py**

```python
"""Data models for the memory system."""

from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """A Markdown memory note with YAML frontmatter."""

    title: str
    category: str
    tags: list[str] = []
    created: date
    updated: date
    content: str
    confidence: float = 1.0
    source: str = "session"


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

    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HotMemorySession(BaseModel):
    """Per-session in-memory state."""

    MAX_MESSAGES: ClassVar[int] = 20

    session_id: str
    user_id: str = "default"
    messages: list[ChatMessage] = []
    task_context: dict = {}
    team_state: dict = {}
```

- [ ] **Step 4: Run → PASS** (6+ tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/models/memory.py tests/backend/test_memory_models.py
git commit -m "feat: add memory system data models"
```

---

## Task 2: MemoryManager

**Files:** `backend/src/taim/brain/memory.py`, `tests/backend/test_memory_manager.py`

- [ ] **Step 1: Write tests**

```python
# tests/backend/test_memory_manager.py
"""Tests for MemoryManager — warm memory filesystem operations."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from taim.brain.memory import MemoryManager
from taim.models.memory import MemoryEntry


@pytest.fixture
def manager(tmp_path: Path) -> MemoryManager:
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    return MemoryManager(users_dir)


def _make_entry(title: str = "T", tags: list[str] | None = None, content: str = "body") -> MemoryEntry:
    today = date.today()
    return MemoryEntry(
        title=title, category="preferences",
        tags=tags or ["preferences"],
        created=today, updated=today,
        content=content,
    )


@pytest.mark.asyncio
class TestWriteAndRead:
    async def test_write_creates_file(self, manager: MemoryManager) -> None:
        entry = _make_entry("User Preferences", ["preferences", "user-profile"])
        path = await manager.write_entry(entry, "preferences.md")
        assert path.exists()
        text = path.read_text()
        assert "title: User Preferences" in text
        assert "body" in text

    async def test_read_roundtrip(self, manager: MemoryManager) -> None:
        entry = _make_entry("Test", ["preferences"], "User prefers concise outputs")
        await manager.write_entry(entry, "test.md")
        loaded = await manager.read_entry("test.md")
        assert loaded is not None
        assert loaded.title == "Test"
        assert "preferences" in loaded.tags
        assert "concise outputs" in loaded.content

    async def test_read_missing_returns_none(self, manager: MemoryManager) -> None:
        result = await manager.read_entry("nonexistent.md")
        assert result is None


@pytest.mark.asyncio
class TestIndex:
    async def test_write_updates_index(self, manager: MemoryManager) -> None:
        await manager.write_entry(_make_entry("First", ["preferences"], "first body"), "a.md")
        await manager.write_entry(_make_entry("Second", ["research"], "second body"), "b.md")
        index = await manager.scan_index()
        assert len(index.entries) == 2
        filenames = {e.filename for e in index.entries}
        assert "a.md" in filenames
        assert "b.md" in filenames

    async def test_scan_empty_index(self, manager: MemoryManager) -> None:
        index = await manager.scan_index()
        assert index.entries == []


@pytest.mark.asyncio
class TestFindRelevant:
    async def test_matches_by_tag(self, manager: MemoryManager) -> None:
        await manager.write_entry(_make_entry("A", ["preferences"], "a"), "a.md")
        await manager.write_entry(_make_entry("B", ["research"], "b"), "b.md")
        results = await manager.find_relevant(["preferences"])
        assert len(results) == 1
        assert results[0].filename == "a.md"

    async def test_matches_by_summary_keyword(self, manager: MemoryManager) -> None:
        await manager.write_entry(_make_entry("X", ["misc"], "User prefers TypeScript"), "ts.md")
        results = await manager.find_relevant(["typescript"])
        assert any(r.filename == "ts.md" for r in results)

    async def test_no_match_returns_empty(self, manager: MemoryManager) -> None:
        await manager.write_entry(_make_entry("A", ["preferences"], "a"), "a.md")
        results = await manager.find_relevant(["completely_unrelated_xyz"])
        assert results == []


@pytest.mark.asyncio
class TestMemoryReaderProtocol:
    async def test_get_preferences_text_missing(self, manager: MemoryManager) -> None:
        assert await manager.get_preferences_text() == ""

    async def test_get_preferences_text_returns_content(self, manager: MemoryManager) -> None:
        await manager.write_entry(
            _make_entry("Prefs", ["preferences"], "The user prefers concise outputs."),
            "preferences.md",
        )
        text = await manager.get_preferences_text()
        assert "concise outputs" in text
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement brain/memory.py**

(Full implementation from design doc Section 4 — copy verbatim.)

- [ ] **Step 4: Run → PASS** (~10 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/brain/memory.py tests/backend/test_memory_manager.py
git commit -m "feat: add MemoryManager with warm memory + INDEX.md operations"
```

---

## Task 3: HotMemory

**Files:** `backend/src/taim/brain/hot_memory.py`, `tests/backend/test_hot_memory.py`

- [ ] **Step 1: Write tests**

```python
# tests/backend/test_hot_memory.py
"""Tests for HotMemory — in-memory per-session state."""

from taim.brain.hot_memory import HotMemory
from taim.models.memory import ChatMessage, HotMemorySession


class TestAppendAndGet:
    def test_append_creates_session(self) -> None:
        hot = HotMemory()
        hot.append_message("s1", "user", "hello")
        messages = hot.get_messages("s1")
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "hello"

    def test_get_messages_empty_session(self) -> None:
        hot = HotMemory()
        assert hot.get_messages("s1") == []

    def test_last_n(self) -> None:
        hot = HotMemory()
        for i in range(5):
            hot.append_message("s1", "user", f"msg{i}")
        last2 = hot.get_messages("s1", last_n=2)
        assert len(last2) == 2
        assert last2[-1].content == "msg4"


class TestSummarization:
    def test_should_summarize_when_over_limit(self) -> None:
        hot = HotMemory()
        for i in range(HotMemorySession.MAX_MESSAGES + 1):
            hot.append_message("s1", "user", f"msg{i}")
        assert hot.should_summarize("s1") is True

    def test_should_not_summarize_when_under(self) -> None:
        hot = HotMemory()
        for i in range(5):
            hot.append_message("s1", "user", f"msg{i}")
        assert hot.should_summarize("s1") is False

    def test_trim_after_summary_keeps_last_n(self) -> None:
        hot = HotMemory()
        for i in range(25):
            hot.append_message("s1", "user", f"msg{i}")
        removed = hot.trim_after_summary("s1", keep_last_n=10)
        assert len(removed) == 15
        remaining = hot.get_messages("s1")
        assert len(remaining) == 10
        assert remaining[0].content == "msg15"
        assert remaining[-1].content == "msg24"


class TestRebuild:
    def test_rebuild_restores_session(self) -> None:
        hot = HotMemory()
        session = HotMemorySession(
            session_id="s1",
            messages=[ChatMessage(role="user", content="prior")],
        )
        hot.rebuild(session)
        assert hot.get_messages("s1")[0].content == "prior"


class TestClear:
    def test_clear_removes_session(self) -> None:
        hot = HotMemory()
        hot.append_message("s1", "user", "hi")
        hot.clear("s1")
        assert hot.get_messages("s1") == []
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement hot_memory.py**

(From design doc Section 5.)

- [ ] **Step 4: Run → PASS** (~8 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/brain/hot_memory.py tests/backend/test_hot_memory.py
git commit -m "feat: add HotMemory for in-memory per-session state"
```

---

## Task 4: SessionStore

**Files:** `backend/src/taim/brain/session_store.py`, `tests/backend/test_session_store.py`

- [ ] **Step 1: Write tests**

```python
# tests/backend/test_session_store.py
"""Tests for SessionStore — SQLite session persistence."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.database import init_database
from taim.brain.session_store import SessionStore
from taim.models.memory import ChatMessage, HotMemorySession


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    db = await init_database(tmp_path / "taim.db")
    s = SessionStore(db)
    yield s
    await db.close()


@pytest.mark.asyncio
class TestPersistAndLoad:
    async def test_persist_and_load_roundtrip(self, store: SessionStore) -> None:
        session = HotMemorySession(
            session_id="s1",
            messages=[
                ChatMessage(role="user", content="hello"),
                ChatMessage(role="assistant", content="hi there"),
            ],
        )
        await store.persist(session)
        loaded = await store.load("s1")
        assert loaded is not None
        assert loaded.session_id == "s1"
        assert len(loaded.messages) == 2
        assert loaded.messages[0].content == "hello"

    async def test_load_missing_returns_none(self, store: SessionStore) -> None:
        assert await store.load("nonexistent") is None

    async def test_persist_upsert(self, store: SessionStore) -> None:
        session = HotMemorySession(session_id="s1", messages=[ChatMessage(role="user", content="a")])
        await store.persist(session)
        session.messages.append(ChatMessage(role="user", content="b"))
        await store.persist(session)
        loaded = await store.load("s1")
        assert len(loaded.messages) == 2


@pytest.mark.asyncio
class TestSummary:
    async def test_update_summary(self, store: SessionStore) -> None:
        session = HotMemorySession(session_id="s1")
        await store.persist(session)
        await store.update_summary("s1", "Brief summary.")
        # Verify by raw query
        async with store._db.execute(
            "SELECT session_summary, has_summary FROM session_state WHERE session_id = ?",
            ("s1",),
        ) as cur:
            row = await cur.fetchone()
        assert row[0] == "Brief summary."
        assert row[1] == 1


@pytest.mark.asyncio
class TestMaxMessages:
    async def test_persists_only_last_20(self, store: SessionStore) -> None:
        session = HotMemorySession(
            session_id="s1",
            messages=[ChatMessage(role="user", content=f"msg{i}") for i in range(25)],
        )
        await store.persist(session)
        loaded = await store.load("s1")
        assert len(loaded.messages) == 20
        assert loaded.messages[0].content == "msg5"  # Oldest kept
        assert loaded.messages[-1].content == "msg24"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement session_store.py**

(From design doc Section 6.)

- [ ] **Step 4: Run → PASS** (~5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/brain/session_store.py tests/backend/test_session_store.py
git commit -m "feat: add SessionStore for SQLite session persistence"
```

---

## Task 5: Summarizer + Prompt

**Files:**
- Create: `backend/src/taim/brain/summarizer.py`
- Create: `taim-vault/system/prompts/session-summarizer.yaml`
- Modify: `backend/src/taim/brain/vault.py` (seed summarizer prompt)
- Create: `tests/backend/test_summarizer.py`

- [ ] **Step 1: Create session-summarizer.yaml**

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

- [ ] **Step 2: Add summarizer prompt seeding to vault.py**

In `backend/src/taim/brain/vault.py`, add constant:

```python
_DEFAULT_SESSION_SUMMARIZER_PROMPT = """\
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
"""
```

In `_ensure_default_prompts()`, add to defaults dict:
```python
"session-summarizer.yaml": _DEFAULT_SESSION_SUMMARIZER_PROMPT,
```

- [ ] **Step 3: Write summarizer tests**

```python
# tests/backend/test_summarizer.py
"""Tests for Summarizer — session memory compression."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.memory import MemoryManager
from taim.brain.prompts import PromptLoader
from taim.brain.summarizer import Summarizer
from taim.brain.vault import VaultOps
from taim.models.memory import ChatMessage

from conftest import MockRouter, make_response


@pytest.fixture
def summarizer(tmp_vault: Path) -> Summarizer:
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    memory_mgr = MemoryManager(ops.vault_config.users_dir)
    router = MockRouter([make_response("The user researched SaaS competitors. 3 companies identified.")])
    return Summarizer(router=router, prompt_loader=loader, memory_manager=memory_mgr)


@pytest.mark.asyncio
class TestSummarizeAndStore:
    async def test_generates_summary(self, summarizer: Summarizer) -> None:
        messages = [
            ChatMessage(role="user", content="Research B2B SaaS competitors"),
            ChatMessage(role="assistant", content="Found 3 companies..."),
        ]
        summary = await summarizer.summarize_and_store("s1", messages)
        assert "SaaS competitors" in summary or "3 companies" in summary

    async def test_writes_warm_memory_entry(self, summarizer: Summarizer, tmp_vault: Path) -> None:
        messages = [ChatMessage(role="user", content="test")]
        await summarizer.summarize_and_store("abc-123", messages)
        # Verify file exists
        memory_dir = tmp_vault / "users" / "default" / "memory"
        files = list(memory_dir.glob("session-abc-123-summary.md"))
        assert len(files) == 1
```

- [ ] **Step 4: Run → FAIL**

- [ ] **Step 5: Implement summarizer.py**

(From design doc Section 7.)

- [ ] **Step 6: Run → PASS** (~2 tests)

- [ ] **Step 7: Verify prompt seeding works**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest ../tests/backend/test_vault.py -v
```

- [ ] **Step 8: Commit**

```bash
git add backend/src/taim/brain/summarizer.py backend/src/taim/brain/vault.py tests/backend/test_summarizer.py taim-vault/system/prompts/session-summarizer.yaml
git commit -m "feat: add Summarizer for hot→warm memory compression with Tier 3 LLM"
```

---

## Task 6: Integration — Lifespan + WebSocket

**Files:**
- Modify: `backend/src/taim/main.py`
- Modify: `backend/src/taim/api/chat.py`
- Create/Extend: `tests/backend/test_chat_websocket.py`

- [ ] **Step 1: Update main.py lifespan**

After `llm_router = LLMRouter(...)` and `app.state.router = llm_router`, REPLACE the existing interpreter section with:

```python
    # 8. Memory System
    from taim.brain.hot_memory import HotMemory
    from taim.brain.memory import MemoryManager
    from taim.brain.session_store import SessionStore
    from taim.brain.summarizer import Summarizer

    memory_manager = MemoryManager(system_config.vault.users_dir)
    hot_memory = HotMemory()
    session_store = SessionStore(db)
    summarizer = Summarizer(llm_router, prompt_loader, memory_manager)

    app.state.memory = memory_manager
    app.state.hot_memory = hot_memory
    app.state.session_store = session_store
    app.state.summarizer = summarizer

    # 9. Intent Interpreter — now with real memory
    from taim.conversation import IntentInterpreter
    interpreter = IntentInterpreter(
        router=llm_router,
        prompt_loader=prompt_loader,
        memory=memory_manager,
        orchestrator=None,  # Step 7 still
    )
    app.state.interpreter = interpreter
```

- [ ] **Step 2: Replace api/chat.py**

Full content from design doc Section 9. Uses `hot`, `store`, `summarizer` from app.state.

- [ ] **Step 3: Extend test_chat_websocket.py**

Add these tests to the existing `tests/backend/test_chat_websocket.py`:

```python
def test_websocket_persists_to_session_store(tmp_vault: Path) -> None:
    """After a message, session_state SQLite row should exist."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from taim.api.chat import router as chat_router
    from taim.brain.hot_memory import HotMemory
    from taim.brain.memory import MemoryManager
    from taim.brain.prompts import PromptLoader
    from taim.brain.session_store import SessionStore
    from taim.brain.summarizer import Summarizer
    from taim.brain.vault import VaultOps
    from taim.conversation import IntentInterpreter

    from conftest import MockRouter, make_classification_response

    import asyncio
    from taim.brain.database import init_database

    async def setup():
        ops = VaultOps(tmp_vault)
        ops.ensure_vault()
        loader = PromptLoader(ops.vault_config.prompts_dir)
        memory_mgr = MemoryManager(ops.vault_config.users_dir)
        db = await init_database(ops.vault_config.db_path)
        return ops, loader, memory_mgr, db

    ops, loader, memory_mgr, db = asyncio.get_event_loop().run_until_complete(setup())
    try:
        store = SessionStore(db)
        router = MockRouter([make_classification_response("status_query", 0.95)])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader, memory=memory_mgr)
        summarizer_mock = None  # Not triggered for <20 messages

        app = FastAPI()
        app.include_router(chat_router)
        app.state.interpreter = interpreter
        app.state.hot_memory = HotMemory()
        app.state.session_store = store
        app.state.summarizer = summarizer_mock

        client = TestClient(app)
        with client.websocket_connect("/ws/sess-persist") as ws:
            ws.send_json({"content": "status?"})
            ws.receive_json()  # thinking
            ws.receive_json()  # response

        # Verify persisted
        async def check():
            session = await store.load("sess-persist")
            assert session is not None
            assert len(session.messages) >= 1

        asyncio.get_event_loop().run_until_complete(check())
    finally:
        asyncio.get_event_loop().run_until_complete(db.close())
```

(This test is complex — alternatively make it async with a proper async test client fixture.)

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v
```

- [ ] **Step 5: Lint**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run ruff check src/ && uv run ruff format src/
```

- [ ] **Step 6: Manual smoke test**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run uvicorn taim.main:app --host localhost --port 8001 > /tmp/taim-step4.log 2>&1 &
sleep 3
curl -s http://localhost:8001/health
kill %1 2>/dev/null
cat /tmp/taim-step4.log | head -10
```

- [ ] **Step 7: Commit**

```bash
git add backend/src/taim/main.py backend/src/taim/api/chat.py tests/backend/test_chat_websocket.py
git commit -m "feat: wire memory system into lifespan, replace local history with HotMemory + SessionStore"
```

---

## Task 7: Final Verification

- [ ] **Step 1: Full suite + coverage**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest --cov=taim --cov-report=term-missing 2>&1 | tail -25
```
Expected: ≥80% coverage on memory modules.

- [ ] **Step 2: Lint clean**

- [ ] **Step 3: Manual verification via curl/wscat if installed**

```bash
# Connect to ws://localhost:8000/ws/test-session
# Send: {"content": "what's happening?"}
# Expect: thinking + system events with "no active team" (orchestrator still None)
# Verify session_state table has row after message
```

- [ ] **Step 4: Fix and commit if any issues**

---

## Summary

| Task | Module | Tests | Steps |
|------|--------|-------|-------|
| 1 | models/memory.py | test_memory_models.py | 5 |
| 2 | brain/memory.py | test_memory_manager.py | 5 |
| 3 | brain/hot_memory.py | test_hot_memory.py | 5 |
| 4 | brain/session_store.py | test_session_store.py | 5 |
| 5 | brain/summarizer.py + prompt | test_summarizer.py | 8 |
| 6 | main.py + api/chat.py | test_chat_websocket.py (extend) | 7 |
| 7 | Verification | — | 4 |
| **Total** | **5 new files** | **5 test files** | **39 steps** |

Parallelizable: Tasks 2+3+4 (memory manager, hot memory, session store) are independent after Task 1.
