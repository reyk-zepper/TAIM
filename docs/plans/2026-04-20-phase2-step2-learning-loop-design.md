# Phase 2, Step 2: Learning Loop — Design

> Version: 1.0
> Date: 2026-04-20
> Scope: Prompt optimization from agent run feedback, success pattern extraction

---

## 1. Overview

The Learning Loop makes tAIm **get better through use**. After every agent run, the system:

1. **Scores** the result (user feedback or heuristic)
2. **Extracts** patterns from successful runs
3. **Stores** learnings as warm memory entries
4. **Applies** learnings to future context assembly

This is NOT fine-tuning. It's structured memory accumulation: successful patterns become part of future agent context, failed patterns become warnings.

```
Agent completes task
    ↓
FeedbackCollector — scores result (user thumbs-up/down or auto-heuristic)
    ↓
PatternExtractor — extracts what worked (Tier 3 LLM call)
    ↓
LearningStore — saves as warm memory with tags
    ↓
Context Assembler loads relevant learnings in future tasks
```

## 2. What Exists Already

- **Agent run records** in `agent_runs` table (final_state, cost, state_history)
- **Memory system** writes/reads/scans Markdown entries
- **Context Assembler** retrieves relevant memory by keyword/tag
- **PromptLoader** loads from vault YAML with mtime cache

The Learning Loop connects these — it's a feedback pipeline, not new infrastructure.

## 3. Components

### 3.1 FeedbackCollector (`brain/feedback.py`)

Collects quality signals:
- **Explicit**: User says "great result" or "this is wrong" → parsed by Stage 1 classifier (already has `confirmation` and `follow_up` categories)
- **Implicit**: Agent finished as DONE (positive) vs FAILED (negative), iteration count (fewer = better), review quality_ok on first try (strong positive)

```python
class TaskFeedback(BaseModel):
    task_id: str
    agent_name: str
    score: float          # 0.0 (bad) to 1.0 (excellent)
    source: str           # "user_explicit", "auto_heuristic"
    signals: dict         # e.g., {"final_state": "DONE", "iterations": 1, "review_first_pass": true}
    task_type: str
    objective: str


class FeedbackCollector:
    def score_from_run(self, run: AgentRun, intent: IntentResult) -> TaskFeedback:
        """Auto-score a completed agent run."""
        score = 0.5  # baseline
        signals = {}

        if run.final_state == AgentStateEnum.DONE:
            score += 0.2
            signals["completed"] = True
        else:
            score -= 0.3
            signals["completed"] = False

        # Fewer iterations = better
        iteration_count = sum(1 for t in run.state_history if t.reason and "iteration" in t.reason)
        if iteration_count == 0:
            score += 0.2  # First-pass success
            signals["first_pass"] = True
        elif iteration_count <= 2:
            score += 0.1
        signals["iterations"] = iteration_count

        score = max(0.0, min(1.0, score))
        ...

    def score_from_user(self, task_id: str, positive: bool) -> TaskFeedback:
        """Score from explicit user feedback."""
        ...
```

### 3.2 PatternExtractor (`brain/pattern_extractor.py`)

For high-scoring runs (score >= 0.7), extracts what worked using a Tier 3 LLM:

```python
class PatternExtractor:
    async def extract(self, feedback: TaskFeedback, result_content: str) -> str | None:
        """Extract a reusable pattern from a successful task."""
        if feedback.score < 0.7:
            return None

        prompt = self._prompts.load("pattern-extractor", {
            "task_type": feedback.task_type,
            "objective": feedback.objective,
            "agent_name": feedback.agent_name,
            "result_snippet": result_content[:2000],
        })
        response = await self._router.complete(
            messages=[{"role": "system", "content": prompt}],
            tier=ModelTierEnum.TIER3_ECONOMY,
        )
        return response.content.strip()
```

### 3.3 LearningStore (`brain/learning_store.py`)

Saves extracted patterns as warm memory entries with specific tags:

```python
class LearningStore:
    async def save_learning(self, feedback: TaskFeedback, pattern: str) -> None:
        entry = MemoryEntry(
            title=f"Learning: {feedback.task_type} — {feedback.agent_name}",
            category="learning",
            tags=["learning", feedback.task_type, feedback.agent_name, f"score:{feedback.score:.1f}"],
            content=pattern,
            source="learning_loop",
            confidence=feedback.score,
        )
        filename = f"learning-{feedback.task_id[:8]}.md"
        await self._memory.write_entry(entry, filename)
```

### 3.4 LearningLoop (`brain/learning_loop.py`)

Orchestrates the pipeline:

```python
class LearningLoop:
    async def process_completed_task(
        self, run: AgentRun, intent: IntentResult, result_content: str,
    ) -> None:
        # 1. Score
        feedback = self._collector.score_from_run(run, intent)

        # 2. Extract pattern (only for good results)
        pattern = await self._extractor.extract(feedback, result_content)

        # 3. Store
        if pattern:
            await self._store.save_learning(feedback, pattern)
            logger.info("learning.saved", task_type=feedback.task_type, score=feedback.score)
```

### 3.5 Integration into Orchestrator

In `orchestrator.py`, after `execute()` and `execute_team()` complete successfully:

```python
# Fire-and-forget learning
if self._learning_loop and result.status == TaskStatus.COMPLETED:
    asyncio.create_task(
        self._learning_loop.process_completed_task(run, intent, result.result_content)
    )
```

## 4. Pattern Extractor Prompt

`taim-vault/system/prompts/pattern-extractor.yaml`:
```yaml
name: pattern-extractor
version: 1
model_tier: tier3_economy
variables:
  - task_type
  - objective
  - agent_name
  - result_snippet
template: |
  A {{ agent_name }} agent successfully completed a {{ task_type }} task.

  Objective: {{ objective }}

  Result snippet:
  {{ result_snippet }}

  Extract a 2-3 sentence pattern describing WHAT made this successful.
  Focus on: approach used, key decisions, output structure.
  This pattern will help future agents with similar tasks.

  Respond with plain text only (no JSON, no markdown headers).
```

## 5. Context Assembler Enhancement

Learnings are already retrievable via existing memory scan (tags include "learning" + task_type + agent_name). The Context Assembler's `find_relevant()` will naturally pick up learnings when keywords match.

No code change needed — the Memory system handles it. The Learning Loop just writes to the same memory store.

## 6. Implementation Tasks

### Task 1: Models + FeedbackCollector + PatternExtractor + LearningStore + LearningLoop + Tests
### Task 2: Orchestrator integration + Prompt + Lifespan + Verify

---

*End of Phase 2 Step 2 Design.*
