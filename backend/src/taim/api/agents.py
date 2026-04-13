"""Agent REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from taim.api.deps import get_registry
from taim.brain.agent_registry import AgentRegistry
from taim.models.agent import Agent

router = APIRouter(prefix="/api/agents")


@router.get("")
async def list_agents(registry: AgentRegistry = Depends(get_registry)) -> dict:
    agents = registry.list_agents()
    return {
        "agents": [
            {"name": a.name, "description": a.description, "skills": a.skills} for a in agents
        ],
        "count": len(agents),
    }


@router.get("/{agent_name}")
async def get_agent(
    agent_name: str,
    registry: AgentRegistry = Depends(get_registry),
) -> Agent:
    agent = registry.get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return agent
