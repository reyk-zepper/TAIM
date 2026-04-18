"""Tests for MCP client — config loading, graceful failure."""

from pathlib import Path

import pytest

from taim.orchestrator.mcp_client import MCPManager, MCPServerConfig


class TestMCPServerConfig:
    def test_parse_minimal(self) -> None:
        cfg = MCPServerConfig({"name": "test", "command": "echo hello"})
        assert cfg.name == "test"
        assert cfg.command == "echo hello"
        assert cfg.enabled is True

    def test_disabled(self) -> None:
        cfg = MCPServerConfig({"name": "test", "command": "x", "enabled": False})
        assert cfg.enabled is False

    def test_url_transport(self) -> None:
        cfg = MCPServerConfig({"name": "api", "url": "http://localhost:3000"})
        assert cfg.url == "http://localhost:3000"
        assert cfg.command is None


class TestMCPManager:
    @pytest.mark.asyncio
    async def test_empty_config(self, tmp_path: Path) -> None:
        mgr = MCPManager()
        (tmp_path / "mcp.yaml").write_text("mcp_servers: []\n")
        await mgr.connect_servers(tmp_path / "mcp.yaml")
        assert mgr.connected_count == 0
        assert mgr.tool_count == 0

    @pytest.mark.asyncio
    async def test_missing_config(self, tmp_path: Path) -> None:
        mgr = MCPManager()
        await mgr.connect_servers(tmp_path / "nonexistent.yaml")
        assert mgr.connected_count == 0

    @pytest.mark.asyncio
    async def test_invalid_config(self, tmp_path: Path) -> None:
        mgr = MCPManager()
        (tmp_path / "mcp.yaml").write_text("not: valid: [")
        await mgr.connect_servers(tmp_path / "mcp.yaml")
        assert mgr.connected_count == 0

    @pytest.mark.asyncio
    async def test_disabled_server_skipped(self, tmp_path: Path) -> None:
        mgr = MCPManager()
        (tmp_path / "mcp.yaml").write_text(
            "mcp_servers:\n  - name: test\n    command: echo hello\n    enabled: false\n"
        )
        await mgr.connect_servers(tmp_path / "mcp.yaml")
        assert mgr.connected_count == 0

    @pytest.mark.asyncio
    async def test_get_discovered_tools_empty(self) -> None:
        mgr = MCPManager()
        assert mgr.get_discovered_tools() == []
