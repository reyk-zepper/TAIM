# TAIM — Architecture Decisions (Phase 1 MVP)

> Finalized: 2026-04-12
> Status: Approved — basis for implementation

---

## Overview

This document captures all architectural decisions made before Phase 1 implementation begins. Each decision includes the reasoning and trade-offs considered.

---

## Decision 1: Prompts as First-Class Vault Citizens

**Decision:** All system prompts are stored as versioned YAML files in `taim-vault/system/prompts/`, never as hardcoded strings in Python code.

**Why this matters:** 80% of TAIM's output quality is determined by prompt quality, not code quality. The Python/React code is plumbing. The prompts are the actual product.

**Format:**
```yaml
# taim-vault/system/prompts/intent-interpreter.yaml
name: intent-interpreter
version: 1
description: "Translates natural language into structured task commands"
model_tier: tier2_standard
variables:
  - user_language
  - available_agents
  - user_preferences
template: |
  You are TAIM's Intent Interpreter...
```

**Implications:**
- Code always loads prompts from vault files via the `PromptLoader` utility
- Prompts are versionable, editable, and improvable without code changes
- Clears the path for Phase 2 Learning Loop (optimizes prompts, not code)
- Power users can customize prompts in Layer 2
- All prompt changes are auditable through git history

**Vault path:** `taim-vault/system/prompts/`

---

## Decision 2: Two-Stage Intent Interpretation

**Decision:** The Intent Interpreter uses two stages instead of one.

**Stage 1 — Quick Classification (Tier 3, cheap):**
- Categorizes the message: new_task, confirmation, follow_up, status_query, configuration, stop_command
- Costs ~50-100 tokens per message
- Handles 60-70% of all messages (simple confirmations, status checks, yes/no)
- Falls through to Stage 2 only for complex requests

**Stage 2 — Deep Understanding (Tier 2, only when needed):**
- Extracts: task_type, parameters, constraints, missing_info
- Loads user memory for context enrichment
- Decides: execute immediately or ask follow-up question
- Uses structured JSON output format

**Why not single-stage:**
- Single Tier 3 model: too dumb for complex requests, breaks the AI Equalizer promise
- Single Tier 2 model: wasteful for simple messages ("yes", "stop", "show status")
- Two-stage: cheap where possible, smart where needed. ~40% cost savings.

**This mirrors human processing:** First categorize (fast), then analyze (slow). The same pattern that makes humans efficient at processing requests.

---

## Decision 3: Agents as Explicit State Machines

**Decision:** Each agent runs as a state machine with explicit, serializable states — not as a simple async loop.

**States:**

| State | Description | Prompt Type |
|-------|-------------|-------------|
| `PLANNING` | Agent analyzes task, plans approach | Planning prompt |
| `EXECUTING` | Agent works on the task | Execution prompt |
| `REVIEWING` | Agent checks own result | Review prompt |
| `ITERATING` | Improvement based on review | Iteration prompt |
| `WAITING` | Needs user input or approval | — |
| `DONE` | Result ready | — |
| `FAILED` | Unrecoverable error | — |

**Transitions:**
```
PLANNING → EXECUTING → REVIEWING → DONE
                          │
                    (needs improvement?)
                          │
                       ITERATING → EXECUTING
                       
Any state → WAITING (needs approval)
WAITING → (previous state) (approval received)
Any state → FAILED (unrecoverable error)
```

**Why state machines over simple loops:**
1. **Debuggable** — Dashboard shows: "Researcher is in REVIEWING, iteration 2/3"
2. **Controllable** — Heartbeat checks state, not just "is it running". Can intervene per state.
3. **Resumable** — State is serializable to SQLite. Process crash → pick up from last state.
4. **LLM-optimized** — Each state gets its own focused prompt. Focused prompts → better results. A "plan your approach" prompt is fundamentally different from a "review your result" prompt.
5. **Observable** — Frontend receives state transitions as WebSocket events. User feels a real team working.

**Implementation:** `AgentStateMachine` class with `current_state`, `transition()`, `serialize()`, `deserialize()` methods. Runs as async coroutine within FastAPI process.

---

## Decision 4: Token-Budgeted Context Assembly

**Decision:** Each agent gets a token budget for its context. The Context Assembler never exceeds it.

**Priority order (highest first):**
1. Task description (mandatory — always included)
2. Active rules/constraints (mandatory — always included)
3. Relevant memory entries (scored by relevance)
4. Few-shot examples from prompt cache (if budget remains)
5. Team context / results from other agents (if budget remains)

**Budget defaults:**
- Tier 1 agents: 4000 tokens context budget
- Tier 2 agents: 2000 tokens context budget
- Tier 3 agents: 800 tokens context budget

**Relevance scoring:** Simple keyword/tag matching against the task description and agent role. No vectors, no embeddings. Works because claudianX memory entries are well-structured with tags and categories.

**Why this matters:**
- Too much context → diluted attention, higher cost, potentially worse results
- Too little context → poor results, missing preferences
- Budget-based → predictable costs, consistent quality
- Fundamentally different from RAG: selects by relevance to task+role+user, not by semantic similarity

---

## Decision 5: Three-Temperature Memory Architecture

**Decision:** Memory is organized in three layers with different loading strategies.

| Layer | Contents | When Loaded | Storage |
|-------|----------|-------------|---------|
| **Hot** | Current session, chat history, active task context | Always in RAM | In-memory dict |
| **Warm** | User preferences, agent configs, recent patterns | At session start via INDEX.md scan | Markdown files (read on demand) |
| **Cold** | Historical patterns, old task results, archived data | Only on explicit need | Markdown files (rarely read) |

**INDEX.md as lightweight retrieval index:**
- Each memory entry has tags and a one-line summary in INDEX.md
- Starting a new chat: scan INDEX.md (~50-200 lines), identify relevant tags for the user
- Load only matching warm memory entries
- Cold memory only when user asks about history or Context Assembler needs more data

**Why three layers:**
- New chat startup doesn't require loading all memory
- Memory cost scales with relevance, not total memory size
- Hot layer enables fast session continuity
- Warm layer provides personalization without overhead
- Cold layer preserves institutional knowledge without cost

---

## Decision 6: Rich WebSocket Event Model

**Decision:** WebSocket communication uses a typed event stream, not simple request/response.

**Event types:**

```typescript
type WSEvent = {
  type: 
    | "thinking"          // TAIM is processing (show loading)
    | "plan_proposed"     // Team plan ready for approval
    | "agent_started"     // Agent began working
    | "agent_progress"    // Live update from agent
    | "agent_state"       // State machine transition
    | "agent_completed"   // Agent finished with summary
    | "question"          // TAIM needs user input
    | "result"            // Final result ready
    | "budget_warning"    // Budget threshold reached
    | "error"             // Error with context
    | "system"            // System messages (connection, heartbeat)
  
  content: string
  timestamp: string  // ISO 8601
  metadata?: {
    agent_name?: string
    task_id?: string
    team_id?: string
    tokens_used?: number
    cost?: number
    state?: AgentState
    progress?: number    // 0-100 percentage
  }
}
```

**Client → Server messages:**

```typescript
type WSMessage = {
  type: "user_message" | "approval" | "stop" | "ping"
  content: string
  metadata?: {
    team_id?: string
    task_id?: string
    approved?: boolean
  }
}
```

**Why a rich event model:**
- Transforms "waiting for a response" into "watching my team work"
- Enables granular UI updates (progress bars, state indicators, live cost tracking)
- Supports the approval gate flow naturally (plan_proposed → user approves → execution continues)
- Budget warnings prevent surprise costs
- All events are loggable for audit trail

---

## Decision 7: Configurable Team Orchestration Patterns

**Decision:** Teams support four orchestration patterns, auto-selected by the Team Composer with smart defaults.

| Pattern | When Used | Example |
|---------|-----------|---------|
| **Sequential** | Output of A is input for B | Researcher → Analyst → Writer |
| **Parallel** | Independent subtasks | 3 Researchers working simultaneously |
| **Pipeline** | Processing chain with transformation | Collect → Analyze → Format → Review |
| **Hierarchical** | Lead delegates to workers | Lead Researcher coordinates 3 Sub-Researchers |

**Auto-selection logic:**
- Research tasks with report → Pipeline (research → analyze → write)
- Multi-source research → Parallel (multiple researchers) + Sequential (→ analyst)
- Code tasks → Sequential (plan → code → review)
- Simple single tasks → no team needed, single agent

**Configuration (Layer 2):**
```yaml
teams:
  research-team:
    pattern: parallel_then_sequential
    parallel_agents: [researcher-1, researcher-2, researcher-3]
    sequential_agents: [analyst, writer]
```

**Layer 1 users never see this.** The Composer picks the best pattern based on task analysis.

---

## Decision 8: Single Central SQLite Database

**Decision:** One SQLite database at `taim-vault/system/state/taim.db` for all runtime state.

**Tables:**
- `token_tracking` — per agent, per task, per team token usage and costs
- `task_state` — active and completed tasks with serialized state
- `session_state` — chat history, session metadata
- `agent_runs` — execution log for each agent run (start, end, state transitions, result summary)

**Why single DB:**
- Simple to backup (one file)
- Simple to migrate
- SQLite handles concurrent reads well (WAL mode)
- Transactions across tables (e.g., update task state + track tokens atomically)
- Sufficient for single-user MVP; PostgreSQL migration path clear for Phase 3

---

## Decision 9: Zustand for Frontend State Management

**Decision:** Use Zustand for React state management.

**Why Zustand over alternatives:**
- Minimal boilerplate (vs. Redux Toolkit)
- No provider wrapping needed (vs. React Context)
- Built-in support for subscriptions (perfect for WebSocket updates)
- TypeScript-first
- ~1KB bundle size
- Simple mental model: stores are just hooks

**Store structure:**
- `useChatStore` — messages, connection state, input
- `useTeamStore` — active teams, agent states, progress
- `useStatsStore` — token usage, costs, budget
- `useAppStore` — navigation, settings, user profile

---

## Decision 10: Error-Type-Aware LLM Error Handling

**Decision:** Error handling distinguishes between error types and responds differently to each.

| Error Type | Detection | Response |
|-----------|-----------|----------|
| **Rate limit** | HTTP 429 | Wait + retry same provider (exponential backoff) |
| **Timeout** | No response within limit | Retry once, then failover |
| **Safety filter** | Content blocked response | Retry with softened prompt, then failover |
| **Bad format** | Response doesn't match expected structure | Retry with format reminder appended to prompt |
| **Low quality** | Response is too short/generic (heuristic) | Escalate to higher tier model |
| **Provider down** | Connection error | Immediate failover to next provider |
| **All providers failed** | No provider available | Inform user with context, suggest checking API keys |

**Retry budget:** Maximum 3 total attempts per LLM call (including failovers). Never infinite retry.

**User communication:** Every error that affects the user gets a WebSocket `error` event with human-readable context. Never fail silently.

---

## Decision 11: Conversation History Management

**Decision:** Chat history is managed with a sliding window + summary strategy.

- **Last 20 messages** are always in context (hot memory)
- **Older messages** get summarized by a Tier 3 model into a compact session summary
- **Session summary** is stored as a warm memory entry
- **Cross-session continuity** via memory entries, not raw history replay

This keeps context costs predictable while maintaining conversational coherence.

---

## Summary Table

| # | Decision | Key Principle |
|---|----------|--------------|
| 1 | Prompts as vault files | The prompts are the product |
| 2 | Two-stage intent interpretation | Cheap where possible, smart where needed |
| 3 | Agents as state machines | Debuggable, controllable, resumable |
| 4 | Token-budgeted context assembly | Relevance beats completeness |
| 5 | Three-temperature memory | Cost scales with relevance |
| 6 | Rich WebSocket events | Watching a team work, not waiting for a response |
| 7 | Configurable orchestration patterns | Smart defaults, expert overrides |
| 8 | Single SQLite database | Simple, sufficient, migratable |
| 9 | Zustand for frontend | Lightweight, TypeScript-first |
| 10 | Error-type-aware handling | Different errors need different responses |
| 11 | Sliding window + summary for chat | Predictable costs, maintained coherence |

---

*These decisions form the technical foundation for Phase 1 implementation. All can be revisited as we learn from building, but provide a clear starting point with considered trade-offs.*
