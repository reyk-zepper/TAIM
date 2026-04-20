"""Data models for the Rules Engine."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class RuleType(StrEnum):
    COMPLIANCE = "compliance"
    BEHAVIOR = "behavior"
    OUTPUT = "output"


class RuleSeverity(StrEnum):
    MANDATORY = "mandatory"
    ADVISORY = "advisory"


class Rule(BaseModel):
    """A set of rules loaded from a YAML file."""

    name: str
    description: str
    type: RuleType = RuleType.COMPLIANCE
    severity: RuleSeverity = RuleSeverity.MANDATORY
    scope: str = "global"
    rules: list[str]


class RuleSet(BaseModel):
    """Compiled rules for context injection."""

    mandatory: list[Rule] = []
    advisory: list[Rule] = []
