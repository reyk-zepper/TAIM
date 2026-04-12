# TAIM Phase 1 MVP — Product Requirements Document

> Version: 1.0
> Date: 2026-04-12
> Status: Approved — basis for implementation
> Source documents: phase1-user-stories.md, phase1-api-contracts.md, phase1-tech-requirements.md, 2026-04-12-ux-ui-specification.md, 2026-04-12-architecture-decisions.md

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Goals & Success Criteria](#2-goals--success-criteria)
3. [Architecture Decisions](#3-architecture-decisions)
4. [User Stories & Acceptance Criteria](#4-user-stories--acceptance-criteria)
5. [API Specification](#5-api-specification)
6. [Data Models](#6-data-models)
7. [UX & Conversation Design](#7-ux--conversation-design)
8. [Technical Requirements](#8-technical-requirements)
9. [Dependencies & Tech Stack](#9-dependencies--tech-stack)
10. [Testing Strategy](#10-testing-strategy)
11. [Risk Register](#11-risk-register)
12. [Out of Scope (Phase 2+)](#12-out-of-scope-phase-2)
13. [Implementation Priority](#13-implementation-priority)

---

## 1. Executive Summary

TAIM (Team AI Manager) is an open-source, self-hosted AI team orchestration system. It enables any user — regardless of technical background — to manage AI agent teams through natural language. The guiding promise: **1 employee = 10**.

### What TAIM Is

TAIM is a system that makes expert-level AI results accessible to everyone. A marketing manager, consultant, or entrepreneur describes what they need in plain language. TAIM assembles an appropriate team of AI agents, proposes a plan, gets confirmation, executes — and the user watches their team work rather than waiting for a response.

TAIM is not a chatbot, a ticket system, or a workflow builder. It is an intelligent virtual team that works for you.

### Phase 1 Scope

Phase 1 delivers the Foundation MVP: the complete system from first-run onboarding through multi-agent execution, real-time monitoring, and results delivery. Every component needed for a working single-user system is in scope. Learning loops, knowledge compilation, multi-user support, and the Rules Engine are Phase 2+.

### Key Innovations

**AI Equalizer.** Today, productive AI use is an expert skill. TAIM closes that gap. No YAML, no model selection, no agent configuration. The system learns the user — the user does not learn the system.

**Conversation First.** Natural language is the primary interface. Every action TAIM takes can be initiated, modified, and stopped through plain text.

**Compile, Don't Search.** Knowledge is structured and retrieved by relevance matching, not vector search. No RAG, no embeddings. This keeps costs predictable and results auditable. (See Architecture Decision 4.)

**Control First.** Humans remain in control at all times. Approval gates pause execution before sensitive actions. Time and budget limits are first-class features, not afterthoughts.

**Agent State Machines.** Every agent is a debuggable state machine. The user can see exactly what each agent is doing. The system can resume from crashes. (See Architecture Decision 3.)

### Tech Stack Summary

- **Backend:** Python 3.11+, FastAPI, Uvicorn, SQLite (WAL mode), LiteLLM
- **Frontend:** React + TypeScript, Vite, TailwindCSS v4, Shadcn/ui, Zustand
- **Storage:** Filesystem (YAML config, Markdown memory), SQLite (runtime state)
- **Package management:** uv (Python), pnpm (Frontend)

---

## 2. Goals & Success Criteria

### Phase 1 Goals

1. A non-technical user can start TAIM, complete onboarding, and get a result from a multi-agent team — with zero documentation reading.
2. A power user can configure custom agents, override defaults, and interact via CLI.
3. The system never silently fails, never runs past authorized limits, and always preserves partial work.
4. Every LLM call, cost, and agent state transition is logged and traceable.

### Measurable Success Criteria

| Criterion | Target |
|-----------|--------|
| Onboarding completion (no docs) | User can configure and run first task in < 5 minutes |
| First task latency (plan proposed) | < 10 seconds from message to `plan_proposed` event |
| Intent Stage 1 latency | p95 < 500ms |
| Intent Stage 2 latency (to first `thinking` event) | p95 < 3 seconds |
| WebSocket event delivery (non-LLM) | p99 < 100ms |
| Dashboard load | TTI < 2s (dev), < 1.5s (prod) |
| Crash resumability | All non-terminal agents detectable within 10s of restart |
| Test coverage (core modules) | > 80% line coverage |
| Zero hardcoded prompts | All prompts in `taim-vault/system/prompts/` |
| Status query response | < 500ms, zero LLM calls |

### Phase 1 Deliverables Checklist

- [ ] FastAPI server with WebSocket support
- [ ] Conversation Layer with Two-Stage Intent Interpreter
- [ ] Guided Onboarding flow (5-step conversational setup)
- [ ] Smart Defaults engine
- [ ] Agent Registry (YAML-based, 5 built-in agents)
- [ ] Team Composer with auto-suggest and 4 orchestration patterns
- [ ] LLM Router with multi-provider support, tiering, and failover
- [ ] Agent Execution Engine (state machine per agent)
- [ ] Agent Memory system (claudianX pattern: INDEX.md + Markdown notes, no Obsidian)
- [ ] Three-temperature memory (Hot / Warm / Cold)
- [ ] Heartbeat Manager (time limits, stuck agent detection)
- [ ] Token tracking (per agent, per task, per team)
- [ ] React Dashboard with integrated Chat (primary view)
- [ ] Teams, Agents, and Stats views
- [ ] CLI for power users
- [ ] Tool Execution Framework (built-in tools: web_search, web_fetch, file_read/write, vault_memory)
- [ ] Agent Skills system (reusable prompt+tool patterns)
- [ ] MCP client integration (connect external MCP servers for extended tools)
- [ ] Tool sandboxing and security (path restrictions, approval gates, audit trail)
- [ ] TAIM Vault directory structure with defaults and built-in agents
- [ ] SQLite database auto-initialized on first run

---

## 3. Architecture Decisions

All 11 architecture decisions were finalized on 2026-04-12 and form the technical foundation for implementation. Full rationale and trade-off analysis: `docs/plans/2026-04-12-architecture-decisions.md`.

| # | Decision | Key Principle | Impact on Implementation |
|---|----------|--------------|--------------------------|
| AD-1 | Prompts as vault files | The prompts are the product | All system prompts in `taim-vault/system/prompts/*.yaml`. `PromptLoader` utility required. See US-11.2. |
| AD-2 | Two-stage intent interpretation | Cheap where possible, smart where needed | Stage 1: Tier 3, ~100 tokens, classifies intent. Stage 2: Tier 2, full understanding. ~40% cost savings. See US-2.1, US-2.2. |
| AD-3 | Agents as state machines | Debuggable, controllable, resumable | 7 states: PLANNING → EXECUTING → REVIEWING → ITERATING / WAITING / DONE / FAILED. Serialized to SQLite after every transition. See US-3.4. |
| AD-4 | Token-budgeted context assembly | Relevance beats completeness | Priority order: task → constraints → warm memory → examples → team context. No vectors. Tier 1: 4000 tokens, Tier 2: 2000, Tier 3: 800. See US-5.2. |
| AD-5 | Three-temperature memory | Cost scales with relevance | Hot: in-RAM (last 20 messages). Warm: user preferences, loaded via INDEX.md scan. Cold: historical, loaded on demand. See US-7.1–7.4. |
| AD-6 | Rich WebSocket event model | Watching a team work, not waiting | 11 server→client event types, 4 client→server types. All events typed and logged. See Section 5 (WebSocket Protocol). |
| AD-7 | Configurable orchestration patterns | Smart defaults, expert overrides | 4 patterns: Sequential, Parallel, Pipeline, Hierarchical. Auto-selected by Team Composer. See US-4.1, US-4.2. |
| AD-8 | Single SQLite database | Simple, sufficient, migratable | One DB at `taim-vault/system/state/taim.db`. 4 tables. WAL mode. See US-11.3. |
| AD-9 | Zustand for frontend state | Lightweight, TypeScript-first | 4 stores: `useChatStore`, `useTeamStore`, `useStatsStore`, `useAppStore`. See Section 7 (WebSocket→Store mapping). |
| AD-10 | Error-type-aware LLM handling | Different errors need different responses | 7 error types, distinct retry/failover logic per type. Max 3 total attempts. See US-6.3. |
| AD-11 | Sliding window + summary for chat | Predictable costs, maintained coherence | Last 20 messages in hot memory. Older messages summarized by Tier 3 model → warm memory entry. See US-1.5. |
| AD-12 | Tool Execution Framework with MCP | Agents must act, not just generate text | LiteLLM tool calling → ToolExecutor → built-in tools + MCP servers. Sandboxed, audited, controllable. See US-12.1–12.6. |

---

## 4. User Stories & Acceptance Criteria

> 59 user stories across 12 epics.
> Priority: P0 = must-have MVP blocker (40 stories), P1 = should-have (15 stories), P2 = nice-to-have (4 stories).
> P0 list: US-1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 3.1, 3.2, 3.4, 4.1, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 9.1, 9.2, 9.3, 9.4, 11.1, 11.2, 11.3, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6

---

### Epic 1: Conversation Layer & Onboarding

#### US-1.1: First-Run Guided Onboarding
**As a** first-time user **I want** TAIM to guide me through setup via natural language conversation **so that** I can start using the system without reading documentation or filling in forms.

**Acceptance Criteria:**
- [ ] AC1: On first launch, TAIM greets the user and asks what kind of work they primarily do.
- [ ] AC2: TAIM asks for at least one API key (Anthropic, OpenAI, or points to Ollama as a free option).
- [ ] AC3: TAIM asks about any basic compliance constraints (e.g., "Any rules I should follow?").
- [ ] AC4: After the conversation ends, TAIM confirms what was configured in a short summary (provider, preferences, compliance notes).
- [ ] AC5: All inputs from the onboarding conversation are persisted: provider config in `taim-vault/config/providers.yaml`, user preferences as a warm memory entry in `taim-vault/users/{name}/memory/`.
- [ ] AC6: Onboarding can be re-run via chat ("Let's redo the setup") or CLI (`taim onboarding`).
- [ ] AC7: If the user skips a question, TAIM applies the appropriate smart default without blocking.

**Related API:** `POST /api/setup/init`, `POST /api/setup/provider`. Related UX: Section 7, Journey 1 and Onboarding Flow.
**Priority:** P0

---

#### US-1.2: Natural Language Task Request
**As a** user **I want** to describe a task in plain language **so that** TAIM understands what I need and proposes a plan — without me knowing anything about agents or YAML.

**Acceptance Criteria:**
- [ ] AC1: The user can type a multi-sentence task description and TAIM returns a proposed plan within 10 seconds.
- [ ] AC2: The plan includes: the team composition (agent roles, count), an estimated time, and an estimated token cost.
- [ ] AC3: TAIM asks a follow-up question only if genuinely critical information is missing (e.g., no API key configured, no target defined at all).
- [ ] AC4: The user can confirm the plan with a natural response ("yes", "go ahead", "sounds good") or a variant.
- [ ] AC5: TAIM does not expose agent YAML, model names, or routing decisions to the user unless explicitly asked.

**Related API:** WebSocket `plan_proposed` event. Related UX: Section 7, Journey 2 and 3.
**Priority:** P0

---

#### US-1.3: Smart Defaults Engine
**As a** user **I want** TAIM to fill in all execution parameters I haven't specified **so that** I can give a minimal request and still get a reasonable result.

**Acceptance Criteria:**
- [ ] AC1: Smart defaults are loaded from `taim-vault/config/defaults.yaml` at startup.
- [ ] AC2: Defaults cover at minimum: model tier selection, team size estimate, iteration count (2–3), time limit (proportional to complexity estimate), and output format.
- [ ] AC3: Any default applied is internally logged (not surfaced to user unless asked).
- [ ] AC4: A user can override any default in natural language mid-conversation ("use the cheapest model", "just one researcher", "max 2 hours").
- [ ] AC5: User-specific overrides are persisted as warm memory entries so future tasks apply them automatically.

**Related architecture:** AD-2 (Stage 2 applies defaults), AD-5 (warm memory stores overrides).
**Priority:** P0

---

#### US-1.4: Inline Constraint Setting via Chat
**As a** user **I want** to set constraints (time limits, budget limits) directly in my task request or as a follow-up **so that** the team doesn't overrun my limits.

**Acceptance Criteria:**
- [ ] AC1: Time constraints in natural language ("max 3 hours", "finish by end of day") are parsed and converted to seconds/timestamps for the Heartbeat Manager.
- [ ] AC2: Budget constraints in natural language ("not more than 5 Euro", "under $10") are parsed and passed to the Router as token budget.
- [ ] AC3: If limits are set, TAIM confirms them: "Limits set: 3 hours max, €5 max. Starting now."
- [ ] AC4: The system proactively sends a warning via WebSocket when 80% of the time or token budget is reached.
- [ ] AC5: When a limit is reached, execution stops gracefully (current agent completes its response, then stops) and the user is informed.

**Related API:** WebSocket `budget_warning` event. Related UX: Section 7, Journey 4.
**Priority:** P0

---

#### US-1.5: Conversation History Continuity
**As a** user **I want** TAIM to remember what we discussed earlier in the session and across sessions **so that** I don't have to re-explain context.

**Acceptance Criteria:**
- [ ] AC1: Within a session, the last 20 messages are always available in hot memory and used by the Intent Interpreter for context.
- [ ] AC2: Messages beyond the 20-message window are summarized by a Tier 3 model call and stored as a session summary in warm memory.
- [ ] AC3: At session start, TAIM loads the previous session summary and incorporates it into the first user interaction if relevant.
- [ ] AC4: The user can ask "What did we discuss last time?" and TAIM can answer from warm memory.
- [ ] AC5: Chat history is persisted in the SQLite `session_state` table and survives server restarts.

**Related architecture:** AD-11 (sliding window + summary). **Related API:** `GET /api/chat/sessions/{session_id}/history`.
**Priority:** P1

---

### Epic 2: Intent Interpretation

#### US-2.1: Stage 1 — Quick Intent Classification
**As the** system **I want** to classify incoming user messages into intent categories using a cheap Tier 3 model call **so that** simple messages (confirmations, status queries) do not incur Tier 2 model costs.

**Acceptance Criteria:**
- [ ] AC1: Stage 1 classifies messages into one of: `new_task`, `confirmation`, `follow_up`, `status_query`, `configuration`, `stop_command`, `onboarding_response`.
- [ ] AC2: Stage 1 uses a Tier 3 model (max 100 tokens input + output combined per call).
- [ ] AC3: Messages classified as `confirmation`, `status_query`, `stop_command`, or `onboarding_response` are handled directly without invoking Stage 2.
- [ ] AC4: Only `new_task`, `configuration`, and ambiguous `follow_up` messages are passed to Stage 2.
- [ ] AC5: Stage 1 uses a prompt loaded from `taim-vault/system/prompts/intent-classifier.yaml`.
- [ ] AC6: Classification result and token cost are logged to `token_tracking` in SQLite.

**Related architecture:** AD-2 (two-stage intent). **Related models:** `IntentCategory`, `IntentClassification`.
**Priority:** P0

---

#### US-2.2: Stage 2 — Deep Task Understanding
**As the** system **I want** to deeply parse complex user requests using a Tier 2 model **so that** I can extract a structured task command with all necessary parameters.

**Acceptance Criteria:**
- [ ] AC1: Stage 2 outputs a structured JSON object containing: `task_type`, `objective`, `parameters`, `constraints` (time/budget), `missing_info` (list of unknowns), `suggested_team` (optional).
- [ ] AC2: Stage 2 loads the user's warm memory entries (preferences, past task patterns) and includes them as context before calling the LLM.
- [ ] AC3: If `missing_info` is non-empty, Stage 2 generates a single targeted follow-up question (not a list of questions).
- [ ] AC4: Stage 2 uses a prompt loaded from `taim-vault/system/prompts/intent-interpreter.yaml`.
- [ ] AC5: Stage 2 is only invoked when Stage 1 routes to it — never called for simple messages.
- [ ] AC6: The output structured command is passed to the Orchestrator, not shown to the user.

**Related models:** `IntentResult`, `TaskConstraints`.
**Priority:** P0

---

#### US-2.3: Stop and Cancel Commands
**As a** user **I want** to stop a running team or task at any time using natural language **so that** I have immediate control over what the system is doing.

**Acceptance Criteria:**
- [ ] AC1: Messages like "stop", "cancel", "halt the team", "enough, stop now" are classified as `stop_command` in Stage 1.
- [ ] AC2: On receiving a stop command, all active agents for the user's current team transition to `DONE` state after completing their current LLM call (no mid-stream abort).
- [ ] AC3: TAIM confirms the stop: "Team stopped. Here's what was completed so far: [summary]."
- [ ] AC4: Any partial results are returned to the user rather than discarded.
- [ ] AC5: Stop commands take effect within one Heartbeat interval (default 30 seconds).

**Related API:** WebSocket `stop` message (client→server). Related UX: Section 7, Journey 6.
**Priority:** P0

---

#### US-2.4: Status Query Handling
**As a** user **I want** to ask for the current status of my running team in plain language **so that** I can understand what is happening without navigating to a separate view.

**Acceptance Criteria:**
- [ ] AC1: Messages like "what's happening?", "how far along are you?", "status?" are classified as `status_query` and handled without Stage 2.
- [ ] AC2: The response lists active agents with their current state (PLANNING/EXECUTING/REVIEWING/ITERATING/WAITING/DONE/FAILED), current iteration, and estimated remaining time.
- [ ] AC3: The response includes current token usage and approximate cost so far.
- [ ] AC4: Status responses are generated without an LLM call — data comes from the task state table and is formatted as text.
- [ ] AC5: Response latency for status queries is under 500ms.

**Related architecture:** AD-3 (state machines), AD-8 (SQLite state). Related NFR: NFR-01.
**Priority:** P1

---

### Epic 3: Agent Management

#### US-3.1: Built-in Agent Definitions
**As a** user **I want** TAIM to ship with ready-to-use agent definitions **so that** I can start immediately without defining any agents myself.

**Acceptance Criteria:**
- [ ] AC1: Five built-in agents exist as YAML files in `taim-vault/agents/`: `researcher`, `coder`, `reviewer`, `writer`, `analyst`.
- [ ] AC2: Each agent definition includes: `name`, `description`, `model_preference` (ordered list), `skills`, `max_iterations`, and `requires_approval_for` (list of action types).
- [ ] AC3: Agent definitions are valid and loadable by the Agent Registry on server startup without errors.
- [ ] AC4: Each agent has a corresponding prompt file in `taim-vault/system/prompts/agents/` for each state (planning, executing, reviewing, iterating).
- [ ] AC5: The Team Composer can select and instantiate any built-in agent without any user configuration.

****Related API:** `GET /api/agents`. **Related models:** `Agent`.
**Priority:** P0

---

#### US-3.2: Agent Registry — Load and Query
**As the** system **I want** a centralized Agent Registry that loads all agent definitions at startup and provides query capabilities **so that** the Team Composer can find suitable agents for any task.

**Acceptance Criteria:**
- [ ] AC1: The Agent Registry scans `taim-vault/agents/` at server startup and loads all `.yaml` files into memory.
- [ ] AC2: Registry exposes: `get_agent(name)`, `list_agents()`, `find_agents_by_skill(skill)`.
- [ ] AC3: Invalid YAML files in the agents directory are logged as warnings but do not prevent server startup.
- [ ] AC4: A REST endpoint `GET /api/agents` returns the list of available agents with name and description.
- [ ] AC5: The registry reloads if the agents directory is modified while the server is running (file watch or manual reload trigger).

**Related API:** `GET /api/agents`, `GET /api/agents/{agent_name}`.
**Priority:** P0

---

#### US-3.3: Power User — Define a Custom Agent via YAML
**As a** power user **I want** to create a custom agent by writing a YAML file in `taim-vault/agents/` **so that** I can extend the system with domain-specific roles.

**Acceptance Criteria:**
- [ ] AC1: Placing a valid agent YAML file in `taim-vault/agents/` and reloading the registry makes the agent available to the Team Composer.
- [ ] AC2: The YAML schema is documented with inline comments in the built-in agent files.
- [ ] AC3: An invalid YAML file generates a clear validation error message (field, expected type, got value) logged to the server log.
- [ ] AC4: The CLI command `taim agent list` displays all registered agents including custom ones.
- [ ] AC5: Custom agents can be selected explicitly via chat: "Use my 'data-engineer' agent for this task."

**Priority:** P1

---

#### US-3.4: Agent State Machine Execution
**As the** system **I want** each executing agent to run as an explicit state machine **so that** its status is always debuggable, controllable, and resumable.

**Acceptance Criteria:**
- [ ] AC1: Agent states are: `PLANNING`, `EXECUTING`, `REVIEWING`, `ITERATING`, `WAITING`, `DONE`, `FAILED`.
- [ ] AC2: Each state transition emits a `agent_state` WebSocket event with the agent name and new state.
- [ ] AC3: Agent state is serialized to the `task_state` SQLite table after every transition.
- [ ] AC4: If the server restarts while agents are running, active agent states are restored from SQLite and execution resumes from the last saved state.
- [ ] AC5: Each state uses a distinct prompt loaded from the vault (`planning.yaml`, `executing.yaml`, `reviewing.yaml`, `iterating.yaml`).
- [ ] AC6: Transition from `REVIEWING` to `ITERATING` only happens if the review prompt output signals quality below threshold and the max iteration count has not been reached.
- [ ] AC7: Agents never exceed their configured `max_iterations`; after the limit they transition to `DONE` with their current result.

**Related architecture:** AD-3 (state machines). **Related models:** `AgentStateEnum`, `AgentState`.
**Priority:** P0

---

#### US-3.5: Approval Gate — User Confirmation Before Sensitive Actions
**As a** user **I want** TAIM to pause and ask for my approval before an agent takes a potentially destructive or sensitive action **so that** I always have final control.

**Acceptance Criteria:**
- [ ] AC1: Each agent definition's `requires_approval_for` list defines which action types trigger an approval gate.
- [ ] AC2: When an agent reaches an approval-required action, it transitions to `WAITING` state and sends a `question` WebSocket event describing the action and asking for confirmation.
- [ ] AC3: Execution is paused until the user responds with an approval (`approved: true`) or rejection (`approved: false`).
- [ ] AC4: On approval, the agent transitions back to `EXECUTING`. On rejection, it transitions to `DONE` and returns whatever it had so far.
- [ ] AC5: The approval gate timeout defaults to 30 minutes; after that, the agent transitions to `DONE` without taking the action and informs the user.

**Related API:** WebSocket `question` event (server→client), `approval` message (client→server). Related UX: Section 7, Journey 5.
**Priority:** P1

---

### Epic 4: Team Composition & Orchestration

#### US-4.1: Automatic Team Composition from Task Description
**As a** user **I want** TAIM to automatically select the right agents for my task **so that** I never have to think about which roles are needed.

**Acceptance Criteria:**
- [ ] AC1: The Team Composer receives the structured task command from the Intent Interpreter and selects agents from the registry.
- [ ] AC2: For a research task, the composer selects at minimum a researcher and an analyst.
- [ ] AC3: For a code task, the composer selects at minimum a coder and a reviewer.
- [ ] AC4: For a writing task, the composer selects at minimum a researcher and a writer.
- [ ] AC5: The proposed team is presented to the user in a `plan_proposed` WebSocket event for confirmation before execution starts.
- [ ] AC6: Team composition uses the prompt at `taim-vault/system/prompts/team-composer.yaml`.

**Related API:** `POST /api/teams`. Related models:** `TeamPlan`, `TeamAgentSlot`.
**Priority:** P0

---

#### US-4.2: Orchestration Pattern Auto-Selection
**As the** system **I want** the Team Composer to auto-select the appropriate orchestration pattern (Sequential, Parallel, Pipeline, Hierarchical) based on task analysis **so that** users get optimal performance without configuring it.

**Acceptance Criteria:**
- [ ] AC1: Multi-source research tasks default to a Parallel + Sequential pattern (multiple researchers then analyst).
- [ ] AC2: Code tasks default to Sequential (plan → code → review).
- [ ] AC3: Single-topic tasks default to Pipeline (research → analyze → write).
- [ ] AC4: Single-agent tasks skip team orchestration entirely and execute the agent directly.
- [ ] AC5: The selected pattern is logged but not shown to the user unless they ask.
- [ ] AC6: A power user can override the pattern in the team YAML file.

**Related architecture:** AD-7 (orchestration patterns). Related models:** `OrchestrationPattern`.
**Priority:** P1

---

#### US-4.3: Team Plan Confirmation Flow
**As a** user **I want** to see and explicitly confirm the proposed team plan before execution starts **so that** I can adjust the scope or budget if needed.

**Acceptance Criteria:**
- [ ] AC1: The `plan_proposed` WebSocket event includes: agent roles and counts, orchestration pattern, estimated time, estimated token cost in user currency.
- [ ] AC2: The user can confirm with a natural affirmation or respond with adjustments ("but skip the reviewer" or "make it faster").
- [ ] AC3: If the user adjusts the plan, the Team Composer revises and re-proposes before starting.
- [ ] AC4: After at most 2 rounds of revision, TAIM executes with the latest confirmed plan or the user's latest instruction.
- [ ] AC5: No agents are started until the user has confirmed the plan.

**Related API:** WebSocket `plan_proposed` event (server→client), `approval` message (client→server). Related UX: Section 7, Journey 5.
**Priority:** P0

---

#### US-4.4: Heartbeat Manager — Time Limit Enforcement
**As a** user **I want** the Heartbeat Manager to enforce time limits and detect stuck agents **so that** execution never runs beyond what I authorized.

**Acceptance Criteria:**
- [ ] AC1: The Heartbeat Manager checks active agents at a configurable interval (default: 30 seconds).
- [ ] AC2: If an agent has not produced a state transition within the timeout threshold (default: 120 seconds), it is marked as stuck and a warning is sent to the user.
- [ ] AC3: If the team-level time limit is reached, all agents are gracefully stopped (complete current LLM call, then transition to DONE).
- [ ] AC4: At 80% of the time limit, a `budget_warning` WebSocket event is sent to the user.
- [ ] AC5: Heartbeat state (last check time, agent status map) is stored in the `session_state` SQLite table.
- [ ] AC6: Heartbeat interval and timeout values are configurable in `taim-vault/config/taim.yaml`.

**Related architecture:** AD-3 (state machines), AD-8 (SQLite). Related models:** `TeamConfig`.
**Priority:** P0

---

#### US-4.5: Task Manager — Internal Task Lifecycle
**As the** system **I want** a Task Manager to track the lifecycle of all task units **so that** state is consistent and recoverable across restarts.

**Acceptance Criteria:**
- [ ] AC1: A task record is created in the `task_state` SQLite table when a user-confirmed plan is executed.
- [ ] AC2: Task record contains: `task_id`, `team_id`, `status` (running/completed/stopped/failed), `created_at`, `completed_at`, `agent_states` (JSON), `token_total`, `cost_total`.
- [ ] AC3: Tasks are updated transactionally (state change + token count atomically).
- [ ] AC4: Completed task records are retained (not deleted) for the Stats and Audit views.
- [ ] AC5: A REST endpoint `GET /api/tasks` returns the list of recent tasks with their status.

**Related architecture:** AD-8 (SQLite). Related models:** `Task`, `TaskStatus`.
**Priority:** P0

---

### Epic 5: Agent Execution Engine

#### US-5.1: Per-State Prompt Loading
**As the** system **I want** each agent state to load its own dedicated prompt from the vault **so that** agents get focused, optimized instructions appropriate for what they are doing.

**Acceptance Criteria:**
- [ ] AC1: The executor loads prompts by composing the path: `taim-vault/system/prompts/agents/{agent_name}/{state}.yaml`.
- [ ] AC2: If a state-specific prompt doesn't exist for an agent, the executor falls back to a generic state prompt (`taim-vault/system/prompts/agents/default/{state}.yaml`).
- [ ] AC3: Prompts support variable substitution: `{task_description}`, `{user_preferences}`, `{iteration_count}`, `{previous_result}`.
- [ ] AC4: A missing prompt file (both specific and fallback) causes the agent to transition to `FAILED` with a clear error message.
- [ ] AC5: Prompt loading is tested with a unit test that mocks the vault filesystem.

**Related architecture:** AD-1 (prompts as vault files). Related stories:** US-11.2 (PromptLoader).
**Priority:** P0

---

#### US-5.2: Context Assembly — Token-Budgeted
**As the** system **I want** the Context Assembler to build an agent's context within a token budget, prioritizing by relevance **so that** context costs are predictable and focused.

**Acceptance Criteria:**
- [ ] AC1: Context is assembled in priority order: task description → active constraints → relevant warm memory entries → few-shot examples from prompt cache → team context.
- [ ] AC2: Token budget defaults: Tier 1 = 4000 tokens, Tier 2 = 2000 tokens, Tier 3 = 800 tokens.
- [ ] AC3: Memory entries are scored for relevance by keyword and tag matching against the task description and agent role. Entries scoring below threshold are excluded.
- [ ] AC4: The assembler never exceeds the budget; it stops adding entries once the budget is reached.
- [ ] AC5: No embeddings, vector search, or similarity computation is used — keyword/tag matching only.
- [ ] AC6: The final assembled context token count is logged alongside the agent run.

**Related architecture:** AD-4 (token-budgeted context assembly), AD-5 (three-temperature memory).
**Priority:** P0

---

#### US-5.3: Inter-Agent Result Passing
**As the** system **I want** completed agent results to be available as context for subsequent agents in the team **so that** agents can build on each other's work.

**Acceptance Criteria:**
- [ ] AC1: In Sequential and Pipeline patterns, the output of agent N is stored in the `task_state` table and made available to agent N+1 as part of its context assembly (if budget allows).
- [ ] AC2: In Parallel patterns, all parallel agent outputs are collected before being passed to the next sequential stage.
- [ ] AC3: Agent outputs are truncated to a configurable token limit (default: 1000 tokens) when passed as context to prevent budget overflow.
- [ ] AC4: The Context Assembler tracks which agent output was passed and logs it.

**Related architecture:** AD-7 (orchestration patterns).
**Priority:** P0

---

#### US-5.4: Agent Run Logging
**As the** system **I want** every agent run logged to SQLite **so that** the audit trail is complete and the stats view has accurate data.

**Acceptance Criteria:**
- [ ] AC1: An `agent_runs` record is created at agent start with: `run_id`, `agent_name`, `task_id`, `team_id`, `state_transitions` (JSON list), `prompt_tokens`, `completion_tokens`, `cost`, `started_at`, `completed_at`, `model_used`.
- [ ] AC2: The record is updated at each state transition and on completion.
- [ ] AC3: `model_used` records the actual model that responded (not just the preference), capturing any failovers.
- [ ] AC4: Agent runs are linked to their parent task via `task_id`.

**Related models:** `AgentRun`. Related architecture:** AD-8 (SQLite).
**Priority:** P0

---

### Epic 6: LLM Router & Failover

#### US-6.1: Multi-Provider Configuration
**As a** user **I want** to configure multiple LLM providers in `providers.yaml` or via onboarding conversation **so that** TAIM can use different providers and fall back if one is unavailable.

**Acceptance Criteria:**
- [ ] AC1: `taim-vault/config/providers.yaml` accepts a list of providers, each with: `name`, `api_key_env` (or inline key), `models` (ordered list), `priority`, `monthly_budget` (optional).
- [ ] AC2: The Router loads and validates the provider config at startup. Missing or invalid configs log a warning but don't crash the server.
- [ ] AC3: Ollama (local) is supported as a provider with `host` config instead of API key.
- [ ] AC4: If no providers are configured, the server starts in a degraded mode and returns a clear error when any LLM call is attempted.
- [ ] AC5: The onboarding conversation generates a valid `providers.yaml` from user inputs.

**Related API:** `POST /api/setup/provider`. Related models:** `ProviderConfig`.
**Priority:** P0

---

#### US-6.2: Model Tiering — Automatic Model Selection
**As the** system **I want** to automatically select the appropriate model tier based on task complexity **so that** the right capability is used at the right cost.

**Acceptance Criteria:**
- [ ] AC1: Three tiers are defined: Tier 1 (premium — complex reasoning, strategy), Tier 2 (standard — code gen, text processing, analysis), Tier 3 (economy — classification, formatting, routing).
- [ ] AC2: The Intent Interpreter Stage 1 always uses Tier 3. Stage 2 always uses Tier 2.
- [ ] AC3: The Team Composer assigns a tier to each agent based on its role and the task complexity.
- [ ] AC4: Tier definitions map to actual models in `providers.yaml` (e.g., Tier 1 → `claude-sonnet-4`, Tier 2 → `claude-haiku-4-5`).
- [ ] AC5: A power user can override the tier for a specific agent in its YAML definition or via chat.

**Related models:** `ModelTierEnum`. Related architecture:** AD-2 (two-stage intent).
**Priority:** P0

---

#### US-6.3: Intelligent Failover Between Providers
**As a** user **I want** TAIM to automatically switch to a backup provider if the primary fails **so that** tasks continue without interruption.

**Acceptance Criteria:**
- [ ] AC1: On HTTP 429 (rate limit), the Router applies exponential backoff on the same provider (2 retries, max 4 seconds wait) before failing over.
- [ ] AC2: On connection error or timeout, the Router immediately fails over to the next provider in priority order.
- [ ] AC3: On content safety filter rejection, the Router retries with a softened prompt once on the same provider, then fails over.
- [ ] AC4: On bad format response (not matching expected JSON structure), the Router retries with a format reminder appended, up to 1 retry.
- [ ] AC5: Maximum 3 total attempts per LLM call (across all retries and failovers combined).
- [ ] AC6: If all providers fail, the agent transitions to `FAILED` and the user receives an `error` WebSocket event with a human-readable explanation and suggestion to check API keys.
- [ ] AC7: Every failover event is logged to `agent_runs` with the reason.

**Related architecture:** AD-10 (error-type-aware handling). Related UX: Section 7, Journey 8.
**Priority:** P0

---

#### US-6.4: Monthly Budget Enforcement Per Provider
**As a** user **I want** each provider to have an optional monthly budget cap **so that** I never accidentally exceed my intended spend.

**Acceptance Criteria:**
- [ ] AC1: `monthly_budget` in `providers.yaml` sets the soft cap in the user's configured currency.
- [ ] AC2: The Router queries the `token_tracking` table to sum costs for the current calendar month before each call.
- [ ] AC3: If a provider's monthly budget would be exceeded by the call, the Router skips it and moves to the next provider.
- [ ] AC4: When a provider's budget is within 10% of the cap, a `budget_warning` event is sent once per session.
- [ ] AC5: Budget tracking works even when the server restarts (persisted in SQLite, not in-memory).

**Related API:** `GET /api/stats/costs`.
**Priority:** P1

---

### Epic 7: Memory System (Brain)

#### US-7.1: Vault Directory Initialization
**As a** user (or the system on first start) **I want** the TAIM Vault to be automatically created with the correct directory structure **so that** no manual setup is required.

**Acceptance Criteria:**
- [ ] AC1: On first startup, if `taim-vault/` does not exist, the server creates the full directory structure as specified in the project spec.
- [ ] AC2: Default config files are written: `taim-vault/config/taim.yaml`, `providers.yaml`, `defaults.yaml` with commented-out example values.
- [ ] AC3: Built-in agent YAML files are copied into `taim-vault/agents/`.
- [ ] AC4: A `users/default/` namespace is created with an empty `INDEX.md`.
- [ ] AC5: Vault initialization is idempotent — running it again on an existing vault changes nothing.
- [ ] AC6: The vault path is configurable via an environment variable `TAIM_VAULT_PATH`.

**Related API:** `POST /api/setup/init`. Related models:** `VaultConfig`.
**Priority:** P0

---

#### US-7.2: Warm Memory — User Preferences Persistence
**As the** system **I want** to persist user preferences as structured Markdown notes with frontmatter **so that** they survive across sessions and are used by the Context Assembler.

**Acceptance Criteria:**
- [ ] AC1: Preferences are stored as Markdown files under `taim-vault/users/{username}/memory/preferences.md` with YAML frontmatter including: `title`, `category`, `tags`, `created`, `updated`.
- [ ] AC2: The `INDEX.md` in the user's namespace is updated every time a new memory entry is created or modified.
- [ ] AC3: Memory entries written during onboarding (e.g., "prefers TypeScript", "DSGVO compliance required") are readable by the Context Assembler on the next session.
- [ ] AC4: The `VaultOps` class provides: `write_memory(user, entry)`, `read_memory(user, filename)`, `update_index(user)`, `scan_index(user)`.
- [ ] AC5: No Obsidian dependency — all operations use standard Python file I/O.

**Related architecture:** AD-5 (three-temperature memory). Related models:** `MemoryEntry`, `MemoryIndex`.
**Priority:** P0

---

#### US-7.3: Hot Memory — In-Session Context
**As the** system **I want** to maintain the current session's messages and active task context in an in-memory structure **so that** the Intent Interpreter has immediate access to recent context without disk reads.

**Acceptance Criteria:**
- [ ] AC1: Hot memory is an in-memory dictionary keyed by session ID, containing: last 20 messages, current task context, active team state.
- [ ] AC2: Hot memory is initialized on WebSocket connection and cleared on disconnect.
- [ ] AC3: The Intent Interpreter reads from hot memory before loading any warm entries.
- [ ] AC4: When hot memory grows beyond 20 messages, the oldest messages trigger a summarization job (Tier 3 call) that compresses them into a warm memory entry.
- [ ] AC5: If the server restarts mid-session, hot memory is rebuilt from the `session_state` SQLite table (last 20 messages).

**Related architecture:** AD-11 (sliding window + summary).
**Priority:** P0

---

#### US-7.4: INDEX.md — Lightweight Retrieval Index
**As the** system **I want** to use an `INDEX.md` file as a fast, human-readable catalog of all memory entries **so that** relevant entries can be found without loading all files.

**Acceptance Criteria:**
- [ ] AC1: `INDEX.md` in a user's memory namespace lists all memory entries with: filename, one-line summary, tags (comma-separated), and last-updated date.
- [ ] AC2: The Context Assembler scans `INDEX.md` to find relevant entries by tag and keyword matching against the current task.
- [ ] AC3: Only entries whose tags have at least one match with the task description or agent role are fully loaded.
- [ ] AC4: Scanning `INDEX.md` costs zero LLM calls — it is pure string matching in Python.
- [ ] AC5: `INDEX.md` is regenerated correctly if entries are added, modified, or deleted.

**Related architecture:** AD-5 (three-temperature memory). Related NFR:** NFR-11 (INDEX.md scan < 200ms for 500 entries).
**Priority:** P0

---

#### US-7.5: Agent Memory Namespace Isolation
**As the** system **I want** each agent to have its own isolated memory namespace **so that** agent-specific learned patterns don't pollute user or other agent memory.

**Acceptance Criteria:**
- [ ] AC1: Agent memory is stored under `taim-vault/users/{username}/agents/{agent_name}/memory/`.
- [ ] AC2: Agent memory entries follow the same Markdown+frontmatter format as user memory entries.
- [ ] AC3: The Context Assembler loads agent memory (within budget) alongside user memory for context assembly.
- [ ] AC4: Agent memory written during one task is available to the same agent in future tasks.
- [ ] AC5: Agent memory is not accessible cross-user (no shared agent memory in Phase 1).

**Priority:** P1

---

### Epic 8: Token Tracking & Cost Display

#### US-8.1: Per-Call Token Tracking
**As the** system **I want** every LLM API call to be logged with its token counts and cost **so that** all downstream reporting is accurate.

**Acceptance Criteria:**
- [ ] AC1: After every successful LLM response, a record is inserted into the `token_tracking` SQLite table with: `call_id`, `agent_run_id`, `task_id`, `model`, `provider`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `timestamp`.
- [ ] AC2: Cost is calculated from a model-to-price mapping stored in `taim-vault/config/providers.yaml` (or a fallback default price table in code).
- [ ] AC3: Failed LLM calls (where no tokens were consumed) are not tracked in `token_tracking` but are logged in the server log.
- [ ] AC4: Token tracking writes are atomic with the associated agent state transition to prevent double-counting.

**Related architecture:** AD-8 (SQLite). Related models:** `TokenUsage`.
**Priority:** P0

---

#### US-8.2: Real-Time Cost Display in Chat
**As a** user **I want** to see the running token cost of my current task in the chat UI **so that** I am never surprised by the bill.

**Acceptance Criteria:**
- [ ] AC1: Every `agent_progress` and `agent_completed` WebSocket event includes `tokens_used` and `cost` in its metadata.
- [ ] AC2: The status bar in the Dashboard displays the cumulative cost for the current task, updated in real time as events arrive.
- [ ] AC3: Cost is displayed in the user's configured currency (default: USD), formatted as a human-readable value (e.g., "$0.42" not "0.421837").
- [ ] AC4: When the task completes, a final `result` event includes the total cost and total tokens for the entire task.

**Related architecture:** AD-6 (WebSocket events). Related UX:** Section 7, StatusBar component.
**Priority:** P0

---

#### US-8.3: Monthly Usage Summary
**As a** user **I want** to see a summary of my monthly token usage and costs on the Stats page **so that** I can understand my spending patterns.

**Acceptance Criteria:**
- [ ] AC1: The Stats page displays: total cost current month, total tokens current month, number of tasks run, average cost per task.
- [ ] AC2: Stats are broken down by provider (e.g., "Anthropic: $12.40, OpenAI: $3.20").
- [ ] AC3: A `GET /api/stats/monthly` endpoint returns this data as JSON.
- [ ] AC4: Stats queries run against the SQLite `token_tracking` table using date filtering.
- [ ] AC5: Stats page loads in under 1 second for up to 10,000 tracking records.

**Related API:** `GET /api/stats/tokens`, `GET /api/stats/costs`.
**Priority:** P1

---

### Epic 9: Dashboard (Frontend)

#### US-9.1: Chat as Primary Dashboard View
**As a** user **I want** the chat interface to be the dominant view when I open the Dashboard **so that** natural language is obviously the primary way to interact with TAIM.

**Acceptance Criteria:**
- [ ] AC1: The Chat view occupies the main content area (minimum 70% of screen width) on all screen sizes above 768px.
- [ ] AC2: The navigation sidebar lists: Chat, Teams, Agents, Stats (Memory, Rules, Audit deferred to Phase 3).
- [ ] AC3: The Dashboard loads within 2 seconds on a local server.
- [ ] AC4: The chat input is focused by default on page load.
- [ ] AC5: New WebSocket messages scroll the chat area into view automatically.

**Related UX:** Section 7, Chat view layout.
**Priority:** P0

---

#### US-9.2: Real-Time Agent Status in Chat
**As a** user **I want** to see live status updates from my running agents appear in the chat conversation **so that** I feel like I'm watching a team work rather than waiting for a response.

**Acceptance Criteria:**
- [ ] AC1: Each `agent_started` event renders a status bubble in the chat (e.g., "Researcher started — PLANNING").
- [ ] AC2: `agent_state` transition events update the existing bubble for that agent (e.g., "Researcher — EXECUTING iteration 1/3").
- [ ] AC3: `agent_progress` events render inline progress text (e.g., "Researcher: Analyzing competitor A...").
- [ ] AC4: `agent_completed` events render a completion bubble with a one-line summary.
- [ ] AC5: Status bubbles are visually distinct from user and TAIM conversational messages.
- [ ] AC6: If 3 or more agents are active, status bubbles are collapsed by default with an expand toggle.

**Related architecture:** AD-6 (WebSocket events). Related UX:** Section 7, Context Panel / Agent Cards.
**Priority:** P0

---

#### US-9.3: Plan Approval UI Flow
**As a** user **I want** the Dashboard to present the proposed plan visually and let me approve or adjust it with a clear UI interaction **so that** the confirmation step is obvious and frictionless.

**Acceptance Criteria:**
- [ ] AC1: A `plan_proposed` WebSocket event renders a distinct "Plan Card" in the chat with: agent roles listed, estimated time and cost, and two buttons: "Approve" and "Adjust".
- [ ] AC2: Clicking "Approve" sends a WebSocket `approval` message with `approved: true` and the plan card changes to a confirmed state.
- [ ] AC3: Clicking "Adjust" focuses the chat input and pre-fills it with "Change the plan: ".
- [ ] AC4: The user can also approve or adjust by typing in the chat input (no button click required).
- [ ] AC5: The plan card is non-interactive after approval to prevent double-submission.

**Related UX:** Section 7, PlanCard component, Journey 5.
**Priority:** P0

---

#### US-9.4: Status Bar
**As a** user **I want** a persistent status bar at the bottom of the Dashboard showing the number of active agents, current task cost, and elapsed time **so that** I always have operational context visible.

**Acceptance Criteria:**
- [ ] AC1: The status bar shows: number of active agents, cumulative cost of current task (or session total if no task running), elapsed time of current task.
- [ ] AC2: All three values update in real time via WebSocket events without requiring page interaction.
- [ ] AC3: When no task is running, the status bar shows "No active task" and the session total cost.
- [ ] AC4: The status bar is always visible — it does not scroll off screen.

**Related UX:** Section 7, StatusBar component and state table.
**Priority:** P0

---

#### US-9.5: Teams View
**As a** user (or power user) **I want** a Teams view that shows active and recently completed teams **so that** I can monitor running teams and review past results.

**Acceptance Criteria:**
- [ ] AC1: The Teams view lists active teams with: team name, agent count, status, elapsed time, current cost.
- [ ] AC2: The Teams view lists recently completed teams (last 10) with: team name, completion time, total cost, outcome (completed/stopped/failed).
- [ ] AC3: Clicking an active team shows the agent states and their current iteration.
- [ ] AC4: A "Stop Team" button on an active team sends a stop command equivalent to typing "stop" in the chat.
- [ ] AC5: Data is loaded from `GET /api/teams` and updated via WebSocket events.

**Related API:** `GET /api/teams`, `POST /api/teams/{team_id}/stop`.
**Priority:** P1

---

#### US-9.6: Agents View
**As a** power user **I want** an Agents view that lists all registered agents with their definitions **so that** I can understand what agents are available and inspect their configuration.

**Acceptance Criteria:**
- [ ] AC1: The Agents view shows all agents from the registry: name, description, model preference, skills.
- [ ] AC2: Clicking an agent shows its full YAML definition in a read-only code view.
- [ ] AC3: A link or instruction is shown for how to add a custom agent (pointing to the vault agents directory).
- [ ] AC4: Data is loaded from `GET /api/agents`.

**Related API:** `GET /api/agents`, `GET /api/agents/{agent_name}`.
**Priority:** P2

---

#### US-9.7: Stats View
**As a** user **I want** a Stats view showing my token usage and costs **so that** I can track my spending and usage patterns.

**Acceptance Criteria:**
- [ ] AC1: Stats view shows the monthly summary (total cost, total tokens, task count, average cost/task).
- [ ] AC2: Stats view shows a breakdown by provider.
- [ ] AC3: Stats view shows the 10 most recent tasks with their cost and duration.
- [ ] AC4: All data loads from `GET /api/stats/monthly` and `GET /api/tasks`.

**Related API:** `GET /api/stats/tokens`, `GET /api/stats/costs`.
**Priority:** P1

---

#### US-9.8: WebSocket Connection State Handling
**As a** user **I want** the Dashboard to gracefully handle WebSocket disconnections **so that** my work is not lost and I'm informed if the connection drops.

**Acceptance Criteria:**
- [ ] AC1: A connection indicator (dot or badge) in the UI shows green (connected) or red (disconnected).
- [ ] AC2: On disconnect, the UI attempts automatic reconnection with exponential backoff (5 attempts, max 30 seconds between attempts).
- [ ] AC3: If reconnection succeeds, the chat history is restored from the `session_state` SQLite table and a system message "Connection restored" is shown.
- [ ] AC4: If all reconnection attempts fail, a persistent banner is shown: "Disconnected from TAIM server. Check that the server is running."
- [ ] AC5: Pending messages typed during disconnection are queued and sent on reconnect.

**Related architecture:** AD-6 (WebSocket events). Related NFR:** NFR-10.
**Priority:** P1

---

### Epic 10: CLI (Power Users)

#### US-10.1: CLI — Server Start and Stop
**As a** power user **I want** to start and stop the TAIM server from the command line **so that** I can manage the server process without a launcher or GUI.

**Acceptance Criteria:**
- [ ] AC1: `taim server start` starts the FastAPI server with Uvicorn on the configured host and port (default: `localhost:8000`).
- [ ] AC2: `taim server stop` gracefully shuts down the running server.
- [ ] AC3: `taim server start --port 9000` overrides the default port.
- [ ] AC4: `taim server start --vault /custom/path` overrides the vault path.
- [ ] AC5: Server startup prints the URL to the Dashboard and a brief status summary.

**Priority:** P1

---

#### US-10.2: CLI — Submit a Task
**As a** power user **I want** to submit a task from the command line **so that** I can trigger TAIM without opening the Dashboard.

**Acceptance Criteria:**
- [ ] AC1: `taim task run "Analyze our three main competitors and write a report"` submits the task to the running server.
- [ ] AC2: The CLI streams agent status events to stdout as they arrive (one line per event).
- [ ] AC3: On task completion, the final result is printed to stdout.
- [ ] AC4: `--time-limit 2h` and `--budget 5` flags pass time and budget constraints to the task.
- [ ] AC5: `--no-confirm` flag skips the plan approval step and immediately executes.
- [ ] AC6: Non-zero exit code is returned if the task fails or all providers are unavailable.

**Priority:** P1

---

#### US-10.3: CLI — Agent and Team Management
**As a** power user **I want** to list and inspect agents and teams from the CLI **so that** I can manage the system without opening the Dashboard.

**Acceptance Criteria:**
- [ ] AC1: `taim agent list` lists all registered agents with name and description.
- [ ] AC2: `taim agent show researcher` prints the full YAML definition of the named agent.
- [ ] AC3: `taim team list` lists all team blueprints defined in the vault.
- [ ] AC4: `taim team show {name}` prints the full YAML definition of the named team blueprint.
- [ ] AC5: All CLI output uses Rich for formatted, readable terminal output.

**Priority:** P2

---

#### US-10.4: CLI — Stats Display
**As a** power user **I want** to view token usage stats from the CLI **so that** I can check costs without opening a browser.

**Acceptance Criteria:**
- [ ] AC1: `taim stats` prints the current month's total cost, total tokens, and task count.
- [ ] AC2: `taim stats --breakdown` additionally prints per-provider cost breakdown.
- [ ] AC3: Output is a clean, readable table formatted with Rich.

**Priority:** P2

---

#### US-10.5: CLI — Vault Operations
**As a** power user **I want** CLI commands for basic vault operations **so that** I can inspect and manage the vault from the terminal.

**Acceptance Criteria:**
- [ ] AC1: `taim vault init` creates the vault directory structure (same as server first-start behavior).
- [ ] AC2: `taim vault status` prints the vault path, disk usage, and counts of agents, teams, and memory entries.
- [ ] AC3: `taim vault memory list` lists all warm memory entries for the current user with their tags and last-updated date.

**Priority:** P2

---

### Epic 11: System Setup & Configuration

#### US-11.1: TAIM Server — FastAPI Application with WebSocket
**As a** developer **I want** a FastAPI application with correctly configured REST endpoints and WebSocket support **so that** the Dashboard and CLI can communicate with the backend in real time.

**Acceptance Criteria:**
- [ ] AC1: The server starts with `uvicorn taim.main:app --reload` in development mode.
- [ ] AC2: A WebSocket endpoint is available at `ws://localhost:8000/ws/{session_id}`.
- [ ] AC3: REST endpoints are available under `/api/` with OpenAPI docs auto-generated at `/docs`.
- [ ] AC4: CORS is configured to allow requests from `localhost:*` (configurable for production).
- [ ] AC5: Server startup logs vault path, loaded agents count, and configured providers.
- [ ] AC6: `GET /health` returns `{"status": "ok", "vault_ok": true, "providers": ["anthropic"]}`.

**Priority:** P0

---

#### US-11.2: Prompts as Vault Files — PromptLoader Utility
**As a** developer **I want** a `PromptLoader` utility that reads prompts from vault YAML files and applies variable substitution **so that** no prompt strings are hardcoded in Python code.

**Acceptance Criteria:**
- [ ] AC1: `PromptLoader.load(prompt_name, variables)` reads from `taim-vault/system/prompts/{prompt_name}.yaml` and substitutes all `{variable}` placeholders.
- [ ] AC2: Missing variable substitutions raise a `PromptVariableError` (not silently inserted as `{variable}`).
- [ ] AC3: Missing prompt file raises a `PromptNotFoundError` with the attempted path.
- [ ] AC4: Prompts are cached in memory after first load; cache is invalidated when the vault file is modified.
- [ ] AC5: `PromptLoader` is unit tested with a mock vault filesystem.
- [ ] AC6: All 20+ prompt files required for Phase 1 exist in the vault before any integration tests run.

**Related architecture:** AD-1 (prompts as vault files).
**Priority:** P0

---

#### US-11.3: SQLite Database Initialization
**As the** system **I want** the SQLite database to be automatically initialized with the correct schema on first run **so that** no manual database setup is required.

**Acceptance Criteria:**
- [ ] AC1: On startup, the server checks if `taim-vault/system/state/taim.db` exists. If not, it runs the schema migration to create all tables.
- [ ] AC2: Tables created: `token_tracking`, `task_state`, `session_state`, `agent_runs` with the columns defined in Architecture Decision 8.
- [ ] AC3: SQLite is opened in WAL mode for better concurrent read performance.
- [ ] AC4: Schema migrations are version-controlled in code (a simple integer version in a `schema_version` table).
- [ ] AC5: Existing databases with an older schema version are migrated, not overwritten.

**Related architecture:** AD-8 (SQLite).
**Priority:** P0

---

#### US-11.4: Environment Variable Configuration
**As an** operator **I want** TAIM's key settings to be configurable via environment variables **so that** I can deploy it in different environments without editing files.

**Acceptance Criteria:**
- [ ] AC1: `TAIM_VAULT_PATH` overrides the default vault path.
- [ ] AC2: `TAIM_HOST` and `TAIM_PORT` override server bind address (defaults: `localhost`, `8000`).
- [ ] AC3: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` are read from environment if not in `providers.yaml`.
- [ ] AC4: A `.env` file in the project root is loaded automatically in development mode (via `python-dotenv`).
- [ ] AC5: `taim server start` with `--env-file .env.prod` loads a specific env file.

**Priority:** P1

---

#### US-11.5: Backend Test Coverage
**As a** developer **I want** the core backend logic to have >80% test coverage **so that** the system is reliable and regressions are caught.

**Acceptance Criteria:**
- [ ] AC1: `pytest` runs without errors from the backend directory using `uv run pytest`.
- [ ] AC2: The following modules have individual test files: Intent Interpreter (both stages), Context Assembler, Agent State Machine, Router (tiering + failover), PromptLoader, VaultOps, Token Tracker.
- [ ] AC3: Tests use mocking for LLM calls (no real API calls in unit tests).
- [ ] AC4: Coverage report shows >80% line coverage for `taim/conversation/`, `taim/orchestrator/`, `taim/router/`, `taim/brain/`.
- [ ] AC5: CI-equivalent check: `uv run pytest --cov=taim --cov-report=term-missing` runs cleanly.

**Priority:** P1

---

### Epic 12: Tool Execution, Agent Skills & MCP

#### US-12.1: Tool Execution Framework
**As the** system **I want** a tool execution framework that allows agents to take real actions (search the web, read/write files, call APIs) **so that** agents produce results based on real data, not just LLM-generated text.

**Acceptance Criteria:**
- [ ] AC1: A `ToolExecutor` class in `backend/src/taim/orchestrator/tools.py` manages tool registration, validation, and execution.
- [ ] AC2: Tools are defined as Python functions with a JSON Schema description, matching LiteLLM's function/tool calling format.
- [ ] AC3: During the EXECUTING state, the agent's LLM response may contain `tool_calls`. The executor runs each tool call, collects results, and feeds them back to the LLM in a follow-up message.
- [ ] AC4: Tool execution follows a loop: LLM response → extract tool_calls → execute → feed results back → repeat until LLM responds without tool_calls or max iterations reached.
- [ ] AC5: Every tool execution is logged to the `agent_runs` table: tool name, input parameters (sanitized), output summary, duration_ms, success/failure.
- [ ] AC6: Tool execution errors do not crash the agent — they are returned to the LLM as error messages so it can adapt.
- [ ] AC7: A `tool_execution` WebSocket event is emitted when a tool runs, showing the tool name and a human-readable summary (not raw parameters).

**Related architecture:** AD-3 (state machines — tool calling happens within EXECUTING state).
**Priority:** P0

---

#### US-12.2: Built-in Tools
**As a** user **I want** TAIM to ship with useful built-in tools **so that** agents can actually interact with the real world from day one.

**Acceptance Criteria:**
- [ ] AC1: The following built-in tools are available:
  - `web_search` — Search the web via an API (Tavily, Serper, or SearXNG). Returns top-N results with title, URL, and snippet.
  - `web_fetch` — Fetch a URL and return its text content (HTML stripped to readable text, max 8000 chars).
  - `file_read` — Read a file from the TAIM vault or a configured workspace directory.
  - `file_write` — Write/append to a file in the vault or workspace directory.
  - `vault_memory_read` — Read a specific memory entry by ID from the user's memory.
  - `vault_memory_write` — Write a new memory entry (used by agents to persist learnings).
- [ ] AC2: `web_search` requires a search API key configured via `TAIM_SEARCH_API_KEY` env var. If not configured, the tool is unavailable and agents are informed.
- [ ] AC3: `file_read`/`file_write` are sandboxed — they can only access paths within the TAIM vault or a configured `TAIM_WORKSPACE_PATH`. Attempts to access paths outside the sandbox return an error.
- [ ] AC4: Each built-in tool has a JSON Schema definition stored in `taim-vault/system/tools/` as YAML files.
- [ ] AC5: The Agent Registry knows which tools each agent has access to (from the agent's YAML `tools` field). An agent cannot call a tool not in its definition.

**Related API:** Tool availability shown in `GET /api/agents/{name}` response.
**Priority:** P0

---

#### US-12.3: Agent Skills (Reusable Prompt+Tool Patterns)
**As the** system **I want** agents to have named skills that combine a specialized prompt template with specific tools **so that** complex capabilities are reusable across different agents and tasks.

**Acceptance Criteria:**
- [ ] AC1: Skills are defined as YAML files in `taim-vault/system/skills/`:
  ```yaml
  name: web-research
  description: "Search the web, fetch pages, and summarize findings"
  required_tools: [web_search, web_fetch, file_write]
  prompt_template: |
    You are conducting web research on: {topic}
    Use web_search to find relevant sources, web_fetch to read them,
    and compile your findings into a structured summary.
  output_format: markdown
  ```
- [ ] AC2: An agent's YAML `skills` field references skill names. When the agent enters EXECUTING state, the Context Assembler loads the relevant skill's prompt template and merges it with the agent's base prompt.
- [ ] AC3: Skills are validated at server startup — a skill referencing a non-existent tool logs a warning.
- [ ] AC4: Built-in skills shipped with Phase 1:
  - `web-research` — Search, fetch, summarize from web sources
  - `code-generation` — Write, test, and iterate on code
  - `code-review` — Read code, identify issues, suggest improvements
  - `content-writing` — Write structured documents (reports, articles, summaries)
  - `data-analysis` — Analyze structured data, produce comparisons and insights
- [ ] AC5: The Team Composer considers required skills when selecting agents — an agent is only assigned a role if it has the required skills for that task type.

**Related models:** `Skill`, `AgentSkillConfig`.
**Priority:** P0

---

#### US-12.4: MCP Client Integration
**As a** power user **I want** to connect MCP (Model Context Protocol) servers to TAIM **so that** agents can use external tools and services I have already configured.

**Acceptance Criteria:**
- [ ] AC1: MCP server connections are configured in `taim-vault/config/mcp-servers.yaml`:
  ```yaml
  mcp_servers:
    - name: filesystem
      command: "npx -y @modelcontextprotocol/server-filesystem /path/to/workspace"
      enabled: true
    - name: github
      command: "npx -y @modelcontextprotocol/server-github"
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
      enabled: true
    - name: custom-api
      url: "http://localhost:3001/mcp"
      enabled: true
  ```
- [ ] AC2: TAIM connects to configured MCP servers at startup (command-based via stdio, URL-based via SSE/HTTP).
- [ ] AC3: Tools discovered from MCP servers are automatically registered in the ToolExecutor with their JSON Schema definitions.
- [ ] AC4: MCP tools are available to agents — an agent YAML can specify `mcp_tools: [github/*, filesystem/read_file]` to whitelist specific MCP tools.
- [ ] AC5: MCP tool calls are logged identically to built-in tool calls (tool name, parameters, result summary, duration).
- [ ] AC6: If an MCP server is unavailable, affected tools are gracefully removed and the agent is informed. The system does not crash.
- [ ] AC7: `GET /api/tools` endpoint returns all available tools (built-in + MCP) with their source.

**Related config:** `taim-vault/config/mcp-servers.yaml`.
**Priority:** P0

---

#### US-12.5: Tool Security & Sandboxing
**As a** user **I want** tool execution to be sandboxed and controllable **so that** agents cannot perform unintended actions on my system.

**Acceptance Criteria:**
- [ ] AC1: File system tools (`file_read`, `file_write`) are restricted to the vault path and `TAIM_WORKSPACE_PATH`. Path traversal attempts (e.g., `../../etc/passwd`) are blocked and logged.
- [ ] AC2: `shell_execute` (if enabled) runs commands in a restricted subprocess with a configurable timeout (default: 30s) and no network access.
- [ ] AC3: Agent YAML `requires_approval_for` can include specific tool names — e.g., `requires_approval_for: [file_write, shell_execute]` triggers an approval gate before those tools execute.
- [ ] AC4: A global tool allowlist/denylist can be configured in `taim-vault/config/defaults.yaml` under `tools.global_denylist`.
- [ ] AC5: All tool executions are included in the audit trail (tool name, agent, success/failure, timestamp).

**Related architecture:** AD-3 (WAITING state for approval gates).
**Priority:** P0

---

#### US-12.6: Tool Usage in WebSocket Events
**As a** user **I want** to see what tools my agents are using in real-time **so that** I understand how the team is working and can intervene if needed.

**Acceptance Criteria:**
- [ ] AC1: A new WebSocket event type `tool_execution` is added:
  ```json
  {
    "type": "tool_execution",
    "content": "Researcher is searching the web for 'competitor analysis SaaS 2026'",
    "metadata": {
      "agent_name": "researcher",
      "tool_name": "web_search",
      "tool_status": "running" | "completed" | "failed",
      "duration_ms": 1200
    }
  }
  ```
- [ ] AC2: Tool executions appear as inline status updates in the chat, not as separate messages. The UI shows them as subtle activity indicators under the agent's status card.
- [ ] AC3: Failed tool executions show a brief explanation ("Web search unavailable — no search API key configured").
- [ ] AC4: The `agent_progress` event includes a `tools_used` count in metadata so the StatusBar can show "Researcher: 3 tools used, EXECUTING".

**Related architecture:** AD-6 (WebSocket event model — `tool_execution` is event type #12).
**Priority:** P0

---

## 5. API Specification

> Architecture Decision 6 defines the WebSocket event model. Architecture Decision 8 defines the SQLite schema that backs these endpoints.

### 5.1 REST Endpoints

#### POST /api/chat/sessions
Create a new chat session. Returns a session ID used to open the WebSocket connection.

**Request Body:**
```json
{
  "user_id": "reyk",
  "locale": "de"
}
```

**Response (201):**
```json
{
  "session_id": "sess_01J5XYZ",
  "user_id": "reyk",
  "created_at": "2026-04-12T10:00:00Z",
  "onboarding_required": false,
  "ws_url": "ws://localhost:8000/ws/chat/sess_01J5XYZ"
}
```

**Referenced by:** US-1.1 (onboarding), US-1.2 (task requests), US-11.1 (server setup)

---

#### GET /api/chat/sessions/{session_id}/history
Returns chat message history for a session.

**Query Parameters:** `limit` (int, default 50), `offset` (int, default 0)

**Response (200):**
```json
{
  "session_id": "sess_01J5XYZ",
  "messages": [
    {
      "message_id": "msg_001",
      "role": "user",
      "content": "Erstelle eine Wettbewerber-Analyse",
      "timestamp": "2026-04-12T10:01:00Z",
      "metadata": null
    }
  ],
  "total": 1,
  "has_summary": false,
  "session_summary": null
}
```

**Referenced by:** US-1.5 (conversation continuity), US-9.8 (WS reconnection restores history)

---

#### GET /api/teams
List all teams.

**Query Parameters:** `status` (optional: active|paused|completed|failed|blueprint), `limit`, `offset`

**Response (200):**
```json
{
  "teams": [
    {
      "team_id": "team_abc123",
      "name": "Research Team",
      "status": "active",
      "pattern": "pipeline",
      "agent_count": 3,
      "elapsed_minutes": 45,
      "tokens_used": 87340,
      "cost_eur": 1.23,
      "budget_eur": 10.00
    }
  ],
  "total": 1
}
```

**Referenced by:** US-9.5 (Teams view)

---

#### POST /api/teams
Create a team directly (Layer 2 — power user).

**Request Body:**
```json
{
  "name": "Frontend Redesign Team",
  "objective": "Redesign der Landing Page",
  "pattern": "sequential",
  "agents": [
    { "role": "lead", "agent_name": "project-planner" },
    { "role": "developer", "agent_name": "frontend-dev" }
  ],
  "config": {
    "time_limit_minutes": 240,
    "token_budget": 500000,
    "budget_eur": 8.00,
    "iteration_rounds": 3,
    "on_limit_reached": "graceful_stop"
  }
}
```

**Response (201):** Full Team object with status `blueprint`.

**Referenced by:** US-4.1 (team composition), US-4.2 (pattern selection)

---

#### GET /api/teams/{team_id}
Get full team details with per-agent status and token usage. Response includes agents array with state machine states, tasks array, and token_summary.

**Referenced by:** US-9.5 (Teams detail view)

---

#### POST /api/teams/{team_id}/start
Start a blueprint or paused team.

**Request Body:**
```json
{
  "task_description": "Analysiere 5 Wettbewerber",
  "constraints": { "time_limit_minutes": 180, "budget_eur": 5.00 },
  "session_id": "sess_01J5XYZ"
}
```

**Referenced by:** US-4.3 (plan confirmation), US-4.4 (heartbeat)

---

#### POST /api/teams/{team_id}/stop
Stop a running team.

**Request Body:**
```json
{ "mode": "graceful", "reason": "User requested stop" }
```

**Referenced by:** US-2.3 (stop commands), US-9.5 (Stop Team button)

---

#### GET /api/agents
List all agents from the registry.

**Query Parameters:** `skills` (comma-separated filter), `available_only` (bool)

**Referenced by:** US-3.2 (agent registry), US-9.6 (Agents view)

---

#### GET /api/agents/{agent_name}
Get full agent definition with runtime stats.

**Referenced by:** US-3.2 (registry query), US-9.6 (agent detail)

---

#### GET /api/stats/tokens
Token usage statistics by period, filterable by team/agent.

**Query Parameters:** `period` (today|week|month|all), `team_id`, `agent_name`

**Referenced by:** US-8.3 (monthly summary), US-9.7 (Stats view)

---

#### GET /api/stats/costs
Cost breakdown in EUR with provider-level detail and budget tracking.

**Referenced by:** US-6.4 (budget enforcement), US-8.3 (monthly summary)

---

#### GET /api/health
Health check with subsystem status (database, vault, providers, orchestrator).

**Response:**
```json
{
  "status": "ok",
  "vault_ok": true,
  "providers": ["anthropic"],
  "db_ok": true,
  "orchestrator_ok": true
}
```

**Referenced by:** US-11.1 (server setup)

---

#### POST /api/setup/init
Initialize TAIM vault. Idempotent.

**Referenced by:** US-7.1 (vault initialization), US-1.1 (onboarding)

---

#### POST /api/setup/provider
Register or update an LLM provider. Tests the connection before confirming.

**Referenced by:** US-6.1 (multi-provider config), US-1.1 (onboarding)

---

#### GET /api/tasks
List recent tasks with their status.

**Referenced by:** US-4.5 (task lifecycle), US-9.7 (Stats view recent tasks)

---

### 5.2 WebSocket Protocol

**Endpoint:** `ws://{host}/ws/chat/{session_id}`

#### Server → Client Events

```typescript
type WSEvent = {
  type: "thinking" | "plan_proposed" | "agent_started" | "agent_progress" |
        "agent_state" | "agent_completed" | "question" | "result" |
        "budget_warning" | "error" | "system"
  content: string
  timestamp: string        // ISO 8601
  event_id: string
  session_id: string
  metadata?: {
    agent_name?: string
    agent_run_id?: string
    task_id?: string
    team_id?: string
    tokens_used?: number
    cost_eur?: number
    state?: AgentState
    previous_state?: AgentState
    progress?: number        // 0–100
    plan?: TeamPlan
    budget_threshold_pct?: number
    error_type?: string
    retry_in_seconds?: number
  }
}
```

| Event Type | Triggered by | UI Effect | Referenced by |
|------------|-------------|-----------|---------------|
| `thinking` | Stage 1/2 processing begins | 3-dot animated indicator | US-1.2, US-2.1 |
| `plan_proposed` | Team Composer finished plan | Plan Card renders in chat | US-4.1, US-4.3, US-9.3 |
| `agent_started` | Agent transitions to PLANNING | New agent card in context panel | US-3.4, US-9.2 |
| `agent_progress` | Agent sends mid-execution update | Progress bar + last-action text updates | US-5.1, US-9.2 |
| `agent_state` | State machine transition | Agent badge updates | US-3.4, US-9.2 |
| `agent_completed` | Agent reaches DONE | Agent card shows DONE, cost delta | US-5.4, US-8.2 |
| `question` | Agent reaches WAITING (approval gate) | TAIM message with inline reply options | US-3.5 |
| `result` | Task completed | Result block in chat, copy button | US-5.3, US-8.2 |
| `budget_warning` | 80% of time or token budget reached | StatusBar turns amber | US-1.4, US-4.4, US-6.4 |
| `error` | Unrecoverable failure | Error card with action buttons | US-6.3, US-9.8 |
| `system` | Connection/heartbeat/info | Small subdued system message | US-11.1 |

#### Client → Server Messages

```typescript
type WSMessage = {
  type: "user_message" | "approval" | "stop" | "ping"
  content: string
  message_id: string
  timestamp: string
  metadata?: {
    team_id?: string
    approved?: boolean
    stop_mode?: "graceful" | "immediate"
  }
}
```

| Message Type | Sent when | Referenced by |
|-------------|-----------|---------------|
| `user_message` | User sends any text in chat | US-1.2, US-2.1–2.4 |
| `approval` | User clicks Start/Cancel on plan card, or approves agent action | US-4.3, US-3.5 |
| `stop` | User types "stop" or clicks Stop button | US-2.3, US-9.5 |
| `ping` | Every 30s to keep WebSocket alive | US-9.8 |

---

## 6. Data Models

All models are Pydantic v2. Source: `backend/src/taim/models/`. 29 total models.

### Agent Models (`models/agent.py`)

| Model | Description | Key Fields |
|-------|-------------|------------|
| `AgentStateEnum` | State machine states | PLANNING, EXECUTING, REVIEWING, ITERATING, WAITING, DONE, FAILED |
| `ModelTierEnum` | LLM model tiers | tier1_premium, tier2_standard, tier3_economy |
| `Agent` | Registry definition | name, model_preference (list), skills (list), tools (list), max_iterations, model_tier |
| `AgentState` | Runtime state snapshot | current_state (AgentStateEnum), iteration (int), tokens_used (int), cost_eur (float), state_history (list) |
| `AgentRun` | Completed execution record | final_state, prompt_tokens, completion_tokens, cost, provider, model_used, failover_occurred |
| `MemoryLayer` | Memory temperature enum | HOT, WARM, COLD |
| `MemoryEntry` | Single memory note | title, category, tags (list), confidence (float), source, content (Markdown body) |
| `MemoryIndex` | In-memory INDEX.md representation | entries (list[MemoryIndexEntry]) |
| `MemoryIndexEntry` | One INDEX.md line | filename, summary, tags (list), updated_at |

### Team Models (`models/team.py`)

| Model | Description | Key Fields |
|-------|-------------|------------|
| `OrchestrationPattern` | Pattern enum | sequential, parallel, pipeline, hierarchical |
| `OnLimitReached` | Limit behavior enum | graceful_stop, immediate_stop, notify_only |
| `TeamStatus` | Team lifecycle status | blueprint, active, paused, completed, failed |
| `TeamConfig` | Execution constraints | time_limit_minutes, token_budget, budget_eur, iteration_rounds, heartbeat_interval_seconds, on_limit_reached |
| `TeamAgentSlot` | Role-to-agent assignment | role (str), agent_name (str) |
| `TeamPlan` | Proposed plan for user approval | agents (list[TeamAgentSlot]), pattern, estimated_minutes, estimated_tokens, estimated_cost_eur, team_id |
| `Team` | Full team definition | team_id, name, objective, status (TeamStatus), pattern, agents, config (TeamConfig), tasks, token_summary |

### Task Models (`models/task.py`)

| Model | Description | Key Fields |
|-------|-------------|------------|
| `TaskStatus` | Task lifecycle | pending, in_progress, waiting_approval, completed, failed, cancelled |
| `TaskResult` | Agent output | content (str), format (str), quality_score (float) |
| `Task` | Internal orchestration unit | task_id, team_id, status, agent_states (dict), token_total, cost_total, created_at, completed_at |

### Chat & Intent Models (`models/chat.py`)

| Model | Description | Key Fields |
|-------|-------------|------------|
| `ChatMessage` | Single message | message_id, role (user/assistant/system), content, timestamp, metadata |
| `ChatSession` | Session with summary support | session_id, user_id, messages (list), has_summary, session_summary, created_at |
| `IntentCategory` | Stage 1 output enum | new_task, confirmation, follow_up, status_query, configuration, stop_command, onboarding_response |
| `IntentClassification` | Stage 1 full output | category (IntentCategory), confidence (float, 0–1), needs_deep_analysis (bool) |
| `TaskConstraints` | Parsed constraints | time_limit_seconds, budget_eur, specific_agents (list), model_tier_override |
| `IntentResult` | Stage 2 full output | task_type, objective, parameters (dict), constraints (TaskConstraints), missing_info (list[str]), suggested_team (optional) |
| `WSEvent` | Server→Client WS envelope | type, content, timestamp, event_id, session_id, metadata |
| `WSMessage` | Client→Server WS envelope | type, content, message_id, timestamp, metadata |

### Config & Tracking Models (`models/config.py`)

| Model | Description | Key Fields |
|-------|-------------|------------|
| `ProviderConfig` | Provider definition | name, api_key_env (str), models (list), priority (int), monthly_budget_eur (optional float) |
| `TokenUsage` | Per-call tracking record | call_id, agent_run_id, task_id, model, provider, prompt_tokens, completion_tokens, cost_usd, timestamp |
| `CostEntry` | Aggregated cost for reporting | period, provider, total_cost_eur, total_tokens, task_count |
| `VaultConfig` | Runtime vault paths | vault_root, agents_dir, prompts_dir, users_dir, config_dir, db_path |
| `SystemConfig` | Merged runtime configuration | vault (VaultConfig), providers (list[ProviderConfig]), defaults (dict), env |

### Consistency Notes

- `cost` fields are consistently `cost_eur` (float, euros) in team/agent models. `TokenUsage.cost_usd` is stored in USD for raw tracking; conversion to EUR happens at the API layer using a configurable rate.
- `AgentState.current_state` uses `AgentStateEnum`, matching the 7 states in Architecture Decision 3.
- `IntentClassification.confidence < 0.80` triggers automatic escalation from Stage 1 to Stage 2 (RISK-07 mitigation).

---

## 7. UX & Conversation Design

> This section integrates the full UX/UI specification. Architecture Decision 6 (WebSocket events) and Architecture Decision 9 (Zustand stores) define the data layer behind all UI components.

### 7.1 User Journeys

Eight journeys document the complete user experience from first-run onboarding through error recovery.

#### Journey 1: First-Time User (Guided Onboarding)
**Entry point:** User opens TAIM for the first time. No user profile exists.

**UI on load:** Full-screen welcome overlay. No sidebar nav items are clickable except Chat. StatusBar shows "Not configured."

**Conversation flow:**
```
TAIM:   "Welcome. I'm TAIM — your AI team manager.
         I'll have you set up in 3 minutes.
         What kind of work do you mainly do?"

User:   "I'm a marketing manager at a B2B SaaS company."

TAIM:   "Good to know. Content creation, competitive research,
         and campaign planning are where I'll help most.
         Do you have API keys for AI services like Anthropic or OpenAI?"

User:   "I have an Anthropic API key."

[UI: Inline API key input field appears in the chat bubble — masked]
[UI: "Key saved securely (local only)" confirmation]

TAIM:   "Are there any rules I should follow? Data privacy
         requirements, brand guidelines, things I must never do?"

User:   "We're GDPR-compliant. No customer data in outputs.
         Always use formal 'You' in German texts."

TAIM:   "Got it. Here's what I've set up for you:
         ✓ Anthropic / Claude as primary model
         ✓ GDPR rule: no customer data in outputs
         ✓ Style rule: formal 'You' in German texts
         ✓ Marketing-optimized agent selection
         You're ready. What do you need?"

[UI: Welcome overlay dismisses. Full dashboard reveals. Nav unlocks.]
```

**Vault writes after onboarding:**
- `taim-vault/users/{name}/INDEX.md` — warm memory index
- `taim-vault/users/{name}/memory/user-profile.md` — name, role, industry, language preferences
- `taim-vault/users/{name}/memory/preferences.md` — output format, verbosity level
- `taim-vault/config/providers.yaml` — provider name and model list (no raw keys)
- `taim-vault/rules/compliance/onboarding-rules.yaml` — compliance rules from Step 4
- `taim-vault/rules/behavior/style-rules.yaml` — style/brand rules from Step 4

**API keys are never written to vault.** They are stored in the OS credential store via the `keyring` Python library (macOS Keychain, Linux/Windows credential store), with `.env` as fallback.

**Related user stories:** US-1.1, US-6.1, US-7.1, US-7.2

---

#### Journey 2: Simple Task (Single Agent)
User wants a short email drafted. TAIM uses a single Writer agent. No plan approval (single-agent tasks skip the team confirmation step per AD-7). Result delivered inline in chat. Cost shown as "€0.02".

---

#### Journey 3: Team Task (Multi-Agent)
User requests a competitive analysis for 5 competitors. TAIM proposes a research team (Lead Researcher + 3× Web Researcher + Analyst). User approves with budget constraint ("Start — but max €5 budget and 2 hours"). TAIM sets limits, executes, provides progress updates at checkpoints, delivers comparison table and strategic summary. Full report saved to vault.

---

#### Journey 4: Task with Constraints
User specifies tight budget upfront ("max 20 minutes and max €1"). TAIM adapts the plan (1 researcher, economy tier, summary format) to fit within constraints. Budget warning shown when 80% used (StatusBar turns amber).

---

#### Journey 5: Approval Flow (Plan Modification)
User requests a multi-phase task. TAIM proposes a 3-agent plan. User clicks "Modify" and requests changes (remove code review, use cheapest model). TAIM re-proposes revised plan with updated estimates. User approves. Maximum 3 modification rounds allowed before TAIM asks if user wants to start from scratch.

---

#### Journey 6: Stop / Interrupt Running Team
User types "Stop the research team." TAIM gracefully stops all agents (each completes current LLM call), summarizes what was completed, returns partial results, and saves them to vault. Emergency stop ("Stop everything now") triggers immediate stop. Stop button available on each agent card and in StatusBar.

---

#### Journey 7: Status Check During Execution
User asks "What's happening?" while agents are running. TAIM returns a formatted status response (agent states, iteration counts, budget used, estimated remaining time) without an LLM call. Response latency < 500ms (NFR-01).

---

#### Journey 8: Error Scenario (Provider Failover)
Anthropic returns HTTP 503 mid-execution. TAIM transparently failovers to next provider (OpenAI). If delay > 5 seconds: small subdued system message "Anthropic briefly unavailable. Switched to OpenAI." If all providers fail: full error card with diagnostic info and 3 actionable options. Partial results always preserved.

---

### 7.2 Guided Onboarding Flow (Complete Script)

**Trigger:** First launch — no user profile detected.

**Step 1: Welcome**
```
TAIM:   "Welcome. I'm TAIM — your AI team manager.
         I help you get expert-level results from AI without
         needing to know how it works.
         Let's get you set up in 3 minutes.
         What kind of work do you mainly do?"
```
UI: Full-screen centered chat. Single pulsing input field. No navigation visible.

**Step 2: Work Context**
User answers. TAIM extracts industry, role type, likely task types, and reflects back a 1-sentence confirmation plus optimization statement. Asks about API keys. If user has no keys: offers Ollama option and continues without blocking.

**Step 3: API Key Setup**
```
TAIM:   "Paste your [Anthropic/OpenAI] API key here.
         It stays on your machine — never sent anywhere except
         directly to [Anthropic/OpenAI] when agents need to work."
```
UI: Inline password-style input field appears in the chat bubble (not a modal). Paste-and-confirm interaction. After confirmation: "Key saved. [Provider] is ready as your primary AI."

**Step 4: Rules and Compliance**
```
TAIM:   "Last thing: are there any rules I should follow?
         For example:
         • Data privacy (GDPR, HIPAA, no customer data in outputs)
         • Brand guidelines (tone, language, style)
         • Things I must never do
         If you have nothing specific, just say 'no rules'."
```
User answers. TAIM extracts and reflects rules back as bullet points.

**Step 5: Confirmation**
```
TAIM:   "You're all set:
         ✓ [Provider] ready as primary model
         ✓ [Rule 1 if any]
         ✓ Optimized for [work context]
         What do you need?"
```
UI: Welcome overlay transitions out. Full dashboard reveals. Navigation unlocks.

---

### 7.3 Dashboard UI Specification

#### Overall Layout (Desktop)

```
┌─────────────────────────────────────────────────────────────────────┐
│  TAIM                                          [User] [Settings]    │
├─────────┬───────────────────────────────────────┬───────────────────┤
│         │                                       │                   │
│  NAV    │   MAIN CONTENT AREA                   │   CONTEXT PANEL   │
│         │   (active view)                        │   (collapsible)   │
│  Chat   │                                       │                   │
│  Teams  │                                       │                   │
│  Agents │                                       │                   │
│  Stats  │                                       │                   │
│         │                                       │                   │
├─────────┴───────────────────────────────────────┴───────────────────┤
│  STATUS BAR                                                         │
└─────────────────────────────────────────────────────────────────────┘
```

**Column widths:**
- Nav sidebar: 56px (icon-only) | 200px (expanded on hover/click)
- Main content: flex-fill
- Context panel: 280px | hidden (toggle button)
- Status bar: full width, 36px height

**Color system (dark theme):**

| Token | Value | Usage |
|-------|-------|-------|
| Background | `zinc-950` (#09090b) | Page background |
| Surface | `zinc-900` (#18181b) | Cards, panels |
| Surface elevated | `zinc-800` (#27272a) | Elevated cards |
| Border | `zinc-800` (#27272a) | All borders |
| Text primary | `zinc-50` (#fafafa) | Main text |
| Text secondary | `zinc-400` (#a1a1aa) | Subtitles, labels |
| Text muted | `zinc-600` (#52525b) | Timestamps, metadata |
| Accent | `violet-500` (#8b5cf6) | Primary actions, active states |
| Success | `emerald-500` (#10b981) | DONE state, completed |
| Warning | `amber-500` (#f59e0b) | Budget warnings, WAITING state |
| Error | `red-500` (#ef4444) | FAILED state, errors |

#### View: Chat (Primary)

Default view. Occupies full main content area.

**Message types and visual treatment:**

| Message Type | Visual Treatment |
|-------------|-----------------|
| User message | Right-aligned, `zinc-800` background, no avatar |
| TAIM response | Left-aligned, `zinc-900` background, TAIM dot avatar |
| Plan card | Inline card, `violet-500/30` border, action buttons (Start/Modify/Cancel) |
| Progress update | Subdued, `zinc-700` background, smaller text |
| System notice | Full-width subtle banner, `zinc-800`, centered text |
| Error message | `red-950` background, `red-400` text, action buttons |
| Result/output | `zinc-900`, syntax highlighting for code, copy button |
| Budget warning | `amber-950` background, `amber-400` text |

**Input field behavior:**
- Placeholder: "What do you need?" (first load) / "Continue..." (subsequent)
- `Enter` to send, `Shift+Enter` for newline
- Max height: 6 lines before scroll
- Send button: disabled when empty, violet when active

**Streaming:** TAIM responses stream token by token. Plan cards appear atomically.

**Context Panel (right side, shown when agents active):**
Shows active agent cards. Each card: name, state badge (color-coded), progress bar, elapsed time, stop button. Budget tracker at bottom.

#### View: Teams

Active teams with real-time status. Saved/blueprint teams with start/edit/delete actions. Team detail panel: agent state table, budget bar, time progress.

#### View: Agents

Agent registry browser. Agent cards in CSS grid. Click to expand detail: capabilities, model preference, defaults, monthly usage stats. "View YAML" link opens vault file path. Read-only in Phase 1.

#### View: Stats

Monthly KPI cards (total cost, task count, average cost/task). Daily cost bar chart (last 30 days). Cost breakdown by agent (horizontal bar list). Recent 10 tasks table. Time period selector. No real-time updates — refreshes on navigation.

#### View: StatusBar (Footer, Always Visible)

| State | Display |
|-------|---------|
| Idle, no task | "Ready · No active tasks" |
| Running, budget set | "● 3 agents active · Budget: €0.60/€5.00 █████░ · 0:15h" |
| Budget warning (80%) | Amber background · "⚠ 3 agents · Budget: €4.00/€5.00" |
| Task complete | "✓ Task complete · €3.40 used · 1:10h" (fades after 10s) |
| Error | Red background · "✗ Error — 1 agent failed · [View]" |

---

### 7.4 Responsive Behavior

| Breakpoint | Layout | Notes |
|-----------|--------|-------|
| Desktop (≥1280px) | 3-column: nav + main + context panel | Context panel visible by default when agents active |
| Tablet (768–1279px) | 2-column: nav (icon-only) + main | Context panel: hidden by default, slide-in toggle |
| Mobile (<768px) | Single column, bottom nav bar | Context panel: bottom sheet |

---

### 7.5 WebSocket Event → UI Mapping

| Event | Key Fields | UI Change | Zustand Store |
|-------|-----------|-----------|---------------|
| `thinking` | — | 3-dot indicator in chat | `useChatStore.isThinking = true` |
| `plan_proposed` | agents[], estimate, team_id | Plan Card renders in chat | `useChatStore` adds PlanMessage; `useTeamStore.pendingPlan` set |
| `agent_started` | agent_name, task_id | New agent card in context panel; StatusBar count++ | `useTeamStore` adds AgentCard; `useAppStore.activeAgentCount++` |
| `agent_progress` | agent_name, progress, message | Agent card progress bar updates | `useTeamStore` updates AgentCard.progress |
| `agent_state` | agent_name, state, previous_state | Agent card badge updates; amber if WAITING | `useTeamStore` updates AgentCard.state |
| `agent_completed` | agent_name, summary, cost | Agent card: DONE (green), cost delta shown | `useTeamStore` updates; `useStatsStore.totalCost += cost` |
| `question` | message, options[] | TAIM message with inline reply buttons | `useChatStore` adds QuestionMessage |
| `result` | content, format, file_path? | Result block in chat; all agent cards → DONE | `useChatStore` adds ResultMessage; `isThinking = false` |
| `budget_warning` | threshold, cost_used | StatusBar amber; budget bar orange | `useStatsStore.budgetWarning = true` |
| `error` | message, error_type, recoverable | Agent card FAILED (red); error card in chat | `useChatStore` adds ErrorMessage; `useAppStore.hasError = true` |
| `system` | message, level | Subdued system message (zinc/amber/red) | `useChatStore` adds SystemMessage |

---

### 7.6 Conversation Patterns

#### TAIM's Communication Personality
- **Direct.** No "Great question!", no sycophantic openers.
- **Concise.** Bullet points for lists, not prose paragraphs.
- **Confident.** Makes decisions. Asks for confirmation on big actions, not small ones.
- **Transparent.** Always tells the user what it's doing and what it costs.

#### Plan Proposal Format (always a structured card, not prose)
```
Proposed team:
• [Agent Role] — [1-line purpose]
• [Agent Role] — [1-line purpose]
Estimated: [time] · ~[token count] · ~€[cost]
[Start] [Modify] [Cancel]
```

Rules: always show cost in EUR; time in human language ("~90 minutes"); never more than 6 agents shown (use "3× Researcher" notation for multiples).

#### Follow-Up Question Rules
TAIM only asks follow-ups when:
1. Task is ambiguous in a way that changes team composition
2. A constraint is missing that would affect cost by > 50%
3. A required input is genuinely unavailable

TAIM does NOT ask about: format preferences (uses memory), minor style decisions, details it can research itself.

#### Verbosity Levels
Users can set verbosity in Settings or in chat ("be more concise"). Three levels: Minimal (direct answer only), Normal (default — structured with brief context), Detailed (full comparison tables, sources, benchmarks).

---

### 7.7 Component Inventory

#### Layout Components
| Component | Purpose | Path |
|-----------|---------|------|
| `AppShell` | Overall layout wrapper | `components/layout/AppShell.tsx` |
| `NavSidebar` | Left navigation | `components/layout/NavSidebar.tsx` |
| `NavItem` | Single nav item | `components/layout/NavItem.tsx` |
| `ContextPanel` | Right-side collapsible panel | `components/layout/ContextPanel.tsx` |
| `StatusBar` | Footer bar with live metrics | `components/layout/StatusBar.tsx` |
| `MobileNav` | Bottom tab bar for mobile | `components/layout/MobileNav.tsx` |

#### Chat Components
| Component | Purpose | Path |
|-----------|---------|------|
| `ChatView` | Main chat container | `components/Chat.tsx` |
| `MessageList` | Scrollable message history | `components/chat/MessageList.tsx` |
| `UserMessage` | User message bubble | `components/chat/UserMessage.tsx` |
| `TaimMessage` | TAIM response bubble | `components/chat/TaimMessage.tsx` |
| `PlanCard` | Team plan proposal with action buttons | `components/chat/PlanCard.tsx` |
| `SystemMessage` | System notices (subdued) | `components/chat/SystemMessage.tsx` |
| `ErrorMessage` | Error display with action buttons | `components/chat/ErrorMessage.tsx` |
| `ResultBlock` | Formatted result with copy button | `components/chat/ResultBlock.tsx` |
| `ThinkingIndicator` | Animated 3-dot loader | `components/chat/ThinkingIndicator.tsx` |
| `ChatInput` | Message input + send button | `components/chat/ChatInput.tsx` |
| `BudgetWarningBanner` | Inline budget warning | `components/chat/BudgetWarningBanner.tsx` |

#### Agent / Context Panel Components
| Component | Purpose | Path |
|-----------|---------|------|
| `AgentCard` | Single agent card with state + progress | `components/agents/AgentCard.tsx` |
| `AgentStateBadge` | State label with color indicator | `components/agents/AgentStateBadge.tsx` |
| `AgentProgressBar` | Thin progress bar | `components/agents/AgentProgressBar.tsx` |
| `ContextBudgetTracker` | Budget mini-display in context panel | `components/agents/ContextBudgetTracker.tsx` |

#### Teams View Components
| Component | Purpose | Path |
|-----------|---------|------|
| `TeamsView` | Teams page container | `components/TeamView.tsx` |
| `TeamCard` | Summary card for a team | `components/teams/TeamCard.tsx` |
| `TeamDetailPanel` | Expanded team details | `components/teams/TeamDetailPanel.tsx` |
| `AgentStateRow` | Single agent in team detail | `components/teams/AgentStateRow.tsx` |
| `TeamStatusBadge` | RUNNING / IDLE / DONE / STOPPED | `components/teams/TeamStatusBadge.tsx` |

#### Agents View Components
| Component | Purpose | Path |
|-----------|---------|------|
| `AgentsView` | Agents registry page | `components/AgentView.tsx` |
| `AgentGrid` | CSS grid container | `components/agents/AgentGrid.tsx` |
| `AgentRegistryCard` | Compact card in registry browser | `components/agents/AgentRegistryCard.tsx` |
| `AgentDetailPanel` | Expanded agent detail | `components/agents/AgentDetailPanel.tsx` |
| `TierBadge` | Tier 1 / 2 / 3 colored badge | `components/agents/TierBadge.tsx` |

#### Stats View Components
| Component | Purpose | Path |
|-----------|---------|------|
| `StatsView` | Stats page container | `components/StatsView.tsx` |
| `StatCard` | Single KPI card | `components/stats/StatCard.tsx` |
| `CostBarChart` | Daily cost bar chart | `components/stats/CostBarChart.tsx` |
| `AgentBreakdownBar` | Horizontal cost breakdown | `components/stats/AgentBreakdownBar.tsx` |
| `RecentTaskList` | Table of recent tasks | `components/stats/RecentTaskList.tsx` |

#### Onboarding Components
| Component | Purpose | Path |
|-----------|---------|------|
| `OnboardingOverlay` | Full-screen onboarding wrapper | `components/onboarding/OnboardingOverlay.tsx` |
| `ApiKeyInput` | Masked API key input (inline in chat) | `components/onboarding/ApiKeyInput.tsx` |

#### Shared / Primitive Components
| Component | Purpose | Path |
|-----------|---------|------|
| `Button` | Variants: primary/secondary/ghost/danger | `components/ui/button.tsx` (shadcn) |
| `Badge` | Small label badge | `components/ui/badge.tsx` (shadcn) |
| `Progress` | Progress bar | `components/ui/progress.tsx` (shadcn) |
| `Tooltip` | Hover tooltip | `components/ui/tooltip.tsx` (shadcn) |
| `Sheet` | Slide-in panel | `components/ui/sheet.tsx` (shadcn) |
| `Separator` | Divider line | `components/ui/separator.tsx` (shadcn) |
| `CostDisplay` | Formats cost values with correct precision | `components/shared/CostDisplay.tsx` |
| `ElapsedTimer` | Live counting timer | `components/shared/ElapsedTimer.tsx` |
| `CopyButton` | Copy-to-clipboard with visual feedback | `components/shared/CopyButton.tsx` |

#### Agent State Color Reference
| State | Dot Color | Badge Background | Badge Text |
|-------|-----------|-----------------|------------|
| PLANNING | `violet-400` | `violet-950` | `violet-300` |
| EXECUTING | `violet-500` (animated pulse) | `violet-900` | `violet-200` |
| REVIEWING | `amber-400` | `amber-950` | `amber-300` |
| ITERATING | `orange-400` | `orange-950` | `orange-300` |
| WAITING | `amber-500` (slow pulse) | `amber-950` | `amber-200` |
| DONE | `emerald-500` | `emerald-950` | `emerald-300` |
| FAILED | `red-500` | `red-950` | `red-300` |
| STOPPED | `zinc-500` | `zinc-800` | `zinc-400` |

---

## 8. Technical Requirements

### 8.1 Non-Functional Requirements

| ID | Name | Target | Rationale |
|----|------|--------|-----------|
| NFR-01 | Intent Stage 1 Latency | p95 < 500ms | Stage 1 handles 60–70% of messages; slowness makes everything feel sluggish |
| NFR-02 | Intent Stage 2 Latency | p95 < 3s to first `thinking` event | Must signal understanding quickly |
| NFR-03 | WebSocket Delivery | p99 < 100ms for non-LLM events | Real-time feedback is the core UX promise |
| NFR-04 | State Transition Speed | < 10ms internal, < 50ms SQLite write | SQLite write must not bottleneck agent loop |
| NFR-05 | Dashboard Load | TTI < 2s (dev), < 1.5s (prod) | Users check status of running agents |
| NFR-06 | Crash Resumability | All non-terminal agents detectable within 10s of restart | State machines serialize to SQLite for this |
| NFR-07 | Graceful Degradation | Error event within 5s when all providers fail | Never crash, always communicate |
| NFR-08 | Retry Budget | Max 3 attempts per LLM call | Prevent infinite retries and silent budget drain |
| NFR-09 | Concurrent Agents | Min 10 agents, < 5MB per idle agent | Phase 1 single user; 10 provides headroom |
| NFR-10 | Concurrent WebSocket | Min 5 connections | Multiple browser tabs |
| NFR-11 | Memory Size | INDEX.md scan < 200ms for 500 entries | Warm/cold strategy depends on fast INDEX scan |
| NFR-12 | API Key Security | Keys only from env vars, never in files/logs/WS | Vault is git-versionable; committed keys = incident |
| NFR-13 | CORS | Explicit origins via env var, no wildcard | Prevent unauthorized LLM call triggering |
| NFR-14 | WS Auth | Session token validated (UUID, no JWT in Phase 1) | Prevent hijacking from other processes |
| NFR-15 | Input Sanitization | Max 4000 chars, no HTML, literal insertion in prompts | Prevent prompt injection via chat |
| NFR-16 | Test Coverage | >80% core logic, >60% async execution | CLAUDE.md mandates >80% on core |
| NFR-17 | Code Style | ruff check + format pass with zero violations | Consistent style |
| NFR-18 | Type Safety | Zero `Any` in non-test code, complete annotations | Especially critical for state machine serialization |
| NFR-19 | Structured Logging | JSON format, every LLM call logged with tokens/latency | Enable post-hoc debugging of multi-agent sessions |
| NFR-20 | Token Tracking | Per-call recording within 100ms, granular by agent/task/team | Dashboard stats require granular data from day one |
| NFR-21 | Audit Trail | All user actions and system decisions append-only | Transparency principle |

### 8.2 Technical Constraints (Hard Rules)

1. **No RAG, ever.** No vectors, no embeddings, no chunking, no similarity search. Knowledge retrieval is tag/keyword matching only (AD-4).
2. **No Obsidian dependency.** Plain filesystem via `pathlib` + `aiofiles` (US-7.2 AC5).
3. **Prompts never hardcoded.** All system prompts in `taim-vault/system/prompts/*.yaml` (AD-1).
4. **LiteLLM as transport only.** Failover/retry/tiering are TAIM's own logic, not delegated to LiteLLM (US-6.3).
5. **SQLite for state only.** YAML = config source of truth. Markdown = memory source of truth (AD-8).
6. **Python 3.11+ required.** May use `match` statements, `TaskGroup`, etc.
7. **All config YAML, all memory Markdown.** No JSON configs, no plain-text memory.
8. **No cloud services.** Self-hosted, no telemetry, no external auth in Phase 1.

### 8.3 Infrastructure

#### SQLite Configuration
- Single DB at `taim-vault/system/state/taim.db`
- WAL mode, foreign keys ON, `busy_timeout` 5000ms
- Tables: `token_tracking`, `task_state`, `session_state`, `agent_runs`
- Schema created on startup; integer version in `schema_version` table
- No migration tool in Phase 1; upgrade path by version check on startup

#### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes (or another provider) | — | Primary LLM API key |
| `OPENAI_API_KEY` | No | — | Secondary provider |
| `TAIM_VAULT_PATH` | No | `./taim-vault` | Override vault location |
| `TAIM_HOST` | No | `localhost` | Server bind address |
| `TAIM_PORT` | No | `8000` | Server port |
| `TAIM_LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `TAIM_CORS_ORIGINS` | No | `localhost:*` | Allowed CORS origins |
| `TAIM_SESSION_TOKEN` | No | — | WS session validation |
| `TAIM_ENV` | No | `development` | Environment mode |

#### Ports
- Backend: 8000 (configurable via `TAIM_PORT`)
- Frontend dev: 5173
- Ollama: 11434 (external)

#### Development Workflow
```bash
# Backend
cd backend && uv run uvicorn taim.main:app --reload

# Frontend
cd frontend && pnpm dev

# Tests
cd backend && uv run pytest
cd frontend && pnpm test --run

# Lint
cd backend && uv run ruff check . && uv run ruff format --check .
```

---

## 9. Dependencies & Tech Stack

### 9.1 Backend Dependencies (`backend/pyproject.toml`)

#### Core (already assumed in stack)
| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ≥0.115.0 | Web framework + WebSocket |
| `uvicorn[standard]` | ≥0.32.0 | ASGI server |
| `pydantic` | ≥2.0.0 | Data models and validation |
| `litellm` | ≥1.40.0 | LLM transport layer |
| `typer` | ≥0.12.0 | CLI framework |
| `pyyaml` | ≥6.0.2 | YAML parsing (config + prompts) |
| `aiofiles` | ≥24.1.0 | Async file I/O for vault operations |

#### Must Add (flagged missing)
| Package | Version | Purpose | Flagged in |
|---------|---------|---------|------------|
| `python-frontmatter` | ≥1.1.0 | Parse Markdown+YAML frontmatter for memory notes | tech-requirements |
| `tiktoken` | ≥0.7.0 | Token counting for context budget enforcement (AD-4) | tech-requirements |
| `python-dotenv` | ≥1.0.0 | Load `.env` file for development (US-11.4) | tech-requirements |
| `structlog` | ≥24.1.0 | Structured JSON logging (NFR-19) | tech-requirements |
| `keyring` | ≥25.0.0 | OS credential store for API keys (UX spec Journey 1) | ux-spec |

#### Dev Dependencies (must add)
| Package | Version | Purpose |
|---------|---------|---------|
| `pytest-mock` | ≥3.14.0 | Mock fixtures for LLM mocking |
| `respx` | ≥0.21.0 | HTTP request mocking for LiteLLM |
| `pytest-asyncio` | ≥0.24.0 | Async test support |
| `pytest-cov` | ≥5.0.0 | Coverage reporting |

### 9.2 Frontend Dependencies (`frontend/package.json`)

#### Core (already assumed in stack)
| Package | Version | Purpose |
|---------|---------|---------|
| `react` | ^19.0.0 | UI framework |
| `react-dom` | ^19.0.0 | DOM rendering |
| `typescript` | ^5.6.0 | Type safety |
| `vite` | ^6.0.0 | Build tool |

#### Must Add (flagged missing)
| Package | Version | Purpose | Flagged in |
|---------|---------|---------|------------|
| `zustand` | ^5.0.0 | State management (AD-9) | tech-requirements |
| `@tailwindcss/vite` | ^4.0.0 | TailwindCSS v4 | tech-requirements |
| `class-variance-authority` | ^0.7.0 | Component variants (Shadcn) | tech-requirements |
| `clsx` | ^2.1.0 | Conditional class merging | tech-requirements |
| `tailwind-merge` | ^3.0.0 | Tailwind class deduplication | tech-requirements |
| `lucide-react` | ^0.400.0 | Icons | tech-requirements |
| `zod` | ^3.23.0 | Schema validation for WS messages | tech-requirements |

#### Dev Dependencies (must add)
| Package | Version | Purpose |
|---------|---------|---------|
| `vitest` | ^3.0.0 | Test runner |
| `@testing-library/react` | ^16.0.0 | Component testing |
| `msw` | ^2.3.0 | WebSocket mocking |

#### Note on Chart Library
The Stats view requires a simple bar chart (`CostBarChart` component). No chart library is explicitly specified in the source documents. Recommendation: `recharts ^2.12.0` — lightweight, React-native, no D3 dependency required.

---

## 10. Testing Strategy

### 10.1 Backend (pytest)

**Coverage targets:**
- Overall floor: 75% line coverage
- Per core module: 80% (CLAUDE.md requirement)
- Covered modules: `taim/conversation/`, `taim/orchestrator/`, `taim/router/`, `taim/brain/`

**Test categories:**

| Category | Scope | Key modules |
|----------|-------|-------------|
| Unit | Pure logic, no I/O | Intent Interpreter (both stages), Context Assembler, Agent State Machine, PromptLoader, VaultOps, Token Tracker, Router (tiering + failover) |
| Integration | WebSocket round-trips, REST endpoints | Full flow: message → team → result |
| LLM mocking | All unit tests | `pytest-mock` for unit; `respx` for integration (mock HTTP responses, never real API calls) |

**Required test files** (from US-11.5):
- `tests/backend/test_interpreter.py` — Stage 1 + Stage 2 (including confidence < 0.80 escalation)
- `tests/backend/test_context_assembler.py` — token budget enforcement, relevance scoring
- `tests/backend/test_state_machine.py` — all 7 states, all valid transitions, crash-resume
- `tests/backend/test_router.py` — tiering logic, all 7 error types, max 3 retry budget
- `tests/backend/test_prompt_loader.py` — variable substitution, missing file errors, caching
- `tests/backend/test_vault_ops.py` — INDEX.md scan, memory write/read, idempotent init
- `tests/backend/test_token_tracker.py` — per-call recording, atomic writes

**Running tests:**
```bash
cd backend && uv run pytest --cov=taim --cov-report=term-missing
```

### 10.2 Frontend (vitest)

**Coverage target:** 70% line coverage

**Test categories:**

| Category | Scope | Tools |
|----------|-------|-------|
| Unit | Zustand stores, utility functions | vitest |
| Component | Key chat components, plan card, status bar | `@testing-library/react` |
| Integration | MSW WebSocket mock → store update → component render | `msw` v2 |

**Key integration test scenarios:**
- `plan_proposed` event → PlanCard renders with correct fields → "Approve" click → `approval` message sent
- `agent_state` event → AgentCard badge updates to correct state and color
- `budget_warning` event → StatusBar turns amber, budget bar changes color
- WebSocket disconnect → reconnection attempts → "Connection restored" message

---

## 11. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| RISK-01 | LiteLLM API instability | Medium | High | Pin version; isolate behind single interface (`router/provider.py`); test HTTP response shapes with `respx`; TAIM owns retry/failover logic (not LiteLLM) |
| RISK-02 | WebSocket connection management | Medium | High | `ConnectionManager` class handles all WS state; agents are decoupled from WS (they emit events to a queue, not directly to socket); client auto-reconnect with exponential backoff |
| RISK-03 | Prompt quality = system quality | High | High | Test cases embedded in prompt YAML files; manual eval script; document which model version was tested against; AD-1 makes prompts independently improvable without code changes |
| RISK-04 | SQLite write contention | Low | Medium | WAL mode; `asyncio.Lock` around writes; `busy_timeout 5000ms`; token tracking uses best-effort (non-blocking) write pattern |
| RISK-05 | Context budget without exact token counting | Medium | Medium | `tiktoken` cl100k_base + 10% safety margin; log estimated vs. actual token count after each LLM call for calibration |
| RISK-06 | Vault filesystem corruption | Low | High | Atomic writes via `.tmp` + rename pattern; startup integrity check; `taim vault check` CLI command |
| RISK-07 | Stage 1 intent misclassification | Medium | High | Confidence threshold: `confidence < 0.80` → automatic escalation to Stage 2 regardless of category; log all Stage 1 classifications for review |
| RISK-08 | Tool API availability (web_search) | Medium | High | web_search depends on external API (Tavily/Serper). If unconfigured or down, agents work without web access — graceful degradation, not failure. Log warning. Suggest Ollama-based search as fallback. |
| RISK-09 | MCP server stability | Medium | Medium | MCP servers are external processes. Startup timeout (10s), health check on connect, auto-reconnect on disconnect. Tool unavailability is communicated to agent, not fatal. |

**Traceability to architecture decisions:**
- RISK-01 → AD-10 (error-type-aware handling)
- RISK-02 → AD-6 (WebSocket event model)
- RISK-03 → AD-1 (prompts as vault files)
- RISK-04 → AD-8 (SQLite)
- RISK-05 → AD-4 (token-budgeted context)
- RISK-06 → AD-5 (memory architecture)
- RISK-07 → AD-2 (two-stage intent)

---

## 12. Out of Scope (Phase 2+)

The following are explicitly excluded from Phase 1. They are documented here to prevent scope creep and to give implementors a clear boundary.

| Feature | Phase | Notes |
|---------|-------|-------|
| **Learning Loop** | Phase 2 | Automated prompt optimization based on task outcomes |
| **noRAG Knowledge Compiler** | Phase 2 | Compile external knowledge bases into CKU format. Phase 1 uses Markdown memory only. |
| **SWAT Builder** | Phase 2 | Dynamic agent swarm creation for ultra-complex tasks |
| **Rules Engine** | Phase 2 | Full compliance rule evaluation at execution time (Phase 1 stores rules as YAML, does not enforce them programmatically) |
| **Multi-User Support** | Phase 2/3 | Shared teams, role-based access, user isolation. Phase 1 is single-user. |
| **PostgreSQL migration** | Phase 3 | Migration path exists but not in Phase 1 |
| **Memory Browser UI** | Phase 3 | Dashboard view for browsing/editing warm memory entries |
| **Rules Editor UI** | Phase 3 | Dashboard view for editing compliance rules |
| **Audit View UI** | Phase 3 | Dashboard view for full audit trail |
| **Drag-and-drop workflow builder** | Never | Explicitly rejected in CLAUDE.md |
| **Fine-tuning capabilities** | Never | Explicitly rejected in CLAUDE.md |
| **Account creation / cloud services** | Never | Self-hosted only. No telemetry, no external auth. |
| **Vector database / RAG** | Never | Explicitly rejected. All retrieval is tag/keyword matching. |
| **Obsidian dependency** | Never | All vault operations use plain filesystem (`pathlib`). |

---

## 13. Implementation Priority

Suggested build order based on the dependency graph between components. Each step is a shippable increment.

### Step 1: Foundation
**Deliverables:** FastAPI server skeleton, vault initialization, SQLite schema, PromptLoader, config loading.
**Stories:** US-7.1, US-11.1, US-11.3, US-11.2
**Why first:** Everything else depends on the vault path, DB connection, and ability to load prompts.

### Step 2: LLM Router
**Deliverables:** Provider config loading, model tiering, LiteLLM transport wrapper, error-type-aware failover.
**Stories:** US-6.1, US-6.2, US-6.3
**Why here:** The Intent Interpreter and all agents need a working router before they can do anything.

### Step 3: Intent Interpreter
**Deliverables:** Stage 1 (quick classification), Stage 2 (deep understanding), stop/status handling.
**Stories:** US-2.1, US-2.2, US-2.3, US-2.4
**Why here:** The conversation layer is the entry point for all user interactions. Without it, the frontend has nothing to connect to.

### Step 4: Memory System
**Deliverables:** Hot memory (in-session), warm memory (INDEX.md + Markdown notes), vault ops class, session persistence.
**Stories:** US-7.2, US-7.3, US-7.4, US-1.5
**Why here:** Stage 2 needs user preferences from warm memory to enrich context. The Context Assembler needs the memory system.

### Step 5: Agent Registry & State Machine
**Deliverables:** Built-in agent YAML files, registry load/query, AgentStateMachine class, state serialization to SQLite.
**Stories:** US-3.1, US-3.2, US-3.4, US-5.1
**Why here:** The Team Composer cannot compose without a registry. The executor cannot run without state machines.

### Step 6: Tool Execution, Skills & MCP
**Deliverables:** ToolExecutor framework, built-in tools (web_search, web_fetch, file_read/write, vault_memory), skill YAML loader, MCP client integration, tool sandboxing, `tool_execution` WebSocket event.
**Stories:** US-12.1, US-12.2, US-12.3, US-12.4, US-12.5, US-12.6
**Why here:** Agents need tools to produce real results. Without tools, the entire system is an expensive prompt wrapper. This must come before team composition — the Composer needs to know what tools agents have when selecting them.

### Step 7: Team Composer & Orchestrator
**Deliverables:** Team Composer (auto-composition, pattern selection), Context Assembler, inter-agent result passing, Task Manager.
**Stories:** US-4.1, US-4.2, US-4.3, US-4.5, US-5.2, US-5.3
**Why here:** First point where a complete "message → plan → execution" flow becomes testable.

### Step 8: Heartbeat Manager & Token Tracking
**Deliverables:** Heartbeat loop, time limit enforcement, budget_warning events, per-call token tracking, agent run logging.
**Stories:** US-4.4, US-8.1, US-8.2, US-5.4, US-6.4
**Why here:** Required before any real user-facing testing — without limits, test runs can exceed budget.

### Step 9: Onboarding & Smart Defaults
**Deliverables:** Guided onboarding flow (5 steps), smart defaults engine, inline constraint parsing, provider setup via chat.
**Stories:** US-1.1, US-1.2, US-1.3, US-1.4
**Why here:** Builds on the complete backend. Onboarding writes to vault/memory, which requires Step 4.

### Step 10: React Dashboard
**Deliverables:** Full frontend — Chat view, Plan Card, agent status in context panel, StatusBar, Teams view, Stats view, WebSocket connection management.
**Stories:** US-9.1–9.8 (P0 and P1)
**Why here:** Frontend builds on a stable backend. Building it last avoids chasing moving API contracts.

### Step 11: CLI & Polish
**Deliverables:** Typer-based CLI (server start/stop, task run, agent/team management, stats), test coverage to targets, documentation of prompt YAML schema.
**Stories:** US-10.1–10.5, US-11.4, US-11.5
**Why last:** CLI is additive — it calls the same REST/WS API as the frontend. Test coverage is enforced throughout but formally verified here.

---

## Appendix A: Story → API Cross-Reference

| User Story | REST Endpoint(s) | WebSocket Event(s) | UI Component(s) |
|-----------|-----------------|-------------------|----------------|
| US-1.1 | POST /api/setup/init, POST /api/setup/provider | — | OnboardingOverlay, ApiKeyInput |
| US-1.2 | POST /api/chat/sessions | plan_proposed, thinking | ChatInput, PlanCard |
| US-1.3 | — | — | ChatInput |
| US-1.4 | — | budget_warning | StatusBar, BudgetWarningBanner |
| US-1.5 | GET /api/chat/sessions/{id}/history | system | MessageList |
| US-2.1 | — | thinking | ThinkingIndicator |
| US-2.2 | — | thinking, plan_proposed | PlanCard |
| US-2.3 | POST /api/teams/{id}/stop | system | ChatInput |
| US-2.4 | — | — | TaimMessage |
| US-3.1 | GET /api/agents | — | AgentRegistryCard |
| US-3.2 | GET /api/agents, GET /api/agents/{name} | — | AgentsView |
| US-3.4 | — | agent_started, agent_state, agent_completed | AgentCard, AgentStateBadge |
| US-3.5 | — | question, agent_state (WAITING) | TaimMessage, AgentStateBadge |
| US-4.1 | POST /api/teams | plan_proposed | PlanCard |
| US-4.3 | POST /api/teams/{id}/start | plan_proposed, approval | PlanCard |
| US-4.4 | — | budget_warning | StatusBar |
| US-4.5 | GET /api/tasks | — | RecentTaskList |
| US-5.1 | — | agent_state | AgentStateBadge |
| US-5.4 | — | agent_completed | AgentCard |
| US-6.1 | POST /api/setup/provider | — | OnboardingOverlay |
| US-6.3 | — | error, system | ErrorMessage, SystemMessage |
| US-7.1 | POST /api/setup/init | — | — |
| US-8.1 | — | agent_completed, result | StatsView |
| US-8.2 | — | agent_progress, agent_completed | StatusBar, ContextBudgetTracker |
| US-8.3 | GET /api/stats/tokens, GET /api/stats/costs | — | StatsView, StatCard |
| US-9.1 | POST /api/chat/sessions | — | ChatView, AppShell |
| US-9.2 | — | agent_started, agent_state, agent_progress, agent_completed | AgentCard, ContextPanel |
| US-9.3 | — | plan_proposed, approval | PlanCard |
| US-9.4 | — | agent_started, agent_completed, budget_warning | StatusBar |
| US-9.5 | GET /api/teams, POST /api/teams/{id}/stop | agent_state, budget_warning | TeamsView, TeamCard, TeamDetailPanel |
| US-11.1 | GET /api/health | system | — |
| US-11.2 | — | — | — |
| US-11.3 | — | — | — |

---

*End of TAIM Phase 1 MVP Product Requirements Document.*
*This document supersedes all individual worker output files for implementation purposes.*
*For full architecture decision rationale: `docs/plans/2026-04-12-architecture-decisions.md`*
*For original project vision: `docs/TAIM-PROJECT-v2.md`*
