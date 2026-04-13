"""Tool REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from taim.api.deps import get_tool_executor
from taim.orchestrator.tools import ToolExecutor

router = APIRouter(prefix="/api/tools")


@router.get("")
async def list_tools(executor: ToolExecutor = Depends(get_tool_executor)) -> dict:
    tools = executor.list_tools()
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "source": t.source,
                "requires_approval": t.requires_approval,
            }
            for t in tools
        ],
        "count": len(tools),
    }
