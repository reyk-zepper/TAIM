"""OnboardingFlow — guided first-run setup."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

import structlog

from taim.brain.memory import MemoryManager
from taim.models.memory import MemoryEntry

logger = structlog.get_logger()


class OnboardingStep(StrEnum):
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
        """Process user response for current step, advance, return next message."""
        if state.step == OnboardingStep.WELCOME:
            state.work_context = user_message
            state.step = _NEXT_STEP[state.step]
            return _STEP_MESSAGES[OnboardingStep.API_KEY]

        if state.step == OnboardingStep.API_KEY:
            state.api_key_info = user_message
            state.step = _NEXT_STEP[state.step]
            return _STEP_MESSAGES[OnboardingStep.RULES]

        if state.step == OnboardingStep.RULES:
            state.rules = user_message
            state.step = _NEXT_STEP[state.step]
            return await self._complete_onboarding(state)

        if state.step == OnboardingStep.SUMMARY:
            state.step = OnboardingStep.DONE
            return "You're all set! What can I help you with?"

        return "Something went wrong. Type 'reset setup' to start over."

    async def _complete_onboarding(self, state: OnboardingState) -> str:
        """Persist onboarding data and return summary."""
        today = date.today()

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

        rules_lower = state.rules.lower().strip()
        has_rules = rules_lower and rules_lower not in (
            "no",
            "no rules",
            "none",
            "skip",
            "nope",
        )
        if has_rules:
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

        if has_rules:
            lines.append(f"✓ Rules: {state.rules[:80]}")
        else:
            lines.append("✓ Rules: none set")

        lines.append("\nYou're ready. Confirm with 'OK' or type your first task.")
        return "\n".join(lines)
