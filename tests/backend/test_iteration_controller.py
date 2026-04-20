"""Tests for IterationController."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.iteration_controller import IterationController
from taim.brain.rule_engine import RuleEngine
from taim.models.agent import Agent, ReviewResult


def _agent(max_iter: int = 3) -> Agent:
    return Agent(
        name="researcher", description="Test",
        model_preference=["tier2_standard"], skills=[],
        max_iterations=max_iter,
    )


def _review(
    quality_ok: bool = True,
    feedback: str = "ok",
    completeness: float = 0.9,
    accuracy: float = 0.9,
    relevance: float = 0.9,
    rule_compliance: bool = True,
) -> ReviewResult:
    return ReviewResult(
        quality_ok=quality_ok,
        feedback=feedback,
        completeness=completeness,
        accuracy=accuracy,
        relevance=relevance,
        rule_compliance=rule_compliance,
    )


class TestShouldIterate:
    def test_quality_ok_no_iterate(self) -> None:
        ctrl = IterationController()
        should, reason = ctrl.should_iterate(_review(), iteration=0, max_iterations=3, agent=_agent())
        assert should is False
        assert reason == "review_passed"

    def test_max_iterations_stops(self) -> None:
        ctrl = IterationController()
        should, reason = ctrl.should_iterate(
            _review(quality_ok=False), iteration=3, max_iterations=3, agent=_agent(),
        )
        assert should is False
        assert "max_iterations" in reason

    def test_rule_compliance_failure_forces_iteration(self) -> None:
        ctrl = IterationController()
        should, reason = ctrl.should_iterate(
            _review(quality_ok=True, rule_compliance=False),
            iteration=0, max_iterations=3, agent=_agent(),
        )
        assert should is True
        assert "rule_compliance" in reason

    def test_low_completeness_forces_iteration(self) -> None:
        ctrl = IterationController()
        should, reason = ctrl.should_iterate(
            _review(quality_ok=True, completeness=0.3),
            iteration=0, max_iterations=3, agent=_agent(),
        )
        assert should is True
        assert "completeness" in reason

    def test_low_accuracy_forces_iteration(self) -> None:
        ctrl = IterationController()
        should, reason = ctrl.should_iterate(
            _review(quality_ok=True, accuracy=0.4),
            iteration=0, max_iterations=3, agent=_agent(),
        )
        assert should is True
        assert "accuracy" in reason

    def test_reviewer_says_not_ok_iterates(self) -> None:
        ctrl = IterationController()
        should, reason = ctrl.should_iterate(
            _review(quality_ok=False, completeness=0.3),
            iteration=0, max_iterations=3, agent=_agent(),
        )
        assert should is True


class TestBuildReviewContext:
    def test_empty_without_rule_engine(self) -> None:
        ctrl = IterationController()
        assert ctrl.build_review_context(_agent()) == ""

    def test_includes_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules" / "c"
        rules_dir.mkdir(parents=True)
        import yaml
        (rules_dir / "r.yaml").write_text(yaml.dump({
            "name": "test", "description": "t", "type": "compliance",
            "severity": "mandatory", "scope": "global",
            "rules": ["No PII in output"],
        }))
        engine = RuleEngine(tmp_path / "rules")
        engine.load()
        ctrl = IterationController(rule_engine=engine)
        ctx = ctrl.build_review_context(_agent())
        assert "No PII" in ctx
        assert "rule_compliance" in ctx
