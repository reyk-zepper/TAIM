"""Skill REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from taim.api.deps import get_skill_registry
from taim.brain.skill_registry import SkillRegistry

router = APIRouter(prefix="/api/skills")


@router.get("")
async def list_skills(registry: SkillRegistry = Depends(get_skill_registry)) -> dict:
    skills = registry.list_skills()
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "required_tools": s.required_tools,
                "output_format": s.output_format,
            }
            for s in skills
        ],
        "count": len(skills),
    }
