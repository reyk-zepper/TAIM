# Step 3: Intent Interpreter — Implementation Design

> Version: 1.0
> Date: 2026-04-13
> Status: Reviewed — critical review applied
> Scope: US-2.1, US-2.2, US-2.3, US-2.4

---

## 1. Overview

Step 3 builds the **Intent Interpreter** — the gateway from natural language to structured commands. Every chat message flows through this layer.

**Architecture: Two-Stage Interpretation (AD-2)**

```
User message
    ↓
Stage 1: Quick Classification (Tier 3, ~50-100 tokens)
    ↓
    ├─ confidence < 0.80 → Stage 2 (escalation)
    ├─ status_query, stop_command, confirmation, onboarding_response → Direct handler
    ├─ needs_deep_analysis = true → Stage 2
    └─ new_task, configuration, follow_up → Stage 2
    ↓
Stage 2: Deep Understanding (Tier 2, JSON output)
    ↓
IntentResult (passed to Orchestrator in Step 7)
```

**Deliverables:**
1. `models/chat.py` — IntentCategory, IntentClassification, IntentResult, TaskConstraints, InterpreterResult
2. `conversation/classifier.py` — Stage 1 (cheap classify)
3. `conversation/understander.py` — Stage 2 (deep extract)
4. `conversation/interpreter.py` — IntentInterpreter (orchestrates stages + handlers)
5. `conversation/handlers.py` — Status + Stop direct handlers (no LLM)
6. `taim-vault/system/prompts/intent-classifier.yaml` (Tier 3 prompt)
7. `taim-vault/system/prompts/intent-interpreter.yaml` (Tier 2 prompt)
8. WebSocket integration: `api/chat.py` updated to call interpreter
9. Lifespan integration: IntentInterpreter in app.state

**Bootstrap Strategy: Optional Dependencies**
- `memory: MemoryReader | None = None` — Step 4 will inject
- `orchestrator: Orchestrator | None = None` — Step 7 will inject
- Without these: Stage 2 runs without user_preferences, status/stop return placeholder responses

---

## 2. Module Architecture

### 2.1 File Layout

```
backend/src/taim/
├── conversation/
│   ├── __init__.py         # Public exports
│   ├── interpreter.py      # IntentInterpreter (main orchestrator)
│   ├── classifier.py       # Stage 1: classify_intent()
│   ├── understander.py     # Stage 2: understand_task()
│   └── handlers.py         # handle_status(), handle_stop()
├── models/
│   └── chat.py             # IntentCategory + 5 Pydantic models
├── api/
│   └── chat.py             # WebSocket — updated to call interpreter

taim-vault/system/prompts/
├── intent-classifier.yaml  # Stage 1 prompt (Tier 3)
└── intent-interpreter.yaml # Stage 2 prompt (Tier 2)
```

### 2.2 Dependency Graph

```
models/chat.py                      (no TAIM deps)
    ↓
conversation/classifier.py          (depends on: models/chat, router, prompts)
conversation/understander.py        (depends on: models/chat, router, prompts)
conversation/handlers.py            (depends on: models/chat — orchestrator is Optional)
    ↓
conversation/interpreter.py         (composes all above)
    ↓
api/chat.py                         (WebSocket calls interpreter)
main.py                             (lifespan creates interpreter, stores in app.state)
```

---

## 3. Data Models (`models/chat.py`)

```python
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
    """Final output of IntentInterpreter — wraps direct responses or Stage 2 results."""
    classification: IntentClassification
    intent: IntentResult | None = None     # Set if Stage 2 was invoked
    direct_response: str | None = None     # Set for status/stop/confirmation
    needs_followup: bool = False
    followup_question: str | None = None
```

---

## 4. Stage 1: Classifier

**Responsibility:** Classify the user's message into one of 7 categories using a Tier 3 model.

```python
# conversation/classifier.py
from taim.models.chat import IntentCategory, IntentClassification
from taim.models.router import ModelTierEnum

CONFIDENCE_THRESHOLD = 0.80


async def classify_intent(
    message: str,
    recent_context: str,
    router: LLMRouter,
    prompt_loader: PromptLoader,
    session_id: str | None = None,
) -> IntentClassification:
    """Stage 1: Quick classification using Tier 3 model."""
    prompt = prompt_loader.load(
        "intent-classifier",
        {"user_message": message, "recent_context": recent_context},
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

---

## 5. Stage 2: Understander

**Responsibility:** Extract a structured task command using a Tier 2 model. Optionally enriches with user memory.

```python
# conversation/understander.py
async def understand_task(
    message: str,
    recent_context: str,
    router: LLMRouter,
    prompt_loader: PromptLoader,
    user_preferences: str = "",   # Empty if no memory available
    session_id: str | None = None,
) -> IntentResult:
    """Stage 2: Deep task extraction using Tier 2 model."""
    prompt = prompt_loader.load(
        "intent-interpreter",
        {
            "user_message": message,
            "recent_context": recent_context,
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

---

## 6. Direct Handlers (`handlers.py`)

No LLM calls. Pure Python with optional orchestrator dependency.

```python
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

For Step 3, `Orchestrator` is a `Protocol` defined in `conversation/handlers.py` — Step 7 will provide the real implementation. This avoids circular imports while typing the dependency.

---

## 7. IntentInterpreter (Main Orchestrator)

```python
# conversation/interpreter.py
from taim.conversation.classifier import classify_intent, CONFIDENCE_THRESHOLD
from taim.conversation.handlers import handle_status, handle_stop
from taim.conversation.understander import understand_task

# Categories that bypass Stage 2 when confidence is high
_DIRECT_CATEGORIES = {
    IntentCategory.STATUS_QUERY,
    IntentCategory.STOP_COMMAND,
    IntentCategory.CONFIRMATION,
    IntentCategory.ONBOARDING_RESPONSE,
}


class IntentInterpreter:
    def __init__(
        self,
        router: LLMRouter,
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

        # Direct handlers (high confidence + bypass category)
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
        return "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent[-5:])

    def _build_followup(self, missing: list[str]) -> str:
        if len(missing) == 1:
            return f"To proceed, I need to know: {missing[0]}"
        return f"To proceed, I need a few details: {', '.join(missing[:3])}"
```

**Note on follow-up question generation:** US-2.2 AC3 says "generate a single targeted follow-up question (not a list)." For Step 3 we use a simple template. A future improvement (Step 4 or later) could use a Tier 3 LLM call to phrase the question naturally.

---

## 8. WebSocket Integration (`api/chat.py`)

The Step 1 stub is replaced with a real handler that calls the interpreter.

```python
@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
) -> None:
    await websocket.accept()
    interpreter: IntentInterpreter = websocket.app.state.interpreter

    # Per-session in-memory message history (Step 4 will formalize this)
    history: list[dict] = []

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("content", "")
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
            except Exception as exc:
                logger.exception("interpreter.error", session=session_id)
                await websocket.send_json({
                    "type": "error",
                    "content": "I had trouble understanding that. Could you rephrase?",
                    "session_id": session_id,
                })
                continue

            response_text = result.direct_response or result.followup_question or _summarize(result.intent)
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

The full chat experience (plan_proposed events, agent_started events, etc.) comes in Steps 7-8 when the Orchestrator can act on the IntentResult.

---

## 9. Prompt YAML Files

Both prompts get created in the vault. The vault's `_ensure_default_configs` is for config — prompts are checked in via VaultOps' new `_ensure_default_prompts()` method (added in Step 3).

### intent-classifier.yaml
Stage 1, Tier 3, classifies into one of 7 categories with confidence + needs_deep_analysis.

### intent-interpreter.yaml
Stage 2, Tier 2, extracts task_type, objective, parameters, constraints, missing_info, suggested_team.

Full content in implementation plan.

---

## 10. Critical Review Findings (Applied)

| # | Finding | Resolution |
|---|---------|------------|
| 1 | Confidence threshold (RISK-07) — must escalate to Stage 2 when Stage 1 < 0.80 | `CONFIDENCE_THRESHOLD = 0.80`, checked in interpreter |
| 2 | Stage 2 needs memory but Memory System is Step 4 | `MemoryReader` Protocol with optional dependency; Stage 2 runs with empty preferences if memory is None |
| 3 | Status/Stop need orchestrator (Step 7) | `Orchestrator` Protocol with optional dependency; placeholder responses if None |
| 4 | Prompts must exist before tests | VaultOps' new `_ensure_default_prompts()` writes them on init |
| 5 | Stage 1 cost gets logged (US-2.1 AC6) | Router already logs every call; pass `session_id` for correlation |
| 6 | Direct categories should respect needs_deep_analysis flag | Check `not needs_deep_analysis` before bypassing Stage 2 |
| 7 | Follow-up question generation (US-2.2 AC3) | Simple template for Step 3; LLM-based phrasing is a future improvement |
| 8 | WebSocket needs basic message history per session | In-memory dict in handler for Step 3; formalized as Hot Memory in Step 4 |
| 9 | Existing WebSocket stub must be replaced, not extended | api/chat.py rewritten — old stub deleted |

---

## 11. Test Strategy

**MockRouter** added to conftest — returns canned LLMResponses for given prompts. (Different from Step 2's MockTransport which mocks at the transport layer.)

```python
class MockRouter:
    def __init__(self, responses: list[LLMResponse | Exception]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def complete(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
```

### Test Files

| File | Tests |
|------|-------|
| `test_chat_models.py` | Pydantic models — defaults, validation, enum values |
| `test_classifier.py` | Stage 1 — JSON parsing, category extraction, confidence |
| `test_understander.py` | Stage 2 — IntentResult parsing, missing_info handling |
| `test_handlers.py` | Status/Stop with and without orchestrator |
| `test_interpreter.py` | Full flow: direct categories, Stage 2 escalation, low confidence, follow-up |
| `test_chat_websocket.py` | WebSocket integration with mocked interpreter |

Coverage target: >80% (NFR-16).

---

*End of Step 3 Intent Interpreter Design.*
