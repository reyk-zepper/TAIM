"""Tests for ContextAssembler — token-budgeted context building."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from taim.brain.context_assembler import ContextAssembler, count_tokens
from taim.brain.memory import MemoryManager
from taim.models.agent import Agent
from taim.models.chat import TaskConstraints
from taim.models.memory import MemoryEntry


def _agent(tier: str = "tier2_standard", skills: list[str] | None = None) -> Agent:
    return Agent(
        name="test",
        description="Test agent",
        model_preference=[tier],
        skills=skills or [],
    )


class TestCountTokens:
    def test_counts(self) -> None:
        assert count_tokens("hello world") > 0

    def test_empty(self) -> None:
        assert count_tokens("") == 0


@pytest.mark.asyncio
class TestAssembleConstraints:
    async def test_includes_constraints(self) -> None:
        assembler = ContextAssembler()
        context = await assembler.assemble(
            agent=_agent(),
            task_description="test",
            constraints=TaskConstraints(time_limit_seconds=300, budget_eur=5.0),
        )
        assert "5 minutes" in context
        assert "€5.00" in context

    async def test_no_constraints_no_output(self) -> None:
        assembler = ContextAssembler()
        context = await assembler.assemble(
            agent=_agent(),
            task_description="test",
        )
        assert context == ""


@pytest.mark.asyncio
class TestAssembleMemory:
    async def test_includes_relevant_memory(self, tmp_path: Path) -> None:
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        memory = MemoryManager(users_dir)
        today = date.today()
        await memory.write_entry(
            MemoryEntry(
                title="User Prefs",
                category="preferences",
                tags=["preferences", "test"],
                created=today,
                updated=today,
                content="User prefers concise outputs.",
            ),
            "prefs.md",
        )

        assembler = ContextAssembler(memory=memory)
        context = await assembler.assemble(
            agent=_agent(skills=["preferences"]),
            task_description="write something concise",
        )
        assert "concise outputs" in context

    async def test_no_memory_manager_returns_empty(self) -> None:
        assembler = ContextAssembler(memory=None)
        context = await assembler.assemble(
            agent=_agent(),
            task_description="test",
        )
        assert context == ""


@pytest.mark.asyncio
class TestAssemblePreviousResults:
    async def test_includes_previous_results(self) -> None:
        assembler = ContextAssembler()
        context = await assembler.assemble(
            agent=_agent(),
            task_description="test",
            previous_results=[("researcher", "Found 3 SaaS competitors")],
        )
        assert "researcher" in context
        assert "3 SaaS competitors" in context

    async def test_truncates_long_results(self) -> None:
        assembler = ContextAssembler()
        long_result = "x" * 10000
        context = await assembler.assemble(
            agent=_agent(),
            task_description="test",
            previous_results=[("agent_a", long_result)],
        )
        # Should be truncated to ~4000 chars
        assert len(context) < 6000


@pytest.mark.asyncio
class TestBudgetEnforcement:
    async def test_respects_tier_budget(self, tmp_path: Path) -> None:
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        memory = MemoryManager(users_dir)
        today = date.today()

        # Write many memory entries
        for i in range(20):
            await memory.write_entry(
                MemoryEntry(
                    title=f"Entry {i}",
                    category="data",
                    tags=["keyword"],
                    created=today,
                    updated=today,
                    content=f"Long content for entry {i}. " * 50,
                ),
                f"entry_{i}.md",
            )

        assembler = ContextAssembler(memory=memory)
        # Tier 3 has only 800 token budget
        context = await assembler.assemble(
            agent=_agent(tier="tier3_economy", skills=["keyword"]),
            task_description="find keyword data",
        )
        tokens = count_tokens(context)
        assert tokens <= 800

    async def test_tier1_has_more_budget(self) -> None:
        assembler = ContextAssembler()
        context = await assembler.assemble(
            agent=_agent(tier="tier1_premium"),
            task_description="test",
            previous_results=[("a", "x " * 2000)],
        )
        tokens = count_tokens(context)
        assert tokens <= 4000


@pytest.mark.asyncio
class TestPriorityOrder:
    async def test_constraints_before_memory(self, tmp_path: Path) -> None:
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        memory = MemoryManager(users_dir)
        today = date.today()
        await memory.write_entry(
            MemoryEntry(
                title="Pref",
                category="preferences",
                tags=["keyword"],
                created=today,
                updated=today,
                content="Memory content here.",
            ),
            "pref.md",
        )

        assembler = ContextAssembler(memory=memory)
        context = await assembler.assemble(
            agent=_agent(skills=["keyword"]),
            task_description="do keyword thing",
            constraints=TaskConstraints(budget_eur=10.0),
        )
        # Constraints should appear before memory
        constraint_pos = context.find("[Constraints]")
        memory_pos = context.find("[Memory:")
        assert constraint_pos >= 0
        assert memory_pos >= 0
        assert constraint_pos < memory_pos
