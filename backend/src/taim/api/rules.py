"""Rules REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from taim.brain.rule_engine import RuleEngine

router = APIRouter(prefix="/api/rules")


def get_rule_engine(request: Request) -> RuleEngine:
    return request.app.state.rule_engine


@router.get("")
async def list_rules(engine: RuleEngine = Depends(get_rule_engine)) -> dict:
    rules = engine.list_rules()
    return {
        "rules": [
            {
                "name": r.name,
                "description": r.description,
                "type": r.type,
                "severity": r.severity,
                "scope": r.scope,
                "rule_count": len(r.rules),
            }
            for r in rules
        ],
        "count": len(rules),
    }


@router.post("/reload")
async def reload_rules(engine: RuleEngine = Depends(get_rule_engine)) -> dict:
    engine.load()
    return {"status": "reloaded", "count": len(engine.list_rules())}
