"""Tests for SQLite database initialization and schema management."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from taim.brain.database import SCHEMA_VERSION, init_database


@pytest.mark.asyncio
class TestDatabaseInit:
    async def test_creates_db_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "state" / "taim.db"
        db = await init_database(db_path)
        try:
            assert db_path.exists()
        finally:
            await db.close()

    async def test_creates_parent_directories(self, tmp_path: Path) -> None:
        db_path = tmp_path / "deep" / "nested" / "taim.db"
        db = await init_database(db_path)
        try:
            assert db_path.parent.is_dir()
        finally:
            await db.close()

    async def test_wal_mode_enabled(self, tmp_path: Path) -> None:
        db = await init_database(tmp_path / "taim.db")
        try:
            async with db.execute("PRAGMA journal_mode") as cursor:
                row = await cursor.fetchone()
                assert row[0] == "wal"
        finally:
            await db.close()

    async def test_foreign_keys_enabled(self, tmp_path: Path) -> None:
        db = await init_database(tmp_path / "taim.db")
        try:
            async with db.execute("PRAGMA foreign_keys") as cursor:
                row = await cursor.fetchone()
                assert row[0] == 1
        finally:
            await db.close()


@pytest.mark.asyncio
class TestSchema:
    async def test_all_tables_created(self, tmp_path: Path) -> None:
        db = await init_database(tmp_path / "taim.db")
        try:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ) as cursor:
                tables = [row[0] for row in await cursor.fetchall()]
            assert "schema_version" in tables
            assert "token_tracking" in tables
            assert "task_state" in tables
            assert "session_state" in tables
            assert "agent_runs" in tables
        finally:
            await db.close()

    async def test_schema_version_recorded(self, tmp_path: Path) -> None:
        db = await init_database(tmp_path / "taim.db")
        try:
            async with db.execute("SELECT MAX(version) FROM schema_version") as cursor:
                row = await cursor.fetchone()
                assert row[0] == SCHEMA_VERSION
        finally:
            await db.close()

    async def test_indexes_created(self, tmp_path: Path) -> None:
        db = await init_database(tmp_path / "taim.db")
        try:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ) as cursor:
                indexes = [row[0] for row in await cursor.fetchall()]
            assert "idx_token_tracking_task" in indexes
            assert "idx_token_tracking_session" in indexes
            assert "idx_agent_runs_task" in indexes
        finally:
            await db.close()


@pytest.mark.asyncio
class TestMigrationIdempotency:
    async def test_second_init_does_not_fail(self, tmp_path: Path) -> None:
        db_path = tmp_path / "taim.db"
        db1 = await init_database(db_path)
        await db1.close()
        db2 = await init_database(db_path)
        try:
            async with db2.execute("SELECT MAX(version) FROM schema_version") as cursor:
                row = await cursor.fetchone()
                assert row[0] == SCHEMA_VERSION
        finally:
            await db2.close()
