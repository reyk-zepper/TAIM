# Step 3: Intent Interpreter — Implementation Plan

> **For agentic workers:** Follow superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the Intent Interpreter — two-stage NL→structured-command pipeline with optional memory and orchestrator dependencies.

**Architecture:** Stage 1 (Tier 3 classify, 7 categories, 0.80 confidence threshold) → Stage 2 (Tier 2 deep extract, JSON output) OR direct handler (status/stop/confirmation). Design: `docs/plans/2026-04-13-step3-intent-interpreter-design.md`.

**Tech Stack:** Python 3.11+, FastAPI WebSocket, LiteLLM via Step 2 Router, Jinja2 prompts via Step 1 PromptLoader.

---

## File Structure

### Files to Create
```
backend/src/taim/models/chat.py
backend/src/taim/conversation/classifier.py
backend/src/taim/conversation/understander.py
backend/src/taim/conversation/handlers.py
backend/src/taim/conversation/interpreter.py
taim-vault/system/prompts/intent-classifier.yaml
taim-vault/system/prompts/intent-interpreter.yaml
tests/backend/test_chat_models.py
tests/backend/test_classifier.py
tests/backend/test_understander.py
tests/backend/test_handlers.py
tests/backend/test_interpreter.py
tests/backend/test_chat_websocket.py
```

### Files to Modify
```
backend/src/taim/api/chat.py            # Replace stub with real handler
backend/src/taim/main.py                # Add IntentInterpreter to lifespan
backend/src/taim/conversation/__init__.py # Public exports
backend/src/taim/brain/vault.py         # Add _ensure_default_prompts()
tests/backend/conftest.py               # Add MockRouter
```

---

## Task 1: Chat Models

**Files:** `backend/src/taim/models/chat.py`, `tests/backend/test_chat_models.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/backend/test_chat_models.py
"""Tests for chat/intent data models."""

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
        import pytest
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
```

- [ ] **Step 2: Run → expect FAIL**

`cd /Users/reykz/repositorys/TAIM/backend && uv run pytest ../tests/backend/test_chat_models.py -v`

- [ ] **Step 3: Implement models/chat.py**

```python
"""Data models for chat / intent interpretation."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    NEW_TASK = "new_task"
    CONFIRMATION = "confirmation"
    FOLLOW_UP = "follow_up"
    STATUS_QUERY = "status_query"
    CONFIGURATION = "configuration"
    STOP_COMMAND = "stop_command"
    ONBOARDING_RESPONSE = "onboarding_response"


class IntentClassification(BaseModel):
    """Stage 1 output."""
    category: IntentCategory
    confidence: float = Field(ge=0.0, le=1.0)
    needs_deep_analysis: bool = False


class TaskConstraints(BaseModel):
    """Constraints parsed from a Stage 2 user message."""
    time_limit_seconds: int | None = None
    budget_eur: float | None = None
    specific_agents: list[str] = []
    model_tier_override: str | None = None


class IntentResult(BaseModel):
    """Stage 2 output — structured task command."""
    task_type: str
    objective: str
    parameters: dict[str, str | int | float | bool] = {}
    constraints: TaskConstraints = TaskConstraints()
    missing_info: list[str] = []
    suggested_team: list[str] = []


class InterpreterResult(BaseModel):
    """Final output of IntentInterpreter."""
    classification: IntentClassification
    intent: IntentResult | None = None
    direct_response: str | None = None
    needs_followup: bool = False
    followup_question: str | None = None
```

- [ ] **Step 4: Run → PASS** (5+ tests)
- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/models/chat.py tests/backend/test_chat_models.py
git commit -m "feat: add chat/intent data models for Step 3"
```

---

## Task 2: Prompt YAMLs + VaultOps Update

**Files:**
- Create: `taim-vault/system/prompts/intent-classifier.yaml`
- Create: `taim-vault/system/prompts/intent-interpreter.yaml`
- Modify: `backend/src/taim/brain/vault.py` (add `_ensure_default_prompts`)

- [ ] **Step 1: Create intent-classifier.yaml**

```yaml
name: intent-classifier
version: 1
description: "Stage 1 — classify user message into intent category"
model_tier: tier3_economy
variables:
  - user_message
  - recent_context
template: |
  You are tAIm's intent classifier. Classify the user's message into ONE category.

  Recent context (last few messages):
  {{ recent_context }}

  User message: "{{ user_message }}"

  Categories:
  - new_task: User wants to start a new task or project
  - confirmation: User confirms or approves something ("yes", "go ahead", "do it")
  - follow_up: User adds to or modifies an existing task
  - status_query: User asks about current status ("what's happening?", "status?")
  - configuration: User wants to change settings or preferences
  - stop_command: User wants to stop ("stop", "cancel", "halt")
  - onboarding_response: User answers an onboarding question

  Respond with JSON only, no markdown:
  {
    "category": "<one of the categories above>",
    "confidence": <0.0 to 1.0>,
    "needs_deep_analysis": <true if message is complex/ambiguous, false if clear>
  }
```

- [ ] **Step 2: Create intent-interpreter.yaml**

```yaml
name: intent-interpreter
version: 1
description: "Stage 2 — extract structured task command from user message"
model_tier: tier2_standard
variables:
  - user_message
  - recent_context
  - user_preferences
template: |
  You are tAIm's intent interpreter. Extract a structured task command from the user's message.

  User preferences (from memory):
  {{ user_preferences }}

  Recent context:
  {{ recent_context }}

  User message: "{{ user_message }}"

  Extract:
  - task_type: short label (e.g., "research", "code_review", "content_creation")
  - objective: one-sentence description of what the user wants achieved
  - parameters: dict of specific values (URLs, names, file paths) mentioned
  - constraints: time/budget limits if mentioned
  - missing_info: list of critical info NOT in the message but needed
  - suggested_team: optional list of agent role names that fit the task

  If anything critical is missing, include it in missing_info — do NOT guess.

  Respond with JSON only, no markdown:
  {
    "task_type": "<string>",
    "objective": "<string>",
    "parameters": {},
    "constraints": {
      "time_limit_seconds": null,
      "budget_eur": null
    },
    "missing_info": [],
    "suggested_team": []
  }
```

- [ ] **Step 3: Update VaultOps to ensure default prompts**

In `backend/src/taim/brain/vault.py`, add at the bottom of the constants:

```python
_DEFAULT_INTENT_CLASSIFIER_PROMPT = """\
<full content of intent-classifier.yaml above>
"""

_DEFAULT_INTENT_INTERPRETER_PROMPT = """\
<full content of intent-interpreter.yaml above>
"""
```

In `ensure_vault()`, after `self._ensure_default_configs()`, add:
```python
        self._ensure_default_prompts()
```

Add new method:
```python
    def _ensure_default_prompts(self) -> None:
        """Write default prompt YAML files only if they don't exist."""
        defaults = {
            "intent-classifier.yaml": _DEFAULT_INTENT_CLASSIFIER_PROMPT,
            "intent-interpreter.yaml": _DEFAULT_INTENT_INTERPRETER_PROMPT,
        }
        for filename, content in defaults.items():
            path = self.vault_config.prompts_dir / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")
```

- [ ] **Step 4: Add test for _ensure_default_prompts**

Append to `tests/backend/test_vault.py`:
```python
class TestDefaultPrompts:
    def test_creates_intent_prompts(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        assert (ops.vault_config.prompts_dir / "intent-classifier.yaml").exists()
        assert (ops.vault_config.prompts_dir / "intent-interpreter.yaml").exists()

    def test_does_not_overwrite_existing_prompts(self, tmp_path: Path) -> None:
        ops = VaultOps(tmp_path / "vault")
        ops.ensure_vault()
        prompt_path = ops.vault_config.prompts_dir / "intent-classifier.yaml"
        prompt_path.write_text("custom: true\n")
        ops.ensure_vault()
        assert prompt_path.read_text() == "custom: true\n"
```

- [ ] **Step 5: Run tests + verify prompts load via PromptLoader**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest ../tests/backend/test_vault.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/taim/brain/vault.py tests/backend/test_vault.py taim-vault/system/prompts/
git commit -m "feat: add default intent prompts and VaultOps prompt seeding"
```

---

## Task 3: MockRouter Fixture

**Files:** Modify `tests/backend/conftest.py`

- [ ] **Step 1: Append MockRouter to conftest.py**

```python
class MockRouter:
    """Test router that returns canned responses for interpreter tests."""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def make_classification_response(category: str, confidence: float = 0.95, needs_deep: bool = False) -> LLMResponse:
    """Build an LLMResponse with a JSON classification body."""
    import json
    body = json.dumps({
        "category": category,
        "confidence": confidence,
        "needs_deep_analysis": needs_deep,
    })
    return make_response(content=body)


def make_intent_response(
    task_type: str = "research",
    objective: str = "Find competitors",
    missing_info: list[str] | None = None,
) -> LLMResponse:
    """Build an LLMResponse with a JSON intent body."""
    import json
    body = json.dumps({
        "task_type": task_type,
        "objective": objective,
        "parameters": {},
        "constraints": {"time_limit_seconds": None, "budget_eur": None},
        "missing_info": missing_info or [],
        "suggested_team": [],
    })
    return make_response(content=body)
```

- [ ] **Step 2: Verify imports** — run: `cd backend && uv run pytest -q` (should still pass 108)

- [ ] **Step 3: Commit (with the next task — these are test-only helpers)**

---

## Task 4: Stage 1 Classifier

**Files:** `backend/src/taim/conversation/classifier.py`, `tests/backend/test_classifier.py`

- [ ] **Step 1: Write tests**

```python
# tests/backend/test_classifier.py
"""Tests for Stage 1 — quick intent classification."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.conversation.classifier import CONFIDENCE_THRESHOLD, classify_intent
from taim.models.chat import IntentCategory

from conftest import MockRouter, make_classification_response


@pytest.fixture
def loader(tmp_vault: Path) -> PromptLoader:
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    return PromptLoader(ops.vault_config.prompts_dir)


@pytest.mark.asyncio
class TestClassifyIntent:
    async def test_returns_classification(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("new_task", 0.9)])
        result = await classify_intent(
            message="Build me a competitive analysis",
            recent_context="",
            router=router,
            prompt_loader=loader,
        )
        assert result.category == IntentCategory.NEW_TASK
        assert result.confidence == 0.9

    async def test_uses_tier3(self, loader: PromptLoader) -> None:
        from taim.models.router import ModelTierEnum
        router = MockRouter([make_classification_response("confirmation")])
        await classify_intent(message="yes", recent_context="", router=router, prompt_loader=loader)
        assert router.calls[0]["tier"] == ModelTierEnum.TIER3_ECONOMY

    async def test_requests_json_format(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("status_query")])
        await classify_intent(message="status?", recent_context="", router=router, prompt_loader=loader)
        assert router.calls[0]["expected_format"] == "json"

    async def test_passes_session_id(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("stop_command")])
        await classify_intent(message="stop", recent_context="", router=router, prompt_loader=loader, session_id="sess-1")
        assert router.calls[0]["session_id"] == "sess-1"


def test_threshold_constant() -> None:
    assert CONFIDENCE_THRESHOLD == 0.80
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement classifier.py**

```python
"""Stage 1 — quick intent classification using Tier 3 model."""

from __future__ import annotations

import json

from taim.brain.prompts import PromptLoader
from taim.models.chat import IntentCategory, IntentClassification
from taim.models.router import ModelTierEnum

CONFIDENCE_THRESHOLD = 0.80


async def classify_intent(
    message: str,
    recent_context: str,
    router,
    prompt_loader: PromptLoader,
    session_id: str | None = None,
) -> IntentClassification:
    """Stage 1: Quick classification using Tier 3 model."""
    prompt = prompt_loader.load(
        "intent-classifier",
        {"user_message": message, "recent_context": recent_context or "(none)"},
    )
    response = await router.complete(
        messages=[{"role": "system", "content": prompt}],
        tier=ModelTierEnum.TIER3_ECONOMY,
        expected_format="json",
        session_id=session_id,
    )
    data = json.loads(response.content)
    return IntentClassification(
        category=IntentCategory(data["category"]),
        confidence=float(data["confidence"]),
        needs_deep_analysis=bool(data.get("needs_deep_analysis", False)),
    )
```

- [ ] **Step 4: Run → PASS** (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/conversation/classifier.py tests/backend/test_classifier.py tests/backend/conftest.py
git commit -m "feat: add Stage 1 intent classifier with confidence threshold constant"
```

---

## Task 5: Stage 2 Understander

**Files:** `backend/src/taim/conversation/understander.py`, `tests/backend/test_understander.py`

- [ ] **Step 1: Write tests**

```python
# tests/backend/test_understander.py
"""Tests for Stage 2 — deep task understanding."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.conversation.understander import understand_task

from conftest import MockRouter, make_intent_response


@pytest.fixture
def loader(tmp_vault: Path) -> PromptLoader:
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    return PromptLoader(ops.vault_config.prompts_dir)


@pytest.mark.asyncio
class TestUnderstandTask:
    async def test_returns_intent_result(self, loader: PromptLoader) -> None:
        router = MockRouter([make_intent_response("research", "Find SaaS competitors")])
        result = await understand_task(
            message="Research B2B SaaS competitors",
            recent_context="",
            router=router,
            prompt_loader=loader,
        )
        assert result.task_type == "research"
        assert result.objective == "Find SaaS competitors"

    async def test_uses_tier2(self, loader: PromptLoader) -> None:
        from taim.models.router import ModelTierEnum
        router = MockRouter([make_intent_response()])
        await understand_task(message="x", recent_context="", router=router, prompt_loader=loader)
        assert router.calls[0]["tier"] == ModelTierEnum.TIER2_STANDARD

    async def test_includes_user_preferences(self, loader: PromptLoader) -> None:
        router = MockRouter([make_intent_response()])
        await understand_task(
            message="x",
            recent_context="",
            router=router,
            prompt_loader=loader,
            user_preferences="prefers concise outputs",
        )
        # The prompt is sent in messages[0]["content"] — verify preferences are embedded
        assert "prefers concise outputs" in router.calls[0]["messages"][0]["content"]

    async def test_handles_empty_preferences(self, loader: PromptLoader) -> None:
        router = MockRouter([make_intent_response()])
        await understand_task(message="x", recent_context="", router=router, prompt_loader=loader, user_preferences="")
        assert "no preferences yet" in router.calls[0]["messages"][0]["content"]

    async def test_extracts_missing_info(self, loader: PromptLoader) -> None:
        router = MockRouter([make_intent_response(missing_info=["timeline", "budget"])])
        result = await understand_task(message="x", recent_context="", router=router, prompt_loader=loader)
        assert result.missing_info == ["timeline", "budget"]
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement understander.py**

```python
"""Stage 2 — deep task understanding using Tier 2 model."""

from __future__ import annotations

import json

from taim.brain.prompts import PromptLoader
from taim.models.chat import IntentResult, TaskConstraints
from taim.models.router import ModelTierEnum


async def understand_task(
    message: str,
    recent_context: str,
    router,
    prompt_loader: PromptLoader,
    user_preferences: str = "",
    session_id: str | None = None,
) -> IntentResult:
    """Stage 2: Deep task extraction using Tier 2 model."""
    prompt = prompt_loader.load(
        "intent-interpreter",
        {
            "user_message": message,
            "recent_context": recent_context or "(none)",
            "user_preferences": user_preferences or "(no preferences yet)",
        },
    )
    response = await router.complete(
        messages=[{"role": "system", "content": prompt}],
        tier=ModelTierEnum.TIER2_STANDARD,
        expected_format="json",
        session_id=session_id,
    )
    data = json.loads(response.content)
    return IntentResult(
        task_type=data["task_type"],
        objective=data["objective"],
        parameters=data.get("parameters", {}),
        constraints=TaskConstraints(**data.get("constraints", {})),
        missing_info=data.get("missing_info", []),
        suggested_team=data.get("suggested_team", []),
    )
```

- [ ] **Step 4: Run → PASS** (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/conversation/understander.py tests/backend/test_understander.py
git commit -m "feat: add Stage 2 intent understander with user preferences support"
```

---

## Task 6: Direct Handlers

**Files:** `backend/src/taim/conversation/handlers.py`, `tests/backend/test_handlers.py`

- [ ] **Step 1: Write tests**

```python
# tests/backend/test_handlers.py
"""Tests for direct intent handlers (status, stop)."""

from __future__ import annotations

import pytest

from taim.conversation.handlers import handle_status, handle_stop


@pytest.mark.asyncio
class TestHandleStatus:
    async def test_no_orchestrator_returns_placeholder(self) -> None:
        result = await handle_status(session_id="s1", orchestrator=None)
        assert "no active team" in result.lower()

    async def test_with_orchestrator_no_team(self) -> None:
        class StubOrch:
            async def get_status(self, session_id: str):
                from types import SimpleNamespace
                return SimpleNamespace(has_team=False)
        result = await handle_status(session_id="s1", orchestrator=StubOrch())
        assert "no active team" in result.lower()

    async def test_with_orchestrator_active_team(self) -> None:
        from types import SimpleNamespace
        class StubOrch:
            async def get_status(self, session_id: str):
                return SimpleNamespace(
                    has_team=True,
                    team_name="ResearchTeam",
                    agents=[SimpleNamespace(name="Researcher", state="EXECUTING", iteration=2)],
                    tokens_total=1500,
                    cost_eur=0.05,
                )
        result = await handle_status(session_id="s1", orchestrator=StubOrch())
        assert "ResearchTeam" in result
        assert "EXECUTING" in result
        assert "0.05" in result


@pytest.mark.asyncio
class TestHandleStop:
    async def test_no_orchestrator_returns_placeholder(self) -> None:
        result = await handle_stop(session_id="s1", orchestrator=None)
        assert "no active team" in result.lower() or "no team" in result.lower()

    async def test_with_orchestrator_stops_and_summarizes(self) -> None:
        class StubOrch:
            async def stop_team(self, session_id: str):
                return "Researcher completed 2 iterations"
        result = await handle_stop(session_id="s1", orchestrator=StubOrch())
        assert "stopped" in result.lower()
        assert "Researcher completed 2 iterations" in result
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement handlers.py**

```python
"""Direct intent handlers — no LLM calls."""

from __future__ import annotations

from typing import Protocol


class Orchestrator(Protocol):
    """Protocol for orchestrator dependency. Real implementation in Step 7."""

    async def get_status(self, session_id: str): ...
    async def stop_team(self, session_id: str) -> str: ...


async def handle_status(
    session_id: str,
    orchestrator: Orchestrator | None = None,
) -> str:
    """Status query — formatted text response, no LLM call."""
    if orchestrator is None:
        return "There's no active team right now."

    status = await orchestrator.get_status(session_id)
    if not status.has_team:
        return "There's no active team right now."

    lines = [f"Team status: {status.team_name}"]
    for agent in status.agents:
        lines.append(f"  • {agent.name}: {agent.state} (iteration {agent.iteration})")
    lines.append(f"Tokens used: {status.tokens_total}")
    lines.append(f"Cost so far: €{status.cost_eur:.4f}")
    return "\n".join(lines)


async def handle_stop(
    session_id: str,
    orchestrator: Orchestrator | None = None,
) -> str:
    """Stop command — triggers graceful stop on orchestrator."""
    if orchestrator is None:
        return "There's no active team to stop."

    summary = await orchestrator.stop_team(session_id)
    return f"Team stopped. Here's what was completed: {summary}"
```

- [ ] **Step 4: Run → PASS** (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/conversation/handlers.py tests/backend/test_handlers.py
git commit -m "feat: add status and stop handlers with optional orchestrator"
```

---

## Task 7: IntentInterpreter (Main Orchestrator)

**Files:** `backend/src/taim/conversation/interpreter.py`, `tests/backend/test_interpreter.py`

- [ ] **Step 1: Write tests**

```python
# tests/backend/test_interpreter.py
"""Tests for IntentInterpreter — full two-stage flow."""

from __future__ import annotations

from pathlib import Path

import pytest

from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.conversation.interpreter import IntentInterpreter
from taim.models.chat import IntentCategory

from conftest import MockRouter, make_classification_response, make_intent_response


@pytest.fixture
def loader(tmp_vault: Path) -> PromptLoader:
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    return PromptLoader(ops.vault_config.prompts_dir)


@pytest.mark.asyncio
class TestDirectCategories:
    async def test_status_query_no_stage2(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("status_query", 0.95)])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="status?", session_id="s1")
        assert result.classification.category == IntentCategory.STATUS_QUERY
        assert result.intent is None
        assert result.direct_response is not None
        assert len(router.calls) == 1  # Only Stage 1

    async def test_stop_command_no_stage2(self, loader: PromptLoader) -> None:
        router = MockRouter([make_classification_response("stop_command", 0.92)])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="stop", session_id="s1")
        assert result.intent is None
        assert "no active team" in result.direct_response.lower()


@pytest.mark.asyncio
class TestStage2Invocation:
    async def test_new_task_invokes_stage2(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("new_task", 0.95),
            make_intent_response("research", "Find SaaS competitors"),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="Research SaaS competitors", session_id="s1")
        assert result.intent is not None
        assert result.intent.task_type == "research"
        assert len(router.calls) == 2  # Stage 1 + Stage 2

    async def test_low_confidence_escalates(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("confirmation", 0.5),  # Low confidence
            make_intent_response("clarification", "Unclear request"),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="maybe yes do it", session_id="s1")
        assert result.intent is not None  # Stage 2 was invoked despite "confirmation"
        assert len(router.calls) == 2

    async def test_needs_deep_analysis_flag_escalates(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("status_query", 0.95, needs_deep=True),
            make_intent_response(),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="how is the third agent doing on iteration 4?", session_id="s1")
        assert result.intent is not None
        assert len(router.calls) == 2


@pytest.mark.asyncio
class TestFollowup:
    async def test_missing_info_creates_followup(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("new_task", 0.95),
            make_intent_response(missing_info=["target audience"]),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="Write some content", session_id="s1")
        assert result.needs_followup is True
        assert "target audience" in result.followup_question

    async def test_no_missing_info_no_followup(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("new_task", 0.95),
            make_intent_response(missing_info=[]),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader)
        result = await interpreter.interpret(message="Research X with €50 budget by tomorrow", session_id="s1")
        assert result.needs_followup is False


@pytest.mark.asyncio
class TestMemoryIntegration:
    async def test_loads_preferences_when_memory_provided(self, loader: PromptLoader) -> None:
        class StubMemory:
            async def get_preferences_text(self) -> str:
                return "User prefers concise outputs"

        router = MockRouter([
            make_classification_response("new_task", 0.95),
            make_intent_response(),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader, memory=StubMemory())
        await interpreter.interpret(message="x", session_id="s1")
        # Stage 2 prompt should include the preference
        stage2_prompt = router.calls[1]["messages"][0]["content"]
        assert "User prefers concise outputs" in stage2_prompt

    async def test_no_memory_uses_placeholder(self, loader: PromptLoader) -> None:
        router = MockRouter([
            make_classification_response("new_task", 0.95),
            make_intent_response(),
        ])
        interpreter = IntentInterpreter(router=router, prompt_loader=loader, memory=None)
        await interpreter.interpret(message="x", session_id="s1")
        stage2_prompt = router.calls[1]["messages"][0]["content"]
        assert "no preferences yet" in stage2_prompt
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement interpreter.py**

```python
"""IntentInterpreter — orchestrates Stage 1, Stage 2, and direct handlers."""

from __future__ import annotations

from typing import Protocol

from taim.brain.prompts import PromptLoader
from taim.conversation.classifier import CONFIDENCE_THRESHOLD, classify_intent
from taim.conversation.handlers import Orchestrator, handle_status, handle_stop
from taim.conversation.understander import understand_task
from taim.models.chat import IntentCategory, InterpreterResult, IntentResult


class MemoryReader(Protocol):
    """Protocol for memory dependency. Real implementation in Step 4."""

    async def get_preferences_text(self) -> str: ...


_DIRECT_CATEGORIES = {
    IntentCategory.STATUS_QUERY,
    IntentCategory.STOP_COMMAND,
    IntentCategory.CONFIRMATION,
    IntentCategory.ONBOARDING_RESPONSE,
}


class IntentInterpreter:
    def __init__(
        self,
        router,
        prompt_loader: PromptLoader,
        memory: MemoryReader | None = None,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        self._router = router
        self._prompts = prompt_loader
        self._memory = memory
        self._orchestrator = orchestrator

    async def interpret(
        self,
        message: str,
        session_id: str,
        recent_context: list[dict] | None = None,
    ) -> InterpreterResult:
        """Run a message through the two-stage interpreter."""
        context_str = self._format_context(recent_context or [])

        # Stage 1
        classification = await classify_intent(
            message=message,
            recent_context=context_str,
            router=self._router,
            prompt_loader=self._prompts,
            session_id=session_id,
        )

        # Direct handlers (high confidence + bypass category + not flagged for deep analysis)
        if (
            classification.confidence >= CONFIDENCE_THRESHOLD
            and not classification.needs_deep_analysis
            and classification.category in _DIRECT_CATEGORIES
        ):
            response = await self._handle_direct(classification.category, session_id)
            return InterpreterResult(
                classification=classification,
                direct_response=response,
            )

        # Stage 2 (escalation or complex category)
        user_prefs = await self._load_preferences()
        intent = await understand_task(
            message=message,
            recent_context=context_str,
            router=self._router,
            prompt_loader=self._prompts,
            user_preferences=user_prefs,
            session_id=session_id,
        )

        result = InterpreterResult(classification=classification, intent=intent)
        if intent.missing_info:
            result.needs_followup = True
            result.followup_question = self._build_followup(intent.missing_info)
        return result

    async def _handle_direct(self, category: IntentCategory, session_id: str) -> str:
        if category == IntentCategory.STATUS_QUERY:
            return await handle_status(session_id, self._orchestrator)
        if category == IntentCategory.STOP_COMMAND:
            return await handle_stop(session_id, self._orchestrator)
        if category == IntentCategory.CONFIRMATION:
            return "Got it. Proceeding."
        if category == IntentCategory.ONBOARDING_RESPONSE:
            return "Thanks. Continuing setup."
        return "OK."

    async def _load_preferences(self) -> str:
        if self._memory is None:
            return ""
        return await self._memory.get_preferences_text()

    def _format_context(self, recent: list[dict]) -> str:
        if not recent:
            return "(no recent messages)"
        return "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent[-5:]
        )

    def _build_followup(self, missing: list[str]) -> str:
        if len(missing) == 1:
            return f"To proceed, I need to know: {missing[0]}"
        return f"To proceed, I need a few details: {', '.join(missing[:3])}"
```

- [ ] **Step 4: Run → PASS** (8 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/taim/conversation/interpreter.py tests/backend/test_interpreter.py
git commit -m "feat: add IntentInterpreter orchestrating Stage 1, Stage 2, and handlers"
```

---

## Task 8: WebSocket Integration + Main App

**Files:**
- Modify: `backend/src/taim/api/chat.py` (replace stub)
- Modify: `backend/src/taim/main.py` (add interpreter to lifespan)
- Modify: `backend/src/taim/conversation/__init__.py` (exports)
- Create: `tests/backend/test_chat_websocket.py`

- [ ] **Step 1: Update conversation/__init__.py**

```python
"""tAIm Conversation Layer — Intent Interpretation."""

from taim.conversation.interpreter import IntentInterpreter, MemoryReader
from taim.conversation.handlers import Orchestrator

__all__ = ["IntentInterpreter", "MemoryReader", "Orchestrator"]
```

- [ ] **Step 2: Replace api/chat.py**

```python
"""WebSocket chat endpoint — wired to IntentInterpreter."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from taim.conversation import IntentInterpreter
from taim.models.chat import IntentResult

logger = structlog.get_logger()
router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """Receive user messages, run through interpreter, send back responses."""
    await websocket.accept()
    interpreter: IntentInterpreter = websocket.app.state.interpreter

    history: list[dict] = []  # In-memory per-session, formalized in Step 4

    try:
        while True:
            data = await websocket.receive_json()
            user_message = (data.get("content") or "").strip()
            if not user_message:
                continue

            history.append({"role": "user", "content": user_message})
            await websocket.send_json({"type": "thinking", "session_id": session_id})

            try:
                result = await interpreter.interpret(
                    message=user_message,
                    session_id=session_id,
                    recent_context=history[:-1],
                )
            except Exception:
                logger.exception("interpreter.error", session=session_id)
                await websocket.send_json({
                    "type": "error",
                    "content": "I had trouble understanding that. Could you rephrase?",
                    "session_id": session_id,
                })
                continue

            response_text = (
                result.direct_response
                or result.followup_question
                or _summarize(result.intent)
            )
            history.append({"role": "assistant", "content": response_text})

            await websocket.send_json({
                "type": "system" if result.direct_response else "intent",
                "content": response_text,
                "category": result.classification.category.value,
                "confidence": result.classification.confidence,
                "intent": result.intent.model_dump() if result.intent else None,
                "session_id": session_id,
            })
    except WebSocketDisconnect:
        pass


def _summarize(intent: IntentResult | None) -> str:
    if intent is None:
        return "Got it."
    return f"I understood: {intent.objective}"
```

- [ ] **Step 3: Update main.py lifespan**

In `main.py`, after `llm_router = LLMRouter(...)`, add:

```python
    # 8. Intent Interpreter
    from taim.conversation import IntentInterpreter
    interpreter = IntentInterpreter(
        router=llm_router,
        prompt_loader=prompt_loader,
        memory=None,        # Step 4 will inject
        orchestrator=None,  # Step 7 will inject
    )
    app.state.interpreter = interpreter
```

And add `get_interpreter()` to `api/deps.py`:
```python
from taim.conversation import IntentInterpreter

def get_interpreter(request: Request) -> IntentInterpreter:
    return request.app.state.interpreter
```

- [ ] **Step 4: Write WebSocket integration test**

```python
# tests/backend/test_chat_websocket.py
"""Integration tests for the chat WebSocket."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from taim.api.chat import router as chat_router
from taim.brain.prompts import PromptLoader
from taim.brain.vault import VaultOps
from taim.conversation import IntentInterpreter

from conftest import MockRouter, make_classification_response, make_intent_response


@pytest.fixture
def app(tmp_vault: Path) -> FastAPI:
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)

    router = MockRouter([
        make_classification_response("status_query", 0.95),
    ])
    interpreter = IntentInterpreter(router=router, prompt_loader=loader)

    app = FastAPI()
    app.include_router(chat_router)
    app.state.interpreter = interpreter
    return app


def test_websocket_status_query(app: FastAPI) -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws/sess-1") as ws:
        ws.send_json({"content": "status?"})
        thinking = ws.receive_json()
        assert thinking["type"] == "thinking"
        response = ws.receive_json()
        assert response["type"] == "system"
        assert "no active team" in response["content"].lower()
        assert response["category"] == "status_query"


def test_websocket_empty_message_ignored(app: FastAPI, tmp_vault: Path) -> None:
    """Empty content should not trigger an interpret call."""
    # Build a fresh app where the router has zero responses (would fail if called)
    ops = VaultOps(tmp_vault)
    ops.ensure_vault()
    loader = PromptLoader(ops.vault_config.prompts_dir)
    router = MockRouter([])  # Will raise IndexError if called
    interpreter = IntentInterpreter(router=router, prompt_loader=loader)
    app2 = FastAPI()
    app2.include_router(chat_router)
    app2.state.interpreter = interpreter

    client = TestClient(app2)
    with client.websocket_connect("/ws/sess-1") as ws:
        ws.send_json({"content": ""})
        # Send a real message after empty one
        # If the empty was processed, MockRouter would have raised
        ws.send_json({"content": ""})
```

- [ ] **Step 5: Run all tests + lint**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest -v
cd /Users/reykz/repositorys/TAIM/backend && uv run ruff check src/ && uv run ruff format src/
```

- [ ] **Step 6: Manual server start test**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run uvicorn taim.main:app --host localhost --port 8000 &
sleep 3
curl -s http://localhost:8000/health
kill %1
```

- [ ] **Step 7: Commit**

```bash
git add backend/src/taim/api/chat.py backend/src/taim/main.py backend/src/taim/api/deps.py backend/src/taim/conversation/__init__.py tests/backend/test_chat_websocket.py
git commit -m "feat: wire IntentInterpreter into FastAPI lifespan and WebSocket"
```

---

## Task 9: Final Verification

- [ ] **Step 1: Coverage check**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run pytest --cov=taim --cov-report=term-missing
```

Expected: ≥80% on conversation/, models/chat.py.

- [ ] **Step 2: Lint clean**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run ruff check src/ && uv run ruff format --check src/
```

- [ ] **Step 3: Manual smoke test**

```bash
cd /Users/reykz/repositorys/TAIM/backend && uv run uvicorn taim.main:app --host localhost --port 8000
# Then in browser console or wscat:
# Connect to ws://localhost:8000/ws/test-1
# Send: {"content": "what's happening?"}
# Expect: thinking event, then system response with "no active team"
```

(For automated test: this is covered by test_chat_websocket.py.)

- [ ] **Step 4: Commit any fixes**

---

## Summary

| Task | Module | Tests | Steps |
|------|--------|-------|-------|
| 1 | models/chat.py | test_chat_models.py | 5 |
| 2 | Prompt YAMLs + VaultOps | test_vault.py (extend) | 6 |
| 3 | MockRouter fixture | conftest.py (extend) | 3 |
| 4 | classifier.py | test_classifier.py | 5 |
| 5 | understander.py | test_understander.py | 5 |
| 6 | handlers.py | test_handlers.py | 5 |
| 7 | interpreter.py | test_interpreter.py | 5 |
| 8 | api/chat.py + main.py | test_chat_websocket.py | 7 |
| 9 | Verification | — | 4 |
| **Total** | **8 new files** | **6 test files** | **45 steps** |

Parallelizable: Tasks 4+5+6 (classifier, understander, handlers) are independent after Task 3.
