"""SQLite database initialization and schema management."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

SCHEMA_VERSION = 1

_SCHEMA_V1 = """\
CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS token_tracking (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id           TEXT UNIQUE NOT NULL,
    agent_run_id      TEXT,
    task_id           TEXT,
    session_id        TEXT,
    model             TEXT NOT NULL,
    provider          TEXT NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd          REAL NOT NULL DEFAULT 0.0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_state (
    task_id        TEXT PRIMARY KEY,
    team_id        TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    objective      TEXT,
    agent_states   TEXT,
    token_total    INTEGER DEFAULT 0,
    cost_total_eur REAL DEFAULT 0.0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at   TEXT
);

CREATE TABLE IF NOT EXISTS session_state (
    session_id      TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL DEFAULT 'default',
    messages        TEXT,
    session_summary TEXT,
    has_summary     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id             TEXT PRIMARY KEY,
    agent_name         TEXT NOT NULL,
    task_id            TEXT NOT NULL,
    team_id            TEXT NOT NULL,
    session_id         TEXT,
    state_history      TEXT,
    final_state        TEXT NOT NULL,
    prompt_tokens      INTEGER DEFAULT 0,
    completion_tokens  INTEGER DEFAULT 0,
    cost_eur           REAL DEFAULT 0.0,
    provider           TEXT,
    model_used         TEXT,
    failover_occurred  INTEGER NOT NULL DEFAULT 0,
    started_at         TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_token_tracking_task ON token_tracking(task_id);
CREATE INDEX IF NOT EXISTS idx_token_tracking_session ON token_tracking(session_id);
CREATE INDEX IF NOT EXISTS idx_token_tracking_agent_run ON token_tracking(agent_run_id);
CREATE INDEX IF NOT EXISTS idx_token_tracking_created ON token_tracking(created_at);
CREATE INDEX IF NOT EXISTS idx_task_state_team ON task_state(team_id);
CREATE INDEX IF NOT EXISTS idx_task_state_status ON task_state(status);
CREATE INDEX IF NOT EXISTS idx_session_state_user ON session_state(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_task ON agent_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_team ON agent_runs(team_id);
"""

_MIGRATIONS = {
    1: _SCHEMA_V1,
}


async def init_database(db_path: Path) -> aiosqlite.Connection:
    """Initialize SQLite database with schema. Idempotent."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))

    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")

    current = await _get_schema_version(db)
    if current < SCHEMA_VERSION:
        await _apply_migrations(db, current)

    return db


async def _get_schema_version(db: aiosqlite.Connection) -> int:
    """Returns 0 if no schema exists yet."""
    try:
        async with db.execute("SELECT MAX(version) FROM schema_version") as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else 0
    except aiosqlite.OperationalError:
        return 0


async def _apply_migrations(db: aiosqlite.Connection, from_version: int) -> None:
    """Apply all migrations from from_version to SCHEMA_VERSION."""
    for version in range(from_version + 1, SCHEMA_VERSION + 1):
        await db.executescript(_MIGRATIONS[version])
        await db.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (version,)
        )
        await db.commit()
