"""SmartDefaults — apply defaults.yaml values to IntentResult."""

from __future__ import annotations

import structlog

from taim.models.chat import IntentResult

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
            intent.constraints.budget_eur = round(token_budget * 0.00001, 2)

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
            m_part = s.replace("m", "").strip()
            total += int(m_part) * 60 if m_part else 0
        return total or 7200
