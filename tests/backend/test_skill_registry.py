"""Tests for SkillRegistry."""

import logging
from pathlib import Path

from taim.brain.skill_registry import SkillRegistry
from taim.orchestrator.tool_registry import ToolRegistry


def _write_skill(skills_dir: Path, name: str, required_tools: list[str] | None = None) -> None:
    tools_yaml = ", ".join(required_tools or [])
    (skills_dir / f"{name}.yaml").write_text(
        f"name: {name}\ndescription: Test {name}\nrequired_tools: [{tools_yaml}]\nprompt_template: 'Be {name}'\n"
    )


class TestLoad:
    def test_loads_valid_skills(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "skill_a")
        _write_skill(skills_dir, "skill_b")
        r = SkillRegistry(skills_dir)
        r.load()
        assert r.get("skill_a") is not None
        assert len(r.list_skills()) == 2

    def test_skips_invalid_yaml(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "bad.yaml").write_text("not: valid: [")
        _write_skill(skills_dir, "good")
        r = SkillRegistry(skills_dir)
        r.load()
        assert r.get("good") is not None
        assert r.get("bad") is None

    def test_missing_dir(self, tmp_path: Path) -> None:
        r = SkillRegistry(tmp_path / "nonexistent")
        r.load()
        assert r.list_skills() == []


class TestValidateAgainstTools:
    def test_unknown_tool_keeps_skill_registered(self, tmp_path: Path, caplog) -> None:
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "needs_unknown", required_tools=["nonexistent_tool"])

        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        tool_reg = ToolRegistry(tools_dir)
        tool_reg.load()

        skill_reg = SkillRegistry(skills_dir)
        skill_reg.load()

        with caplog.at_level(logging.WARNING):
            skill_reg.validate_against_tools(tool_reg)

        assert skill_reg.get("needs_unknown") is not None

    def test_known_tool_no_error(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "needs_known", required_tools=["echo"])

        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "echo.yaml").write_text(
            "name: echo\ndescription: Echo\nparameters: {type: object, properties: {}, required: []}\n"
        )
        tool_reg = ToolRegistry(tools_dir)
        tool_reg.load()

        skill_reg = SkillRegistry(skills_dir)
        skill_reg.load()
        skill_reg.validate_against_tools(tool_reg)
        assert skill_reg.get("needs_known") is not None
