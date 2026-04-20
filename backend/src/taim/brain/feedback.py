"""FeedbackCollector — scores agent runs automatically or from user input."""

from __future__ import annotations

from taim.models.agent import AgentRun, AgentStateEnum
from taim.models.chat import IntentResult
from taim.models.feedback import TaskFeedback


class FeedbackCollector:
    """Scores completed agent runs."""

    def score_from_run(self, run: AgentRun, intent: IntentResult) -> TaskFeedback:
        """Auto-score a completed agent run using heuristics."""
        score = 0.5
        signals: dict = {}

        # Completion bonus
        if run.final_state == AgentStateEnum.DONE:
            score += 0.2
            signals["completed"] = True
        else:
            score -= 0.3
            signals["completed"] = False

        # Fewer iterations = better
        iteration_count = sum(1 for t in run.state_history if t.reason and "iteration" in t.reason)
        signals["iterations"] = iteration_count
        if iteration_count == 0:
            score += 0.2
            signals["first_pass"] = True
        elif iteration_count <= 2:
            score += 0.1

        # Has result content
        if run.result_content and len(run.result_content) > 50:
            score += 0.1
            signals["has_content"] = True

        score = max(0.0, min(1.0, score))

        return TaskFeedback(
            task_id=run.task_id,
            agent_name=run.agent_name,
            score=round(score, 2),
            source="auto_heuristic",
            signals=signals,
            task_type=intent.task_type,
            objective=intent.objective,
        )

    def score_from_user(
        self,
        task_id: str,
        agent_name: str,
        positive: bool,
        task_type: str = "",
        objective: str = "",
    ) -> TaskFeedback:
        """Score from explicit user feedback."""
        return TaskFeedback(
            task_id=task_id,
            agent_name=agent_name,
            score=0.9 if positive else 0.2,
            source="user_explicit",
            signals={"user_positive": positive},
            task_type=task_type,
            objective=objective,
        )
