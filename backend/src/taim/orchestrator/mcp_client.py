"""MCP Client — connects to external MCP servers and discovers tools."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import structlog
import yaml

from taim.models.tool import Tool

logger = structlog.get_logger()


class MCPServerConfig:
    """Parsed config for one MCP server."""

    def __init__(self, data: dict) -> None:
        self.name: str = data["name"]
        self.command: str | None = data.get("command")
        self.url: str | None = data.get("url")
        self.enabled: bool = data.get("enabled", True)
        self.env: dict[str, str] = data.get("env", {})


class MCPToolWrapper:
    """Wraps an MCP tool call, forwarding to the connected MCP server."""

    def __init__(self, server_name: str, tool_name: str, session) -> None:
        self._server_name = server_name
        self._tool_name = tool_name
        self._session = session

    async def __call__(self, args: dict[str, Any], context: dict[str, Any]) -> str:
        """Execute the MCP tool call via the session."""
        try:
            result = await self._session.call_tool(self._tool_name, arguments=args)
            # Extract text content from result
            if hasattr(result, "content") and result.content:
                texts = []
                for block in result.content:
                    if hasattr(block, "text"):
                        texts.append(block.text)
                return "\n".join(texts) if texts else str(result)
            return str(result)
        except Exception as e:
            return f"MCP tool error ({self._server_name}/{self._tool_name}): {e}"


class MCPManager:
    """Manages connections to multiple MCP servers."""

    def __init__(self) -> None:
        self._sessions: dict[str, Any] = {}
        self._tools: dict[str, tuple[Tool, MCPToolWrapper]] = {}
        self._cleanup_tasks: list[Any] = []

    async def connect_servers(self, config_path: Path) -> None:
        """Load config and connect to all enabled MCP servers."""
        if not config_path.exists():
            logger.info("mcp.no_config", path=str(config_path))
            return

        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            logger.warning("mcp.config_parse_error", error=str(e))
            return

        servers = data.get("mcp_servers", [])
        if not servers:
            logger.info("mcp.no_servers_configured")
            return

        for server_data in servers:
            try:
                config = MCPServerConfig(server_data)
                if not config.enabled:
                    continue
                await self._connect_one(config)
            except Exception:
                logger.exception("mcp.connect_failed", server=server_data.get("name", "?"))

    async def _connect_one(self, config: MCPServerConfig) -> None:
        """Connect to a single MCP server and discover its tools."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            logger.warning("mcp.sdk_not_available", hint="pip install mcp")
            return

        if config.command:
            # Stdio transport
            env = dict(os.environ)
            for k, v in config.env.items():
                # Resolve ${VAR} references
                if v.startswith("${") and v.endswith("}"):
                    env_key = v[2:-1]
                    env[k] = os.environ.get(env_key, "")
                else:
                    env[k] = v

            parts = config.command.split()
            server_params = StdioServerParameters(
                command=parts[0],
                args=parts[1:] if len(parts) > 1 else [],
                env=env,
            )

            try:
                read_stream, write_stream = await asyncio.wait_for(
                    stdio_client(server_params).__aenter__(),
                    timeout=15,
                )
                session = ClientSession(read_stream, write_stream)
                await session.__aenter__()
                await session.initialize()
            except (TimeoutError, Exception) as e:
                logger.warning("mcp.stdio_connect_failed", server=config.name, error=str(e))
                return

            self._sessions[config.name] = session

        elif config.url:
            # SSE transport — simplified for MVP
            logger.info("mcp.sse_not_implemented_yet", server=config.name)
            return
        else:
            logger.warning("mcp.no_transport", server=config.name)
            return

        # Discover tools
        try:
            tools_result = await session.list_tools()
            for tool_def in tools_result.tools:
                full_name = f"{config.name}/{tool_def.name}"
                schema = Tool(
                    name=full_name,
                    description=tool_def.description or f"MCP tool: {tool_def.name}",
                    parameters=tool_def.inputSchema
                    if hasattr(tool_def, "inputSchema")
                    else {"type": "object", "properties": {}},
                    source=f"mcp:{config.name}",
                )
                wrapper = MCPToolWrapper(config.name, tool_def.name, session)
                self._tools[full_name] = (schema, wrapper)

            logger.info(
                "mcp.connected",
                server=config.name,
                tools=len(tools_result.tools),
            )
        except Exception:
            logger.exception("mcp.tool_discovery_failed", server=config.name)

    def get_discovered_tools(self) -> list[tuple[Tool, MCPToolWrapper]]:
        """Return all discovered MCP tools (schema + executor pairs)."""
        return list(self._tools.values())

    @property
    def connected_count(self) -> int:
        return len(self._sessions)

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    async def disconnect_all(self) -> None:
        """Close all MCP sessions."""
        for name, session in self._sessions.items():
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                logger.exception("mcp.disconnect_error", server=name)
        self._sessions.clear()
        self._tools.clear()
