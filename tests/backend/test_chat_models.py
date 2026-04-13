"""Tests for chat/intent data models."""

import pytest

from taim.models.chat import (
    InterpreterResult, IntentCategory, IntentClassification, IntentResult, TaskConstraints,
)


class TestIntentCategory:
    def test_all_categories(self) -> None:
        assert IntentCategory.NEW_TASK == "new_task"
        assert IntentCategory.STATUS_QUERY == "status_query"
        assert IntentCategory.STOP_COMMAND == "stop_command"


class TestIntentClassification:
    def test_minimal(self) -> None:
        c = IntentClassification(category=IntentCategory.CONFIRMATION, confidence=0.95)
        assert c.needs_deep_analysis is False

    def test_confidence_bounds(self) -> None:
        with pytest.raises(Exception):
            IntentClassification(category=IntentCategory.NEW_TASK, confidence=1.5)
        with pytest.raises(Exception):
            IntentClassification(category=IntentCategory.NEW_TASK, confidence=-0.1)


class TestTaskConstraints:
    def test_defaults(self) -> None:
        tc = TaskConstraints()
        assert tc.time_limit_seconds is None
        assert tc.budget_eur is None
        assert tc.specific_agents == []


class TestIntentResult:
    def test_minimal(self) -> None:
        r = IntentResult(task_type="research", objective="Find competitors")
        assert r.parameters == {}
        assert r.missing_info == []
        assert isinstance(r.constraints, TaskConstraints)


class TestInterpreterResult:
    def test_with_intent(self) -> None:
        c = IntentClassification(category=IntentCategory.NEW_TASK, confidence=0.9)
        intent = IntentResult(task_type="research", objective="Find X")
        r = InterpreterResult(classification=c, intent=intent)
        assert r.direct_response is None
        assert r.needs_followup is False

    def test_with_direct_response(self) -> None:
        c = IntentClassification(category=IntentCategory.STATUS_QUERY, confidence=0.95)
        r = InterpreterResult(classification=c, direct_response="No active team.")
        assert r.intent is None
