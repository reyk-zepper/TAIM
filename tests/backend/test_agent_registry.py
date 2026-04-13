"""Tests for AgentRegistry."""

from pathlib import Path

import pytest

from taim.brain.agent_registry import AgentRegistry


class TestLoad:
    def test_loads_valid_agents(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "a.yaml").write_text(
            "name: a\ndescription: A\nmodel_preference: [tier2_standard]\nskills: [s1]\n"
        )
        registry = AgentRegistry(agents_dir)
        registry.load()
        assert registry.get_agent("a") is not None
        assert len(registry.list_agents()) == 1

    def test_skips_invalid_yaml(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "bad.yaml").write_text("not: valid: yaml: [")
        (agents_dir / "good.yaml").write_text(
            "name: good\ndescription: Good\nmodel_preference: [tier2_standard]\nskills: []\n"
        )
        registry = AgentRegistry(agents_dir)
        registry.load()
        assert registry.get_agent("good") is not None
        assert registry.get_agent("bad") is None

    def test_missing_dir(self, tmp_path: Path) -> None:
        registry = AgentRegistry(tmp_path / "nonexistent")
        registry.load()
        assert registry.list_agents() == []


class TestQuery:
    def _setup(self, tmp_path: Path) -> AgentRegistry:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "r.yaml").write_text(
            "name: r\ndescription: R\nmodel_preference: [tier2_standard]\nskills: [research, summarization]\n"
        )
        (agents_dir / "c.yaml").write_text(
            "name: c\ndescription: C\nmodel_preference: [tier1_premium]\nskills: [coding]\n"
        )
        registry = AgentRegistry(agents_dir)
        registry.load()
        return registry

    def test_get_by_name(self, tmp_path: Path) -> None:
        registry = self._setup(tmp_path)
        assert registry.get_agent("r").name == "r"
        assert registry.get_agent("nonexistent") is None

    def test_find_by_skill(self, tmp_path: Path) -> None:
        registry = self._setup(tmp_path)
        results = registry.find_by_skill("research")
        assert len(results) == 1
        assert results[0].name == "r"

    def test_find_by_skill_case_insensitive(self, tmp_path: Path) -> None:
        registry = self._setup(tmp_path)
        assert len(registry.find_by_skill("RESEARCH")) == 1


class TestReload:
    def test_reload_picks_up_new_file(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        registry = AgentRegistry(agents_dir)
        registry.load()
        assert registry.list_agents() == []

        (agents_dir / "new.yaml").write_text(
            "name: new\ndescription: New\nmodel_preference: [tier2_standard]\nskills: []\n"
        )
        registry.reload()
        assert registry.get_agent("new") is not None
