"""Tests for Rules Engine."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from taim.brain.memory import MemoryManager
from taim.brain.rule_engine import RuleEngine
from taim.models.memory import MemoryEntry
from taim.models.rule import Rule, RuleSeverity, RuleType


def _write_rule(
    rules_dir: Path,
    subdir: str,
    name: str,
    rules: list[str],
    severity: str = "mandatory",
    scope: str = "global",
) -> None:
    d = rules_dir / subdir
    d.mkdir(parents=True, exist_ok=True)
    import yaml

    (d / f"{name}.yaml").write_text(
        yaml.dump({
            "name": name,
            "description": f"Test {name}",
            "type": "compliance",
            "severity": severity,
            "scope": scope,
            "rules": rules,
        })
    )


class TestLoad:
    def test_loads_yaml_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules"
        _write_rule(rules_dir, "compliance", "gdpr", ["No PII in outputs"])
        engine = RuleEngine(rules_dir)
        engine.load()
        assert len(engine.list_rules()) == 1
        assert engine.list_rules()[0].name == "gdpr"

    def test_loads_from_subdirectories(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules"
        _write_rule(rules_dir, "compliance", "gdpr", ["rule1"])
        _write_rule(rules_dir, "behavior", "style", ["rule2"])
        engine = RuleEngine(rules_dir)
        engine.load()
        assert len(engine.list_rules()) == 2

    def test_skips_invalid_yaml(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules" / "compliance"
        rules_dir.mkdir(parents=True)
        (rules_dir / "bad.yaml").write_text("not: valid: [")
        _write_rule(tmp_path / "rules", "compliance", "good", ["ok"])
        engine = RuleEngine(tmp_path / "rules")
        engine.load()
        assert len(engine.list_rules()) == 1

    def test_missing_dir_no_error(self, tmp_path: Path) -> None:
        engine = RuleEngine(tmp_path / "nonexistent")
        engine.load()
        assert engine.list_rules() == []


class TestGetActiveRules:
    def test_global_rules_always_active(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules"
        _write_rule(rules_dir, "c", "r1", ["rule1"], scope="global")
        engine = RuleEngine(rules_dir)
        engine.load()
        rs = engine.get_active_rules()
        assert len(rs.mandatory) == 1

    def test_agent_scoped_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules"
        _write_rule(rules_dir, "c", "coder-only", ["no eval()"], scope="agent:coder")
        engine = RuleEngine(rules_dir)
        engine.load()
        # Matches
        rs = engine.get_active_rules(agent_name="coder")
        assert len(rs.mandatory) == 1
        # Doesn't match
        rs = engine.get_active_rules(agent_name="researcher")
        assert len(rs.mandatory) == 0

    def test_severity_split(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules"
        _write_rule(rules_dir, "c", "hard", ["must do"], severity="mandatory")
        _write_rule(rules_dir, "b", "soft", ["should do"], severity="advisory")
        engine = RuleEngine(rules_dir)
        engine.load()
        rs = engine.get_active_rules()
        assert len(rs.mandatory) == 1
        assert len(rs.advisory) == 1


class TestCompileForContext:
    def test_formats_mandatory_and_advisory(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules"
        _write_rule(rules_dir, "c", "hard", ["No PII"], severity="mandatory")
        _write_rule(rules_dir, "b", "soft", ["Be concise"], severity="advisory")
        engine = RuleEngine(rules_dir)
        engine.load()
        rs = engine.get_active_rules()
        text = engine.compile_for_context(rs)
        assert "MUST follow" in text
        assert "No PII" in text
        assert "GUIDELINES" in text
        assert "Be concise" in text

    def test_empty_returns_empty_string(self) -> None:
        from taim.models.rule import RuleSet

        engine = RuleEngine(Path("/nonexistent"))
        assert engine.compile_for_context(RuleSet()) == ""


@pytest.mark.asyncio
class TestMemoryRules:
    async def test_loads_from_memory(self, tmp_path: Path) -> None:
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        memory = MemoryManager(users_dir)
        today = date.today()
        await memory.write_entry(
            MemoryEntry(
                title="Compliance Rules",
                category="rules",
                tags=["rules", "compliance"],
                created=today,
                updated=today,
                content="- Never share API keys\n- Always use HTTPS",
            ),
            "compliance-rules.md",
        )

        engine = RuleEngine(tmp_path / "rules", memory=memory)
        engine.load()
        await engine.load_memory_rules()
        rules = engine.list_rules()
        assert any(r.name == "onboarding-rules" for r in rules)
        onboarding = next(r for r in rules if r.name == "onboarding-rules")
        assert "Never share API keys" in onboarding.rules

    async def test_no_memory_no_error(self, tmp_path: Path) -> None:
        engine = RuleEngine(tmp_path / "rules", memory=None)
        await engine.load_memory_rules()
        assert engine.list_rules() == []
