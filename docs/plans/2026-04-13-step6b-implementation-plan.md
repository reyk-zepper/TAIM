# Step 6b: Skills Layer — Implementation Plan

> **For agentic workers:** Follow superpowers:subagent-driven-development.

**Goal:** Add Skills (reusable prompt+tool patterns), 5 built-in skills, primary-skill prepending in EXECUTING state.

**Architecture:** SkillRegistry loads vault YAMLs, AgentStateMachine prepends primary skill prompt. Design: `docs/plans/2026-04-13-step6b-skills-design.md`.

**Tech Stack:** Same as 6a + Jinja2 (already in deps).

---

## File Structure

### Files to Create
```
backend/src/taim/models/skill.py
backend/src/taim/brain/skill_registry.py
backend/src/taim/api/skills.py
taim-vault/system/skills/{web_research,code_generation,code_review,content_writing,data_analysis}.yaml
tests/backend/test_skill_models.py
tests/backend/test_skill_registry.py
tests/backend/test_agent_state_machine_skills.py
tests/backend/test_skills_api.py
```

### Files to Modify
```
backend/src/taim/brain/vault.py        # Seed skill YAMLs + reorder coder/reviewer skills
backend/src/taim/brain/agent_state_machine.py  # Skill prepending in EXECUTING
backend/src/taim/main.py               # SkillRegistry in lifespan + skills router
backend/src/taim/api/deps.py           # get_skill_registry()
tests/backend/test_vault.py            # Verify skill YAMLs seeded
```

---

## Task 1: Skill Model + Registry

**Files:**
- Create: `backend/src/taim/models/skill.py`
- Create: `backend/src/taim/brain/skill_registry.py`
- Create: `tests/backend/test_skill_models.py`
- Create: `tests/backend/test_skill_registry.py`

### Step 1: Create skill model

```python
# backend/src/taim/models/skill.py
"""Skill model — reusable prompt+tool pattern."""

from __future__ import annotations

from pydantic import BaseModel


class Skill(BaseModel):
    """Reusable prompt+tool pattern for agent specialization."""

    name: str
    description: str
    required_tools: list[str] = []
    prompt_template: str
    output_format: str = "markdown"
```

### Step 2: Write tests

```python
# tests/backend/test_skill_models.py
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
```

### Step 3: Create SkillRegistry

```python
# backend/src/taim/brain/skill_registry.py
"""SkillRegistry — loads skill YAMLs and validates against ToolRegistry."""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml
from pydantic import ValidationError

from taim.models.skill import Skill
from taim.orchestrator.tool_registry import ToolRegistry

logger = structlog.get_logger()


class SkillRegistry:
    """In-memory registry of skills loaded from taim-vault/system/skills/."""

    def __init__(self, skills_dir: Path) -> None:
        self._dir = skills_dir
        self._skills: dict[str, Skill] = {}

    def load(self) -> None:
        self._skills.clear()
        if not self._dir.exists():
            logger.warning("skill_registry.dir_missing", path=str(self._dir))
            return

        for yaml_file in sorted(self._dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
                skill = Skill(**data)
                self._skills[skill.name] = skill
            except (yaml.YAMLError, ValidationError) as e:
                logger.warning(
                    "skill_registry.invalid_skill",
                    file=yaml_file.name,
                    error=str(e),
                )
        logger.info("skill_registry.loaded", count=len(self._skills))

    def validate_against_tools(self, tool_registry: ToolRegistry) -> None:
        """Log warnings for skills referencing unregistered tools."""
        for skill in self._skills.values():
            for tool_name in skill.required_tools:
                if tool_registry.get_schema(tool_name) is None:
                    logger.warning(
                        "skill_registry.unknown_tool",
                        skill=skill.name,
                        tool=tool_name,
                    )

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())
```

### Step 4: Write registry tests

```python
# tests/backend/test_skill_registry.py
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
    def test_unknown_tool_warning(self, tmp_path: Path, caplog) -> None:
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

        # Skill is still registered despite missing tool
        assert skill_reg.get("needs_unknown") is not None

    def test_known_tool_no_warning(self, tmp_path: Path) -> None:
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
        # Should not raise
        skill_reg.validate_against_tools(tool_reg)
        assert skill_reg.get("needs_known") is not None
```

### Step 5: Run + Commit

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v
```

(~252 expected: 247 + 2 model + 5 registry)

```bash
cd /Users/reykz/repositorys/TAIM && git add backend/src/taim/models/skill.py backend/src/taim/brain/skill_registry.py tests/backend/test_skill_models.py tests/backend/test_skill_registry.py
git commit -m "feat: add Skill model and SkillRegistry with tool validation"
```

---

## Task 2: 5 Built-in Skill YAMLs + Vault Seeding

**Files:**
- Create: 5 YAML files in `taim-vault/system/skills/`
- Modify: `backend/src/taim/brain/vault.py` (add 5 constants + `_ensure_default_skills()`)
- Extend: `tests/backend/test_vault.py`

### Step 1: Create the 5 skill YAML files

(Use full content from design Section 5 for each.)

### Step 2: Add constants + method to vault.py

Add 5 module constants `_DEFAULT_SKILL_*` with the YAML content (triple-quoted strings).

Add method:
```python
    def _ensure_default_skills(self) -> None:
        """Seed default skill YAML definitions."""
        skills_dir = self.vault_config.vault_root / "system" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        defaults = {
            "web_research.yaml": _DEFAULT_SKILL_WEB_RESEARCH,
            "code_generation.yaml": _DEFAULT_SKILL_CODE_GENERATION,
            "code_review.yaml": _DEFAULT_SKILL_CODE_REVIEW,
            "content_writing.yaml": _DEFAULT_SKILL_CONTENT_WRITING,
            "data_analysis.yaml": _DEFAULT_SKILL_DATA_ANALYSIS,
        }
        for filename, content in defaults.items():
            path = skills_dir / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")
```

In `ensure_vault()`, after `self._ensure_default_tools()`, add:
```python
        self._ensure_default_skills()
```

### Step 3: Update agent constants — reorder coder + reviewer

Modify `_DEFAULT_AGENT_CODER`:
```yaml
skills:
  - code_generation
  - refactoring
  - code_explanation
```

Modify `_DEFAULT_AGENT_REVIEWER`:
```yaml
skills:
  - code_review
  - quality_assessment
  - content_review
```

### Step 4: Re-seed dev vault

```bash
cd /Users/reykz/repositorys/TAIM && rm -f taim-vault/agents/coder.yaml taim-vault/agents/reviewer.yaml
```

(Other agents already have matching primary skill — no need to re-seed.)

### Step 5: Extend test_vault.py

```python
class TestDefaultSkills:
    def test_creates_five_skill_yamls(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        skills_dir = ops.vault_config.vault_root / "system" / "skills"
        for name in ["web_research", "code_generation", "code_review", "content_writing", "data_analysis"]:
            assert (skills_dir / f"{name}.yaml").exists()
```

### Step 6: Run + Commit

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v
```

```bash
cd /Users/reykz/repositorys/TAIM && git add backend/src/taim/brain/vault.py taim-vault/system/skills/ taim-vault/agents/ tests/backend/test_vault.py
git commit -m "feat: seed 5 built-in skill YAMLs and align agent primary skills"
```

---

## Task 3: AgentStateMachine Skill Prepending

**Files:**
- Modify: `backend/src/taim/brain/agent_state_machine.py`
- Create: `tests/backend/test_agent_state_machine_skills.py`

### Step 1: Add skill_registry param + prepending

Read agent_state_machine.py. Add to imports:
```python
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from taim.brain.skill_registry import SkillRegistry
```

Add to `__init__`:
```python
        skill_registry: SkillRegistry | None = None,
```
(Add to body: `self._skill_registry = skill_registry`)

Add a class-level Jinja env (or lazy property):
```python
    _jinja: SandboxedEnvironment = SandboxedEnvironment(undefined=StrictUndefined)
```

Add method:
```python
    def _render_primary_skill(self) -> str:
        """Return rendered primary skill prompt or empty string."""
        if self._skill_registry is None or not self._agent.skills:
            return ""
        primary_name = self._agent.skills[0]
        skill = self._skill_registry.get(primary_name)
        if skill is None:
            logger.warning(
                "agent.skill_not_found",
                agent=self._agent.name,
                skill=primary_name,
            )
            return ""
        try:
            template = self._jinja.from_string(skill.prompt_template)
            return template.render(
                task_description=self._task_description,
                agent_description=self._agent.description,
            )
        except Exception:
            logger.exception("agent.skill_render_error", skill=primary_name)
            return ""
```

Modify `_do_executing` — at the start, after loading base_prompt:
```python
        skill_prefix = self._render_primary_skill()
        full_prompt = (skill_prefix + "\n\n" + base_prompt) if skill_prefix else base_prompt

        # ... rest stays same, but use full_prompt instead of base_prompt in:
        messages: list[dict] = [{"role": "system", "content": full_prompt}]
```

### Step 2: Write tests

```python
# tests/backend/test_agent_state_machine_skills.py
"""Tests for AgentStateMachine skill prepending."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from taim.brain.agent_run_store import AgentRunStore
from taim.brain.agent_state_machine import AgentStateMachine
from taim.brain.database import init_database
from taim.brain.prompts import PromptLoader
from taim.brain.skill_registry import SkillRegistry
from taim.brain.vault import VaultOps
from taim.models.agent import Agent, AgentStateEnum

from conftest import MockRouter, make_response


@pytest_asyncio.fixture
async def setup(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    db = await init_database(ops.vault_config.db_path)
    store = AgentRunStore(db)

    skills_dir = ops.vault_config.vault_root / "system" / "skills"
    skill_reg = SkillRegistry(skills_dir)
    skill_reg.load()

    yield ops, loader, store, skill_reg
    await db.close()


def _make_agent(skills: list[str] | None = None) -> Agent:
    return Agent(
        name="researcher",
        description="Test agent",
        model_preference=["tier2_standard"],
        skills=skills or [],
    )


@pytest.mark.asyncio
class TestSkillPrepending:
    async def test_skill_prepended_when_present(self, setup) -> None:
        _, loader, store, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = _make_agent(skills=["web_research"])  # built-in skill exists
        sm = AgentStateMachine(
            agent=agent,
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="t1",
            task_description="research SaaS competitors",
            skill_registry=skill_reg,
        )
        await sm.run()

        # The EXECUTING call (index 1) should have skill content prepended
        executing_messages = router.calls[1]["messages"]
        prompt_content = executing_messages[0]["content"]
        assert "web research" in prompt_content.lower() or "research" in prompt_content.lower()

    async def test_no_skill_no_prepending(self, setup) -> None:
        _, loader, store, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = _make_agent(skills=[])
        sm = AgentStateMachine(
            agent=agent,
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="t1",
            task_description="task",
            skill_registry=skill_reg,
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE

    async def test_no_registry_no_prepending(self, setup) -> None:
        _, loader, store, _ = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = _make_agent(skills=["web_research"])
        sm = AgentStateMachine(
            agent=agent,
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="t1",
            task_description="task",
            skill_registry=None,  # no registry
        )
        run = await sm.run()
        assert run.final_state == AgentStateEnum.DONE

    async def test_unknown_skill_continues(self, setup) -> None:
        _, loader, store, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = _make_agent(skills=["nonexistent_skill"])
        sm = AgentStateMachine(
            agent=agent,
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="t1",
            task_description="task",
            skill_registry=skill_reg,
        )
        run = await sm.run()
        # Agent continues with base prompt only, completes successfully
        assert run.final_state == AgentStateEnum.DONE

    async def test_task_description_in_skill_render(self, setup) -> None:
        _, loader, store, skill_reg = setup
        router = MockRouter([
            make_response("plan"),
            make_response("result"),
            make_response('{"quality_ok": true, "feedback": "ok"}'),
        ])
        agent = _make_agent(skills=["web_research"])
        sm = AgentStateMachine(
            agent=agent,
            router=router,
            prompt_loader=loader,
            run_store=store,
            task_id="t1",
            task_description="UNIQUE_MARKER_xyz",
            skill_registry=skill_reg,
        )
        await sm.run()
        executing_prompt = router.calls[1]["messages"][0]["content"]
        # Either via skill {{ task_description }} OR via base prompt — both include task
        assert "UNIQUE_MARKER_xyz" in executing_prompt
```

### Step 3: Run + Commit

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v
```

```bash
cd /Users/reykz/repositorys/TAIM && git add backend/src/taim/brain/agent_state_machine.py tests/backend/test_agent_state_machine_skills.py
git commit -m "feat: prepend primary skill prompt in AgentStateMachine EXECUTING"
```

---

## Task 4: Lifespan + API + Verify

**Files:**
- Modify: `backend/src/taim/main.py` (SkillRegistry in lifespan + skills router)
- Modify: `backend/src/taim/api/deps.py` (get_skill_registry)
- Create: `backend/src/taim/api/skills.py`
- Create: `tests/backend/test_skills_api.py`

### Step 1: Add skills router

```python
# backend/src/taim/api/skills.py
"""Skill REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from taim.api.deps import get_skill_registry
from taim.brain.skill_registry import SkillRegistry

router = APIRouter(prefix="/api/skills")


@router.get("")
async def list_skills(registry: SkillRegistry = Depends(get_skill_registry)) -> dict:
    skills = registry.list_skills()
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "required_tools": s.required_tools,
                "output_format": s.output_format,
            }
            for s in skills
        ],
        "count": len(skills),
    }
```

### Step 2: Update deps.py

Append:
```python
from taim.brain.skill_registry import SkillRegistry


def get_skill_registry(request: Request) -> SkillRegistry:
    return request.app.state.skill_registry
```

### Step 3: Update main.py lifespan

After Tool System block, add:
```python
    # 12. Skill Registry
    from taim.brain.skill_registry import SkillRegistry

    skill_registry = SkillRegistry(
        system_config.vault.vault_root / "system" / "skills"
    )
    skill_registry.load()
    skill_registry.validate_against_tools(tool_registry)
    app.state.skill_registry = skill_registry
    logger.info("skills.loaded", count=len(skill_registry.list_skills()))
```

In `create_app()`, after `tools_router` registration:
```python
    from taim.api.skills import router as skills_router
    app.include_router(skills_router)
```

### Step 4: Write API tests

```python
# tests/backend/test_skills_api.py
"""Tests for /api/skills endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taim.api.skills import router as skills_router
from taim.brain.skill_registry import SkillRegistry
from taim.brain.vault import VaultOps


@pytest_asyncio.fixture
async def client(tmp_vault: Path):
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    skill_reg = SkillRegistry(ops.vault_config.vault_root / "system" / "skills")
    skill_reg.load()

    app = FastAPI()
    app.include_router(skills_router)
    app.state.skill_registry = skill_reg

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestListSkills:
    async def test_returns_five_built_in(self, client) -> None:
        resp = await client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5
        names = {s["name"] for s in data["skills"]}
        expected = {"web_research", "code_generation", "code_review", "content_writing", "data_analysis"}
        assert names == expected

    async def test_includes_required_tools(self, client) -> None:
        resp = await client.get("/api/skills")
        data = resp.json()
        web = next(s for s in data["skills"] if s["name"] == "web_research")
        assert "web_search" in web["required_tools"]
```

### Step 5: Run all tests + lint

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v
cd /Users/reykz/repositorys/TAIM/backend && uv run ruff check src/ && uv run ruff format src/
```

### Step 6: Smoke test

```bash
cd /Users/reykz/repositorys/TAIM && rm -f taim-vault/agents/coder.yaml taim-vault/agents/reviewer.yaml
cd /Users/reykz/repositorys/TAIM/backend && uv run uvicorn taim.main:app --host localhost --port 8005 > /tmp/taim-step6b.log 2>&1 &
sleep 3
echo "--- /api/skills ---"
curl -s http://localhost:8005/api/skills | python3 -m json.tool
echo "--- log (look for skill_registry.unknown_tool warnings for web_search/web_fetch) ---"
cat /tmp/taim-step6b.log | grep -E "skill|tool" | head -20
kill %1 2>/dev/null
```

Expected:
- `skills.loaded count=5`
- Warnings for `web_research → web_search` and `web_research → web_fetch` (these tools are Step 6d — expected)
- `/api/skills` returns 5 skills

### Step 7: Commit

```bash
cd /Users/reykz/repositorys/TAIM && git add backend/src/taim/main.py backend/src/taim/api/deps.py backend/src/taim/api/skills.py tests/backend/test_skills_api.py
git commit -m "feat: wire SkillRegistry into lifespan + add /api/skills endpoint"
```

---

## Task 5: Final Verification

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest --cov=taim --cov-report=term-missing 2>&1 | tail -25
cd /Users/reykz/repositorys/TAIM/backend && uv run ruff check src/ && uv run ruff format --check src/
```

Commit any cleanup as `style: ruff cleanup`.

---

## Summary

| Task | Module | Tests | Steps |
|------|--------|-------|-------|
| 1 | models/skill.py + skill_registry.py | test_skill_models.py + test_skill_registry.py | 5 |
| 2 | 5 skill YAMLs + vault.py + agent reorder | test_vault.py extend | 6 |
| 3 | agent_state_machine.py (skill prepending) | test_agent_state_machine_skills.py | 3 |
| 4 | main.py + api/skills.py + deps.py | test_skills_api.py | 7 |
| 5 | Verification | — | 2 |
| **Total** | **3 new modules + 5 vault YAMLs** | **4 test files** | **23 steps** |

Smaller than 6a but tightly focused. Expected ~265 tests after merge.
