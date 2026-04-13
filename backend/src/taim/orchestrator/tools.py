"""ToolExecutor — registers and executes tools with sandboxing + denylist."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import jsonschema
import structlog

from taim.errors import TaimError
from taim.models.tool import Tool, ToolCall, ToolResult
from taim.orchestrator.tool_registry import ToolRegistry

logger = structlog.get_logger()

ToolFn = Callable[[dict[str, Any], dict[str, Any]], Awaitable[str]]


class ToolError(TaimError):
    """Generic tool execution error."""


class ToolExecutor:
    """Registers and executes tools. Returns errors to LLM, never crashes the agent."""

    def __init__(
        self,
        registry: ToolRegistry,
        global_denylist: list[str] | None = None,
    ) -> None:
        self._registry = registry
        self._executors: dict[str, ToolFn] = {}
        self._denylist = set(global_denylist or [])

    def register(self, name: str, fn: ToolFn) -> None:
        if self._registry.get_schema(name) is None:
            logger.warning("tool_executor.no_schema", name=name)
        self._executors[name] = fn

    def list_tools(self) -> list[Tool]:
        return [
            t
            for t in self._registry.list_schemas()
            if t.name in self._executors and t.name not in self._denylist
        ]

    def get_tools_for_agent(self, allowed_names: list[str]) -> list[dict]:
        result = []
        for tool in self.list_tools():
            if tool.name in allowed_names:
                result.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                        },
                    }
                )
        return result

    async def execute(
        self,
        call: ToolCall,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        if call.name in self._denylist:
            return ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=False,
                error=f"Tool '{call.name}' is disabled by global denylist.",
            )

        schema = self._registry.get_schema(call.name)
        executor = self._executors.get(call.name)
        if schema is None or executor is None:
            return ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=False,
                error=f"Tool '{call.name}' is not available.",
            )

        try:
            jsonschema.validate(call.arguments, schema.parameters)
        except jsonschema.ValidationError as e:
            return ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=False,
                error=f"Invalid arguments: {e.message}",
            )

        start = time.monotonic()
        try:
            output = await executor(call.arguments, context or {})
            return ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=True,
                output=output,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as e:  # noqa: BLE001 — tool errors must not crash agent
            logger.exception("tool_executor.error", tool=call.name)
            return ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=False,
                error=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            )
