"""Tests for built-in tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.memory import MemoryManager
from taim.orchestrator.builtin_tools.file_io import file_read, file_write
from taim.orchestrator.builtin_tools.memory_tools import (
    vault_memory_read,
    vault_memory_write,
)
from taim.orchestrator.tool_sandbox import ToolSandboxError


@pytest.mark.asyncio
class TestFileIO:
    async def test_file_write_then_read(self, tmp_path: Path) -> None:
        ctx = {"allowed_roots": [tmp_path]}
        target = tmp_path / "test.txt"
        write_result = await file_write({"path": str(target), "content": "hello"}, ctx)
        assert "Wrote" in write_result
        read_result = await file_read({"path": str(target)}, ctx)
        assert read_result == "hello"

    async def test_file_read_missing(self, tmp_path: Path) -> None:
        ctx = {"allowed_roots": [tmp_path]}
        result = await file_read({"path": str(tmp_path / "missing.txt")}, ctx)
        assert "not found" in result.lower()

    async def test_sandbox_blocks_outside(self, tmp_path: Path) -> None:
        ctx = {"allowed_roots": [tmp_path]}
        with pytest.raises(ToolSandboxError):
            await file_read({"path": "/etc/passwd"}, ctx)

    async def test_file_write_append(self, tmp_path: Path) -> None:
        ctx = {"allowed_roots": [tmp_path]}
        target = tmp_path / "log.txt"
        await file_write({"path": str(target), "content": "line1\n"}, ctx)
        await file_write({"path": str(target), "content": "line2\n", "mode": "append"}, ctx)
        result = await file_read({"path": str(target)}, ctx)
        assert "line1" in result and "line2" in result


@pytest.mark.asyncio
class TestMemoryTools:
    async def test_write_then_read(self, tmp_path: Path) -> None:
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        memory = MemoryManager(users_dir)
        ctx = {"memory_manager": memory}

        write_msg = await vault_memory_write(
            {"title": "Test Pref", "content": "concise outputs", "tags": ["preferences"]},
            ctx,
        )
        assert "Saved" in write_msg

        read_result = await vault_memory_read({"filename": "agent-test-pref.md"}, ctx)
        assert "concise outputs" in read_result

    async def test_read_missing_returns_friendly(self, tmp_path: Path) -> None:
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        ctx = {"memory_manager": MemoryManager(users_dir)}
        result = await vault_memory_read({"filename": "nonexistent.md"}, ctx)
        assert "not found" in result.lower()
