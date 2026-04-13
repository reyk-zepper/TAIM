"""Tests for ToolRegistry."""

from pathlib import Path

from taim.orchestrator.tool_registry import ToolRegistry


class TestLoad:
    def test_loads_valid_schemas(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "t1.yaml").write_text(
            "name: t1\ndescription: Test\nparameters:\n  type: object\n  properties: {}\n  required: []\n"
        )
        registry = ToolRegistry(tools_dir)
        registry.load()
        assert registry.get_schema("t1") is not None
        assert len(registry.list_schemas()) == 1

    def test_skips_invalid_yaml(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "bad.yaml").write_text("not: valid: [")
        (tools_dir / "good.yaml").write_text(
            "name: good\ndescription: G\nparameters: {type: object, properties: {}, required: []}\n"
        )
        registry = ToolRegistry(tools_dir)
        registry.load()
        assert registry.get_schema("good") is not None
        assert registry.get_schema("bad") is None

    def test_missing_dir(self, tmp_path: Path) -> None:
        registry = ToolRegistry(tmp_path / "nonexistent")
        registry.load()
        assert registry.list_schemas() == []
