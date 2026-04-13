"""Tests for Skill model."""

from taim.models.skill import Skill


class TestSkill:
    def test_minimal(self) -> None:
        s = Skill(name="x", description="X", prompt_template="Be X")
        assert s.required_tools == []
        assert s.output_format == "markdown"

    def test_full(self) -> None:
        s = Skill(
            name="web_research",
            description="Research the web",
            required_tools=["web_search", "web_fetch"],
            prompt_template="You are researching {{ task_description }}",
            output_format="markdown",
        )
        assert "web_search" in s.required_tools
