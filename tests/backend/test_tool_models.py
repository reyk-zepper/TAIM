"""Tests for tool data models."""

from taim.models.tool import Tool, ToolCall, ToolExecutionEvent, ToolResult


class TestTool:
    def test_minimal(self) -> None:
        t = Tool(
            name="file_read",
            description="Read a file",
            parameters={"type": "object", "properties": {}, "required": []},
        )
        assert t.requires_approval is False
        assert t.source == "builtin"


class TestToolCall:
    def test_minimal(self) -> None:
        c = ToolCall(id="call-1", name="file_read", arguments={"path": "/tmp/x"})
        assert c.arguments["path"] == "/tmp/x"


class TestToolResult:
    def test_success(self) -> None:
        r = ToolResult(call_id="c1", tool_name="file_read", success=True, output="hello", duration_ms=12.0)
        assert r.error == ""

    def test_failure(self) -> None:
        r = ToolResult(call_id="c1", tool_name="file_read", success=False, error="not found")
        assert r.output == ""


class TestToolExecutionEvent:
    def test_minimal(self) -> None:
        e = ToolExecutionEvent(agent_name="researcher", run_id="r1", tool_name="file_read", status="running")
        assert e.duration_ms == 0.0
        assert e.error == ""
