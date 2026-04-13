"""IntentInterpreter — orchestrates Stage 1, Stage 2, and direct handlers."""

from __future__ import annotations

from typing import Protocol

from taim.brain.prompts import PromptLoader
from taim.conversation.classifier import CONFIDENCE_THRESHOLD, classify_intent
from taim.conversation.handlers import Orchestrator, handle_status, handle_stop
from taim.conversation.understander import understand_task
from taim.models.chat import IntentCategory, InterpreterResult


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
    """Routes user messages through Stage 1 → (direct handler | Stage 2)."""

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
