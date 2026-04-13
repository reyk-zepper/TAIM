"""Tests for AgentStateMachine tool calling loop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.agent_run_store import AgentRunStore
from taim.brain.agent_state_machine import AgentStateMachine
from taim.brain.database import init_database
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.models.agent import Agent, AgentStateEnum
from taim.models.router import LLMResponse
from taim.models.tool import ToolExecutionEvent
from taim.orchestrator.tool_registry import ToolRegistry
from taim.orchestrator.tools import ToolExecutor

from conftest import MockRouter, make_response


def _make_response_with_tool_calls(
    tool_name: str, arguments: dict, call_id: str = "tc-1"
) -> LLMResponse:
    return LLMResponse(
        content="",
        model="m", provider="p",
        prompt_tokens=10, completion_tokens=5,
        cost_usd=0.001, latency_ms=50.0,
        tool_calls=[{
            "id": call_id,
            "name": tool_name,
            "arguments": json.dumps(arguments),
        }],
    )


@pytest_asyncio.fixture
async def setup(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    db = await init_database(ops.vault_config.db_path)
    store = AgentRunStore(db)

    # Build a simple registry + executor with one test tool
    test_tools_dir = tmp_vault / "test-tools"
    test_tools_dir.mkdir()
    (test_tools_dir / "echo.yaml").write_text(
        "name: echo\ndescription: Echo\nparameters:\n  type: object\n  properties:\n    msg: {type: string}\n  required: [msg]\n"
    )
    registry = ToolRegistry(test_tools_dir)
    registry.load()
    executor = ToolExecutor(registry=registry)

    async def echo_fn(args, ctx):
        return f"echoed:{args['msg']}"

    executor.register("echo", echo_fn)

    yield ops, loader, store, executor
    await db.close()


def _make_agent(tools: list[str] | None = None) -> Agent:
    return Agent(
        name="researcher",
        description="Test",
        model_preference=["tier2_standard"],
        skills=[],
        tools=tools or [],
    )


@pytest.mark.asyncio
class TestToolLoop:
    async def test_executes_tool_then_returns(self, setup) -> None:
        _, loader, store, executor = setup
        router = MockRouter([
            make_response("plan"),
            _make_response_with_tool_calls("echo", {"msg": "hi"}),
            make_response("Done with tools, here's the result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = _make_agent(tools=["echo"])
        sm = AgentStateMachine(
            agent=agent,
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
            tool_executor=executor,
            tool_context={},
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
        assert "result" in run.result_content.lower()

    async def test_no_tools_falls_back_to_normal_flow(self, setup) -> None:
        _, loader, store, executor = setup
        router = MockRouter([
            make_response("plan"),
            make_response("normal result"),
            make_response('{"quality_ok": true, "feedback": ""}'),
        ])
        agent = _make_agent(tools=[])
        sm = AgentStateMachine(
            agent=agent,
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
            tool_executor=executor,
            tool_context={},
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE
        assert run.result_content == "normal result"

    async def test_tool_event_emitted(self, setup) -> None:
        _, loader, store, executor = setup
        events: list[ToolExecutionEvent] = []

        async def capture(e: ToolExecutionEvent) -> None:
            events.append(e)

        router = MockRouter([
            make_response("plan"),
            _make_response_with_tool_calls("echo", {"msg": "hi"}),
            make_response("done"),
            make_response('{"quality_ok": true, "feedback": ""}'),
        ])
        agent = _make_agent(tools=["echo"])
        sm = AgentStateMachine(
            agent=agent,
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
            tool_executor=executor,
            tool_context={},
            on_tool_event=capture,
        )
        await sm.run()
        statuses = [e.status for e in events]
        assert "running" in statuses
        assert "completed" in statuses

    async def test_tool_error_continues(self, setup) -> None:
        _, loader, store, executor = setup

        async def crashing_fn(args, ctx):
            raise RuntimeError("intentional test failure")

        executor.register("echo", crashing_fn)
        router = MockRouter([
            make_response("plan"),
            _make_response_with_tool_calls("echo", {"msg": "hi"}),
            make_response("recovered after error"),
            make_response('{"quality_ok": true, "feedback": ""}'),
        ])
        agent = _make_agent(tools=["echo"])
        sm = AgentStateMachine(
            agent=agent,
            router=router, prompt_loader=loader, run_store=store,
            task_id="t1", task_description="test",
            tool_executor=executor,
            tool_context={},
        )
        run = await sm.run()
        # Agent recovered — DONE not FAILED
        assert run.final_state == AgentStateEnum.DONE
