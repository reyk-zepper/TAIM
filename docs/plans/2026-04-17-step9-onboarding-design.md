# Step 9: Onboarding & Smart Defaults — Design + Plan

> Version: 1.0
> Date: 2026-04-17
> Status: Reviewed
> Scope: US-1.1 (Guided Onboarding), US-1.3 (Smart Defaults formalization)

---

## 1. What Already Exists

| Feature | Status | Where |
|---------|--------|-------|
| defaults.yaml loading | ✅ Done | VaultOps → ProductConfig.defaults |
| Constraint extraction | ✅ Done | IntentResult.constraints |
| Memory persistence | ✅ Done | MemoryManager writes preferences |
| Intent classification | ✅ Done | onboarding_response category exists |
| US-1.2 NL task request | ✅ Done | IntentInterpreter + Orchestrator |
| US-1.4 inline constraints | ✅ Done | IntentResult.constraints parsed by Stage 2 |
| US-1.5 session continuity | ✅ Done | Hot Memory + Session Store + Summarizer |

## 2. What to Build

### 2.1 OnboardingFlow (`conversation/onboarding.py`)

A state machine that guides a first-time user through setup:

```
Step 1: Welcome + ask work context ("What kind of work do you do?")
Step 2: API key setup ("Do you have API keys for Anthropic or OpenAI?")
Step 3: Rules/compliance ("Any rules I should follow?")
Step 4: Summary + confirmation
Step 5: Done → normal chat mode
```

**Detection:** On WebSocket connect, check if `users/default/memory/user-profile.md` exists. If not → trigger onboarding.

**State tracking:** `app.state.onboarding_sessions: dict[str, OnboardingState]` — per-session, volatile.

### 2.2 SmartDefaults (`conversation/defaults.py`)

Formalize the defaults application:
- Load from `defaults.yaml` (already in `ProductConfig.defaults`)
- Apply to `IntentResult` when constraints are not explicitly set
- Log which defaults were applied

### 2.3 REST API

- `POST /api/setup/init` — trigger onboarding programmatically
- `POST /api/setup/provider` — add a provider config

### 2.4 Onboarding Prompt

`taim-vault/system/prompts/onboarding.yaml` — extracts user role, industry, preferences from free-text responses.

---

## 3. OnboardingFlow

```python
"""OnboardingFlow — guided first-run setup."""

from __future__ import annotations

from datetime import date
from enum import Enum

import structlog

from taim.brain.memory import MemoryManager
from taim.models.memory import MemoryEntry

logger = structlog.get_logger()


class OnboardingStep(str, Enum):
    WELCOME = "welcome"
    API_KEY = "api_key"
    RULES = "rules"
    SUMMARY = "summary"
    DONE = "done"


_STEP_MESSAGES = {
    OnboardingStep.WELCOME: (
        "Welcome! I'm tAIm — your AI team manager.\n"
        "I help you get expert-level results from AI without needing to know how it works.\n"
        "Let's get you set up in about 2 minutes.\n\n"
        "What kind of work do you mainly do?"
    ),
    OnboardingStep.API_KEY: (
        "Thanks! Now I need access to an AI service.\n"
        "Do you have an API key for Anthropic (Claude) or OpenAI?\n"
        "If not, I can also work with Ollama (free, runs locally).\n\n"
        "Paste your API key here, or type 'ollama' for local mode, or 'skip' to set up later."
    ),
    OnboardingStep.RULES: (
        "Almost done. Are there any rules I should follow?\n"
        "For example:\n"
        "• Data privacy (GDPR, no customer data in outputs)\n"
        "• Brand guidelines (tone, language, style)\n"
        "• Things I must never do\n\n"
        "If you have nothing specific, just say 'no rules'."
    ),
}

_NEXT_STEP = {
    OnboardingStep.WELCOME: OnboardingStep.API_KEY,
    OnboardingStep.API_KEY: OnboardingStep.RULES,
    OnboardingStep.RULES: OnboardingStep.SUMMARY,
    OnboardingStep.SUMMARY: OnboardingStep.DONE,
}


class OnboardingState:
    """Per-session onboarding progress."""

    def __init__(self) -> None:
        self.step = OnboardingStep.WELCOME
        self.work_context: str = ""
        self.api_key_info: str = ""
        self.rules: str = ""

    @property
    def is_complete(self) -> bool:
        return self.step == OnboardingStep.DONE


class OnboardingFlow:
    """Manages the guided onboarding conversation."""

    def __init__(self, memory: MemoryManager) -> None:
        self._memory = memory

    def get_welcome_message(self) -> str:
        return _STEP_MESSAGES[OnboardingStep.WELCOME]

    async def is_needed(self, user: str = "default") -> bool:
        """Check if onboarding has been completed."""
        profile = await self._memory.read_entry("user-profile.md", user=user)
        return profile is None

    async def handle_response(
        self,
        state: OnboardingState,
        user_message: str,
    ) -> str:
        """Process user's response for the current step, advance, return next message."""
        if state.step == OnboardingStep.WELCOME:
            state.work_context = user_message
            state.step = _NEXT_STEP[state.step]
            return _STEP_MESSAGES[OnboardingStep.API_KEY]

        elif state.step == OnboardingStep.API_KEY:
            state.api_key_info = user_message
            state.step = _NEXT_STEP[state.step]
            return _STEP_MESSAGES[OnboardingStep.RULES]

        elif state.step == OnboardingStep.RULES:
            state.rules = user_message
            state.step = _NEXT_STEP[state.step]
            # Persist and generate summary
            summary = await self._complete_onboarding(state)
            return summary

        elif state.step == OnboardingStep.SUMMARY:
            state.step = OnboardingStep.DONE
            return "You're all set! What can I help you with?"

        return "Something went wrong with the setup. Type 'reset setup' to start over."

    async def _complete_onboarding(self, state: OnboardingState) -> str:
        """Persist onboarding data and return summary."""
        today = date.today()

        # Save user profile
        await self._memory.write_entry(
            MemoryEntry(
                title="User Profile",
                category="user-profile",
                tags=["user-profile", "onboarding"],
                created=today,
                updated=today,
                content=f"Work context: {state.work_context}",
                source="onboarding",
            ),
            "user-profile.md",
        )

        # Save rules if provided
        rules_lower = state.rules.lower().strip()
        if rules_lower and rules_lower not in ("no", "no rules", "none", "skip", "nope"):
            await self._memory.write_entry(
                MemoryEntry(
                    title="Compliance Rules",
                    category="rules",
                    tags=["rules", "compliance", "onboarding"],
                    created=today,
                    updated=today,
                    content=state.rules,
                    source="onboarding",
                ),
                "compliance-rules.md",
            )

        # Build summary
        lines = [
            "Here's what I've set up for you:",
            f"✓ Work context: {state.work_context[:80]}",
        ]
        key_info = state.api_key_info.lower().strip()
        if key_info in ("skip", "later"):
            lines.append("✓ API key: skipped (you can set it up later)")
        elif key_info == "ollama":
            lines.append("✓ Provider: Ollama (local, free)")
        else:
            lines.append("✓ API key: saved (local only)")

        if rules_lower and rules_lower not in ("no", "no rules", "none", "skip", "nope"):
            lines.append(f"✓ Rules: {state.rules[:80]}")
        else:
            lines.append("✓ Rules: none set")

        lines.append("\nYou're ready. Confirm with 'OK' or type your first task.")
        return "\n".join(lines)
```

---

## 4. SmartDefaults (`conversation/defaults.py`)

```python
"""SmartDefaults — apply defaults.yaml values to IntentResult."""

from __future__ import annotations

import structlog

from taim.models.chat import IntentResult, TaskConstraints

logger = structlog.get_logger()


class SmartDefaults:
    """Applies defaults from config when user doesn't specify values."""

    def __init__(self, defaults: dict) -> None:
        self._defaults = defaults

    def apply(self, intent: IntentResult) -> IntentResult:
        """Fill in missing constraints from defaults. Returns modified intent."""
        team = self._defaults.get("team", {})

        if intent.constraints.time_limit_seconds is None:
            time_budget = team.get("time_budget", "2h")
            intent.constraints.time_limit_seconds = self._parse_time(time_budget)

        if intent.constraints.budget_eur is None:
            token_budget = team.get("token_budget", 500000)
            # Rough cost estimate: 500k tokens ≈ €5 at tier2 rates
            intent.constraints.budget_eur = token_budget * 0.00001

        logger.debug(
            "defaults.applied",
            time_limit=intent.constraints.time_limit_seconds,
            budget_eur=intent.constraints.budget_eur,
        )
        return intent

    @staticmethod
    def _parse_time(s: str) -> int:
        """Parse time strings like '2h', '30m', '1h30m' into seconds."""
        s = s.lower().strip()
        total = 0
        if "h" in s:
            parts = s.split("h")
            total += int(parts[0]) * 3600
            s = parts[1] if len(parts) > 1 else ""
        if "m" in s:
            total += int(s.replace("m", "").strip() or 0) * 60
        return total or 7200  # default 2h
```

---

## 5. Chat Integration

In `api/chat.py`, at the start of the WebSocket message loop (BEFORE the pending_plan check):

```python
# Check if onboarding needed
onboarding_sessions = getattr(websocket.app.state, "onboarding_sessions", {})
onboarding_flow = getattr(websocket.app.state, "onboarding_flow", None)

if session_id in onboarding_sessions:
    state = onboarding_sessions[session_id]
    response = await onboarding_flow.handle_response(state, user_message)
    hot.append_message(session_id, "assistant", response)
    await store.persist(hot.get_or_create(session_id))
    await websocket.send_json({
        "type": "onboarding",
        "content": response,
        "step": state.step.value,
        "session_id": session_id,
    })
    if state.is_complete:
        del onboarding_sessions[session_id]
    continue
```

On first connect (before the message loop), check if onboarding is needed:
```python
if onboarding_flow and await onboarding_flow.is_needed():
    state = OnboardingState()
    onboarding_sessions[session_id] = state
    welcome = onboarding_flow.get_welcome_message()
    await websocket.send_json({
        "type": "onboarding",
        "content": welcome,
        "step": "welcome",
        "session_id": session_id,
    })
```

---

## 6. Lifespan + API

In main.py:
```python
    # 15. Onboarding + Smart Defaults
    from taim.conversation.onboarding import OnboardingFlow
    from taim.conversation.defaults import SmartDefaults

    onboarding_flow = OnboardingFlow(memory=memory_manager)
    smart_defaults = SmartDefaults(product_config.defaults)

    app.state.onboarding_flow = onboarding_flow
    app.state.smart_defaults = smart_defaults
    app.state.onboarding_sessions = {}
```

`POST /api/setup/init` triggers onboarding reset (deletes user-profile.md so next WS connect re-triggers).

---

## 7. Implementation Tasks

### Task 1: OnboardingFlow + SmartDefaults + Tests
### Task 2: Chat integration + API + Verify

---

*End of Step 9 Design.*
