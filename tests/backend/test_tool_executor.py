"""Tests for ToolExecutor."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.models.tool import ToolCall
from taim.orchestrator.tool_registry import ToolRegistry
from taim.orchestrator.tools import ToolExecutor


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "echo.yaml").write_text(
        "name: echo\ndescription: Echo back\nparameters:\n"
        "  type: object\n  properties:\n    msg: {type: string}\n  required: [msg]\n"
    )
    r = ToolRegistry(tools_dir)
    r.load()
    return r


@pytest.fixture
def executor(registry: ToolRegistry) -> ToolExecutor:
    e = ToolExecutor(registry=registry)

    async def echo_fn(args, ctx):
        return f"echoed: {args['msg']}"

    e.register("echo", echo_fn)
    return e


@pytest.mark.asyncio
class TestExecute:
    async def test_success(self, executor: ToolExecutor) -> None:
        result = await executor.execute(ToolCall(id="c1", name="echo", arguments={"msg": "hi"}))
        assert result.success is True
        assert result.output == "echoed: hi"
        assert result.duration_ms >= 0

    async def test_invalid_arguments(self, executor: ToolExecutor) -> None:
        result = await executor.execute(ToolCall(id="c1", name="echo", arguments={}))
        assert result.success is False
        assert "msg" in result.error.lower() or "required" in result.error.lower()

    async def test_unknown_tool(self, executor: ToolExecutor) -> None:
        result = await executor.execute(ToolCall(id="c1", name="nonexistent", arguments={}))
        assert result.success is False
        assert "not available" in result.error.lower()

    async def test_executor_exception_swallowed(self, registry: ToolRegistry) -> None:
        e = ToolExecutor(registry=registry)

        async def crashy(args, ctx):
            raise RuntimeError("boom")

        e.register("echo", crashy)
        result = await e.execute(ToolCall(id="c1", name="echo", arguments={"msg": "x"}))
        assert result.success is False
        assert "boom" in result.error


@pytest.mark.asyncio
class TestDenylist:
    async def test_denied_tool_returns_error(self, registry: ToolRegistry) -> None:
        e = ToolExecutor(registry=registry, global_denylist=["echo"])

        async def echo_fn(args, ctx):
            return "ok"

        e.register("echo", echo_fn)
        result = await e.execute(ToolCall(id="c1", name="echo", arguments={"msg": "x"}))
        assert result.success is False
        assert "denylist" in result.error.lower() or "disabled" in result.error.lower()


class TestGetToolsForAgent:
    def test_returns_litellm_format(self, executor: ToolExecutor) -> None:
        tools = executor.get_tools_for_agent(["echo"])
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "echo"

    def test_filters_by_agent_allowed(self, executor: ToolExecutor) -> None:
        tools = executor.get_tools_for_agent(["nonexistent"])
        assert tools == []
