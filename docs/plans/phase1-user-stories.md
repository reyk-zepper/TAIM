# Phase 1 User Stories — TAIM MVP

> Version: 1.0
> Date: 2026-04-12
> Scope: Phase 1 MVP only. No Phase 2+ features (Learning Loop, noRAG, SWAT Builder, Rules Engine, Multi-User).

---

## Epic 1: Conversation Layer & Onboarding

### US-1.1: First-Run Guided Onboarding
**As a** first-time user **I want** TAIM to guide me through setup via natural language conversation **so that** I can start using the system without reading documentation or filling in forms.

**Acceptance Criteria:**
- [ ] AC1: On first launch, TAIM greets the user and asks what kind of work they primarily do.
- [ ] AC2: TAIM asks for at least one API key (Anthropic, OpenAI, or points to Ollama as a free option).
- [ ] AC3: TAIM asks about any basic compliance constraints (e.g., "Any rules I should follow?").
- [ ] AC4: After the conversation ends, TAIM confirms what was configured in a short summary (provider, preferences, compliance notes).
- [ ] AC5: All inputs from the onboarding conversation are persisted: provider config in `taim-vault/config/providers.yaml`, user preferences as a warm memory entry in `taim-vault/users/{name}/memory/`.
- [ ] AC6: Onboarding can be re-run via chat ("Let's redo the setup") or CLI (`taim onboarding`).
- [ ] AC7: If the user skips a question, TAIM applies the appropriate smart default without blocking.

**Priority:** P0

---

### US-1.2: Natural Language Task Request
**As a** user **I want** to describe a task in plain language **so that** TAIM understands what I need and proposes a plan — without me knowing anything about agents or YAML.

**Acceptance Criteria:**
- [ ] AC1: The user can type a multi-sentence task description and TAIM returns a proposed plan within 10 seconds.
- [ ] AC2: The plan includes: the team composition (agent roles, count), an estimated time, and an estimated token cost.
- [ ] AC3: TAIM asks a follow-up question only if genuinely critical information is missing (e.g., no API key configured, no target defined at all).
- [ ] AC4: The user can confirm the plan with a natural response ("yes", "go ahead", "sounds good") or a variant.
- [ ] AC5: TAIM does not expose agent YAML, model names, or routing decisions to the user unless explicitly asked.

**Priority:** P0

---

### US-1.3: Smart Defaults Engine
**As a** user **I want** TAIM to fill in all execution parameters I haven't specified **so that** I can give a minimal request and still get a reasonable result.

**Acceptance Criteria:**
- [ ] AC1: Smart defaults are loaded from `taim-vault/config/defaults.yaml` at startup.
- [ ] AC2: Defaults cover at minimum: model tier selection, team size estimate, iteration count (2–3), time limit (proportional to complexity estimate), and output format.
- [ ] AC3: Any default applied is internally logged (not surfaced to user unless asked).
- [ ] AC4: A user can override any default in natural language mid-conversation ("use the cheapest model", "just one researcher", "max 2 hours").
- [ ] AC5: User-specific overrides are persisted as warm memory entries so future tasks apply them automatically.

**Priority:** P0

---

### US-1.4: Inline Constraint Setting via Chat
**As a** user **I want** to set constraints (time limits, budget limits) directly in my task request or as a follow-up **so that** the team doesn't overrun my limits.

**Acceptance Criteria:**
- [ ] AC1: Time constraints in natural language ("max 3 hours", "finish by end of day") are parsed and converted to seconds/timestamps for the Heartbeat Manager.
- [ ] AC2: Budget constraints in natural language ("not more than 5 Euro", "under $10") are parsed and passed to the Router as token budget.
- [ ] AC3: If limits are set, TAIM confirms them: "Limits set: 3 hours max, €5 max. Starting now."
- [ ] AC4: The system proactively sends a warning via WebSocket when 80% of the time or token budget is reached.
- [ ] AC5: When a limit is reached, execution stops gracefully (current agent completes its response, then stops) and the user is informed.

**Priority:** P0

---

### US-1.5: Conversation History Continuity
**As a** user **I want** TAIM to remember what we discussed earlier in the session and across sessions **so that** I don't have to re-explain context.

**Acceptance Criteria:**
- [ ] AC1: Within a session, the last 20 messages are always available in hot memory and used by the Intent Interpreter for context.
- [ ] AC2: Messages beyond the 20-message window are summarized by a Tier 3 model call and stored as a session summary in warm memory.
- [ ] AC3: At session start, TAIM loads the previous session summary and incorporates it into the first user interaction if relevant.
- [ ] AC4: The user can ask "What did we discuss last time?" and TAIM can answer from warm memory.
- [ ] AC5: Chat history is persisted in the SQLite `session_state` table and survives server restarts.

**Priority:** P1

---

## Epic 2: Intent Interpretation

### US-2.1: Stage 1 — Quick Intent Classification
**As the** system **I want** to classify incoming user messages into intent categories using a cheap Tier 3 model call **so that** simple messages (confirmations, status queries) do not incur Tier 2 model costs.

**Acceptance Criteria:**
- [ ] AC1: Stage 1 classifies messages into one of: `new_task`, `confirmation`, `follow_up`, `status_query`, `configuration`, `stop_command`.
- [ ] AC2: Stage 1 uses a Tier 3 model (max 100 tokens input + output combined per call).
- [ ] AC3: Messages classified as `confirmation`, `status_query`, or `stop_command` are handled directly without invoking Stage 2.
- [ ] AC4: Only `new_task`, `configuration`, and ambiguous `follow_up` messages are passed to Stage 2.
- [ ] AC5: Stage 1 uses a prompt loaded from `taim-vault/system/prompts/intent-classifier.yaml`.
- [ ] AC6: Classification result and token cost are logged to `token_tracking` in SQLite.

**Priority:** P0

---

### US-2.2: Stage 2 — Deep Task Understanding
**As the** system **I want** to deeply parse complex user requests using a Tier 2 model **so that** I can extract a structured task command with all necessary parameters.

**Acceptance Criteria:**
- [ ] AC1: Stage 2 outputs a structured JSON object containing: `task_type`, `objective`, `parameters`, `constraints` (time/budget), `missing_info` (list of unknowns), `suggested_team` (optional).
- [ ] AC2: Stage 2 loads the user's warm memory entries (preferences, past task patterns) and includes them as context before calling the LLM.
- [ ] AC3: If `missing_info` is non-empty, Stage 2 generates a single targeted follow-up question (not a list of questions).
- [ ] AC4: Stage 2 uses a prompt loaded from `taim-vault/system/prompts/intent-interpreter.yaml`.
- [ ] AC5: Stage 2 is only invoked when Stage 1 routes to it — never called for simple messages.
- [ ] AC6: The output structured command is passed to the Orchestrator, not shown to the user.

**Priority:** P0

---

### US-2.3: Stop and Cancel Commands
**As a** user **I want** to stop a running team or task at any time using natural language **so that** I have immediate control over what the system is doing.

**Acceptance Criteria:**
- [ ] AC1: Messages like "stop", "cancel", "halt the team", "enough, stop now" are classified as `stop_command` in Stage 1.
- [ ] AC2: On receiving a stop command, all active agents for the user's current team transition to `DONE` state after completing their current LLM call (no mid-stream abort).
- [ ] AC3: TAIM confirms the stop: "Team stopped. Here's what was completed so far: [summary]."
- [ ] AC4: Any partial results are returned to the user rather than discarded.
- [ ] AC5: Stop commands take effect within one Heartbeat interval (default 30 seconds).

**Priority:** P0

---

### US-2.4: Status Query Handling
**As a** user **I want** to ask for the current status of my running team in plain language **so that** I can understand what is happening without navigating to a separate view.

**Acceptance Criteria:**
- [ ] AC1: Messages like "what's happening?", "how far along are you?", "status?" are classified as `status_query` and handled without Stage 2.
- [ ] AC2: The response lists active agents with their current state (PLANNING/EXECUTING/REVIEWING/DONE), current iteration, and estimated remaining time.
- [ ] AC3: The response includes current token usage and approximate cost so far.
- [ ] AC4: Status responses are generated without an LLM call — data comes from the task state table and is formatted as text.
- [ ] AC5: Response latency for status queries is under 500ms.

**Priority:** P1

---

## Epic 3: Agent Management

### US-3.1: Built-in Agent Definitions
**As a** user **I want** TAIM to ship with ready-to-use agent definitions **so that** I can start immediately without defining any agents myself.

**Acceptance Criteria:**
- [ ] AC1: Five built-in agents exist as YAML files in `taim-vault/agents/`: `researcher`, `coder`, `reviewer`, `writer`, `analyst`.
- [ ] AC2: Each agent definition includes: `name`, `description`, `model_preference` (ordered list), `skills`, `max_iterations`, and `requires_approval_for` (list of action types).
- [ ] AC3: Agent definitions are valid and loadable by the Agent Registry on server startup without errors.
- [ ] AC4: Each agent has a corresponding prompt file in `taim-vault/system/prompts/agents/` for each state (planning, executing, reviewing, iterating).
- [ ] AC5: The Team Composer can select and instantiate any built-in agent without any user configuration.

**Priority:** P0

---

### US-3.2: Agent Registry — Load and Query
**As the** system **I want** a centralized Agent Registry that loads all agent definitions at startup and provides query capabilities **so that** the Team Composer can find suitable agents for any task.

**Acceptance Criteria:**
- [ ] AC1: The Agent Registry scans `taim-vault/agents/` at server startup and loads all `.yaml` files into memory.
- [ ] AC2: Registry exposes: `get_agent(name)`, `list_agents()`, `find_agents_by_skill(skill)`.
- [ ] AC3: Invalid YAML files in the agents directory are logged as warnings but do not prevent server startup.
- [ ] AC4: A REST endpoint `GET /api/agents` returns the list of available agents with name and description.
- [ ] AC5: The registry reloads if the agents directory is modified while the server is running (file watch or manual reload trigger).

**Priority:** P0

---

### US-3.3: Power User — Define a Custom Agent via YAML
**As a** power user **I want** to create a custom agent by writing a YAML file in `taim-vault/agents/` **so that** I can extend the system with domain-specific roles.

**Acceptance Criteria:**
- [ ] AC1: Placing a valid agent YAML file in `taim-vault/agents/` and reloading the registry makes the agent available to the Team Composer.
- [ ] AC2: The YAML schema is documented with inline comments in the built-in agent files.
- [ ] AC3: An invalid YAML file generates a clear validation error message (field, expected type, got value) logged to the server log.
- [ ] AC4: The CLI command `taim agent list` displays all registered agents including custom ones.
- [ ] AC5: Custom agents can be selected explicitly via chat: "Use my 'data-engineer' agent for this task."

**Priority:** P1

---

### US-3.4: Agent State Machine Execution
**As the** system **I want** each executing agent to run as an explicit state machine **so that** its status is always debuggable, controllable, and resumable.

**Acceptance Criteria:**
- [ ] AC1: Agent states are: `PLANNING`, `EXECUTING`, `REVIEWING`, `ITERATING`, `WAITING`, `DONE`, `FAILED`.
- [ ] AC2: Each state transition emits a `agent_state` WebSocket event with the agent name and new state.
- [ ] AC3: Agent state is serialized to the `task_state` SQLite table after every transition.
- [ ] AC4: If the server restarts while agents are running, active agent states are restored from SQLite and execution resumes from the last saved state.
- [ ] AC5: Each state uses a distinct prompt loaded from the vault (`planning.yaml`, `executing.yaml`, `reviewing.yaml`, `iterating.yaml`).
- [ ] AC6: Transition from `REVIEWING` to `ITERATING` only happens if the review prompt output signals quality below threshold and the max iteration count has not been reached.
- [ ] AC7: Agents never exceed their configured `max_iterations`; after the limit they transition to `DONE` with their current result.

**Priority:** P0

---

### US-3.5: Approval Gate — User Confirmation Before Sensitive Actions
**As a** user **I want** TAIM to pause and ask for my approval before an agent takes a potentially destructive or sensitive action **so that** I always have final control.

**Acceptance Criteria:**
- [ ] AC1: Each agent definition's `requires_approval_for` list defines which action types trigger an approval gate.
- [ ] AC2: When an agent reaches an approval-required action, it transitions to `WAITING` state and sends a `question` WebSocket event describing the action and asking for confirmation.
- [ ] AC3: Execution is paused until the user responds with an approval (`approved: true`) or rejection (`approved: false`).
- [ ] AC4: On approval, the agent transitions back to `EXECUTING`. On rejection, it transitions to `DONE` and returns whatever it had so far.
- [ ] AC5: The approval gate timeout defaults to 30 minutes; after that, the agent transitions to `DONE` without taking the action and informs the user.

**Priority:** P1

---

## Epic 4: Team Composition & Orchestration

### US-4.1: Automatic Team Composition from Task Description
**As a** user **I want** TAIM to automatically select the right agents for my task **so that** I never have to think about which roles are needed.

**Acceptance Criteria:**
- [ ] AC1: The Team Composer receives the structured task command from the Intent Interpreter and selects agents from the registry.
- [ ] AC2: For a research task, the composer selects at minimum a researcher and an analyst.
- [ ] AC3: For a code task, the composer selects at minimum a coder and a reviewer.
- [ ] AC4: For a writing task, the composer selects at minimum a researcher and a writer.
- [ ] AC5: The proposed team is presented to the user in a `plan_proposed` WebSocket event for confirmation before execution starts.
- [ ] AC6: Team composition uses the prompt at `taim-vault/system/prompts/team-composer.yaml`.

**Priority:** P0

---

### US-4.2: Orchestration Pattern Auto-Selection
**As the** system **I want** the Team Composer to auto-select the appropriate orchestration pattern (Sequential, Parallel, Pipeline, Hierarchical) based on task analysis **so that** users get optimal performance without configuring it.

**Acceptance Criteria:**
- [ ] AC1: Multi-source research tasks default to a Parallel + Sequential pattern (multiple researchers then analyst).
- [ ] AC2: Code tasks default to Sequential (plan → code → review).
- [ ] AC3: Single-topic tasks default to Pipeline (research → analyze → write).
- [ ] AC4: Single-agent tasks skip team orchestration entirely and execute the agent directly.
- [ ] AC5: The selected pattern is logged but not shown to the user unless they ask.
- [ ] AC6: A power user can override the pattern in the team YAML file.

**Priority:** P1

---

### US-4.3: Team Plan Confirmation Flow
**As a** user **I want** to see and explicitly confirm the proposed team plan before execution starts **so that** I can adjust the scope or budget if needed.

**Acceptance Criteria:**
- [ ] AC1: The `plan_proposed` WebSocket event includes: agent roles and counts, orchestration pattern, estimated time, estimated token cost in user currency.
- [ ] AC2: The user can confirm with a natural affirmation or respond with adjustments ("but skip the reviewer" or "make it faster").
- [ ] AC3: If the user adjusts the plan, the Team Composer revises and re-proposes before starting.
- [ ] AC4: After at most 2 rounds of revision, TAIM executes with the latest confirmed plan or the user's latest instruction.
- [ ] AC5: No agents are started until the user has confirmed the plan.

**Priority:** P0

---

### US-4.4: Heartbeat Manager — Time Limit Enforcement
**As a** user **I want** the Heartbeat Manager to enforce time limits and detect stuck agents **so that** execution never runs beyond what I authorized.

**Acceptance Criteria:**
- [ ] AC1: The Heartbeat Manager checks active agents at a configurable interval (default: 30 seconds).
- [ ] AC2: If an agent has not produced a state transition within the timeout threshold (default: 120 seconds), it is marked as stuck and a warning is sent to the user.
- [ ] AC3: If the team-level time limit is reached, all agents are gracefully stopped (complete current LLM call, then transition to DONE).
- [ ] AC4: At 80% of the time limit, a `budget_warning` WebSocket event is sent to the user.
- [ ] AC5: Heartbeat state (last check time, agent status map) is stored in the `session_state` SQLite table.
- [ ] AC6: Heartbeat interval and timeout values are configurable in `taim-vault/config/taim.yaml`.

**Priority:** P0

---

### US-4.5: Task Manager — Internal Task Lifecycle
**As the** system **I want** a Task Manager to track the lifecycle of all task units **so that** state is consistent and recoverable across restarts.

**Acceptance Criteria:**
- [ ] AC1: A task record is created in the `task_state` SQLite table when a user-confirmed plan is executed.
- [ ] AC2: Task record contains: `task_id`, `team_id`, `status` (running/completed/stopped/failed), `created_at`, `completed_at`, `agent_states` (JSON), `token_total`, `cost_total`.
- [ ] AC3: Tasks are updated transactionally (state change + token count atomically).
- [ ] AC4: Completed task records are retained (not deleted) for the Stats and Audit views.
- [ ] AC5: A REST endpoint `GET /api/tasks` returns the list of recent tasks with their status.

**Priority:** P0

---

## Epic 5: Agent Execution Engine

### US-5.1: Per-State Prompt Loading
**As the** system **I want** each agent state to load its own dedicated prompt from the vault **so that** agents get focused, optimized instructions appropriate for what they are doing.

**Acceptance Criteria:**
- [ ] AC1: The executor loads prompts by composing the path: `taim-vault/system/prompts/agents/{agent_name}/{state}.yaml`.
- [ ] AC2: If a state-specific prompt doesn't exist for an agent, the executor falls back to a generic state prompt (`taim-vault/system/prompts/agents/default/{state}.yaml`).
- [ ] AC3: Prompts support variable substitution: `{task_description}`, `{user_preferences}`, `{iteration_count}`, `{previous_result}`.
- [ ] AC4: A missing prompt file (both specific and fallback) causes the agent to transition to `FAILED` with a clear error message.
- [ ] AC5: Prompt loading is tested with a unit test that mocks the vault filesystem.

**Priority:** P0

---

### US-5.2: Context Assembly — Token-Budgeted
**As the** system **I want** the Context Assembler to build an agent's context within a token budget, prioritizing by relevance **so that** context costs are predictable and focused.

**Acceptance Criteria:**
- [ ] AC1: Context is assembled in priority order: task description → active constraints → relevant warm memory entries → few-shot examples from prompt cache → team context.
- [ ] AC2: Token budget defaults: Tier 1 = 4000 tokens, Tier 2 = 2000 tokens, Tier 3 = 800 tokens.
- [ ] AC3: Memory entries are scored for relevance by keyword and tag matching against the task description and agent role. Entries scoring below threshold are excluded.
- [ ] AC4: The assembler never exceeds the budget; it stops adding entries once the budget is reached.
- [ ] AC5: No embeddings, vector search, or similarity computation is used — keyword/tag matching only.
- [ ] AC6: The final assembled context token count is logged alongside the agent run.

**Priority:** P0

---

### US-5.3: Inter-Agent Result Passing
**As the** system **I want** completed agent results to be available as context for subsequent agents in the team **so that** agents can build on each other's work.

**Acceptance Criteria:**
- [ ] AC1: In Sequential and Pipeline patterns, the output of agent N is stored in the `task_state` table and made available to agent N+1 as part of its context assembly (if budget allows).
- [ ] AC2: In Parallel patterns, all parallel agent outputs are collected before being passed to the next sequential stage.
- [ ] AC3: Agent outputs are truncated to a configurable token limit (default: 1000 tokens) when passed as context to prevent budget overflow.
- [ ] AC4: The Context Assembler tracks which agent output was passed and logs it.

**Priority:** P0

---

### US-5.4: Agent Run Logging
**As the** system **I want** every agent run logged to SQLite **so that** the audit trail is complete and the stats view has accurate data.

**Acceptance Criteria:**
- [ ] AC1: An `agent_runs` record is created at agent start with: `run_id`, `agent_name`, `task_id`, `team_id`, `state_transitions` (JSON list), `prompt_tokens`, `completion_tokens`, `cost`, `started_at`, `completed_at`, `model_used`.
- [ ] AC2: The record is updated at each state transition and on completion.
- [ ] AC3: `model_used` records the actual model that responded (not just the preference), capturing any failovers.
- [ ] AC4: Agent runs are linked to their parent task via `task_id`.

**Priority:** P0

---

## Epic 6: LLM Router & Failover

### US-6.1: Multi-Provider Configuration
**As a** user **I want** to configure multiple LLM providers in `providers.yaml` or via onboarding conversation **so that** TAIM can use different providers and fall back if one is unavailable.

**Acceptance Criteria:**
- [ ] AC1: `taim-vault/config/providers.yaml` accepts a list of providers, each with: `name`, `api_key_env` (or inline key), `models` (ordered list), `priority`, `monthly_budget` (optional).
- [ ] AC2: The Router loads and validates the provider config at startup. Missing or invalid configs log a warning but don't crash the server.
- [ ] AC3: Ollama (local) is supported as a provider with `host` config instead of API key.
- [ ] AC4: If no providers are configured, the server starts in a degraded mode and returns a clear error when any LLM call is attempted.
- [ ] AC5: The onboarding conversation generates a valid `providers.yaml` from user inputs.

**Priority:** P0

---

### US-6.2: Model Tiering — Automatic Model Selection
**As the** system **I want** to automatically select the appropriate model tier based on task complexity **so that** the right capability is used at the right cost.

**Acceptance Criteria:**
- [ ] AC1: Three tiers are defined: Tier 1 (premium — complex reasoning, strategy), Tier 2 (standard — code gen, text processing, analysis), Tier 3 (economy — classification, formatting, routing).
- [ ] AC2: The Intent Interpreter Stage 1 always uses Tier 3. Stage 2 always uses Tier 2.
- [ ] AC3: The Team Composer assigns a tier to each agent based on its role and the task complexity.
- [ ] AC4: Tier definitions map to actual models in `providers.yaml` (e.g., Tier 1 → `claude-sonnet-4`, Tier 2 → `claude-haiku-4-5`).
- [ ] AC5: A power user can override the tier for a specific agent in its YAML definition or via chat.

**Priority:** P0

---

### US-6.3: Intelligent Failover Between Providers
**As a** user **I want** TAIM to automatically switch to a backup provider if the primary fails **so that** tasks continue without interruption.

**Acceptance Criteria:**
- [ ] AC1: On HTTP 429 (rate limit), the Router applies exponential backoff on the same provider (2 retries, max 4 seconds wait) before failing over.
- [ ] AC2: On connection error or timeout, the Router immediately fails over to the next provider in priority order.
- [ ] AC3: On content safety filter rejection, the Router retries with a softened prompt once on the same provider, then fails over.
- [ ] AC4: On bad format response (not matching expected JSON structure), the Router retries with a format reminder appended, up to 1 retry.
- [ ] AC5: Maximum 3 total attempts per LLM call (across all retries and failovers combined).
- [ ] AC6: If all providers fail, the agent transitions to `FAILED` and the user receives an `error` WebSocket event with a human-readable explanation and suggestion to check API keys.
- [ ] AC7: Every failover event is logged to `agent_runs` with the reason.

**Priority:** P0

---

### US-6.4: Monthly Budget Enforcement Per Provider
**As a** user **I want** each provider to have an optional monthly budget cap **so that** I never accidentally exceed my intended spend.

**Acceptance Criteria:**
- [ ] AC1: `monthly_budget` in `providers.yaml` sets the soft cap in the user's configured currency.
- [ ] AC2: The Router queries the `token_tracking` table to sum costs for the current calendar month before each call.
- [ ] AC3: If a provider's monthly budget would be exceeded by the call, the Router skips it and moves to the next provider.
- [ ] AC4: When a provider's budget is within 10% of the cap, a `budget_warning` event is sent once per session.
- [ ] AC5: Budget tracking works even when the server restarts (persisted in SQLite, not in-memory).

**Priority:** P1

---

## Epic 7: Memory System (Brain)

### US-7.1: Vault Directory Initialization
**As a** user (or the system on first start) **I want** the TAIM Vault to be automatically created with the correct directory structure **so that** no manual setup is required.

**Acceptance Criteria:**
- [ ] AC1: On first startup, if `taim-vault/` does not exist, the server creates the full directory structure as specified in the project spec.
- [ ] AC2: Default config files are written: `taim-vault/config/taim.yaml`, `providers.yaml`, `defaults.yaml` with commented-out example values.
- [ ] AC3: Built-in agent YAML files are copied into `taim-vault/agents/`.
- [ ] AC4: A `users/default/` namespace is created with an empty `INDEX.md`.
- [ ] AC5: Vault initialization is idempotent — running it again on an existing vault changes nothing.
- [ ] AC6: The vault path is configurable via an environment variable `TAIM_VAULT_PATH`.

**Priority:** P0

---

### US-7.2: Warm Memory — User Preferences Persistence
**As the** system **I want** to persist user preferences as structured Markdown notes with frontmatter **so that** they survive across sessions and are used by the Context Assembler.

**Acceptance Criteria:**
- [ ] AC1: Preferences are stored as Markdown files under `taim-vault/users/{username}/memory/preferences.md` with YAML frontmatter including: `title`, `category`, `tags`, `created`, `updated`.
- [ ] AC2: The `INDEX.md` in the user's namespace is updated every time a new memory entry is created or modified.
- [ ] AC3: Memory entries written during onboarding (e.g., "prefers TypeScript", "DSGVO compliance required") are readable by the Context Assembler on the next session.
- [ ] AC4: The `VaultOps` class provides: `write_memory(user, entry)`, `read_memory(user, filename)`, `update_index(user)`, `scan_index(user)`.
- [ ] AC5: No Obsidian dependency — all operations use standard Python file I/O.

**Priority:** P0

---

### US-7.3: Hot Memory — In-Session Context
**As the** system **I want** to maintain the current session's messages and active task context in an in-memory structure **so that** the Intent Interpreter has immediate access to recent context without disk reads.

**Acceptance Criteria:**
- [ ] AC1: Hot memory is an in-memory dictionary keyed by session ID, containing: last 20 messages, current task context, active team state.
- [ ] AC2: Hot memory is initialized on WebSocket connection and cleared on disconnect.
- [ ] AC3: The Intent Interpreter reads from hot memory before loading any warm entries.
- [ ] AC4: When hot memory grows beyond 20 messages, the oldest messages trigger a summarization job (Tier 3 call) that compresses them into a warm memory entry.
- [ ] AC5: If the server restarts mid-session, hot memory is rebuilt from the `session_state` SQLite table (last 20 messages).

**Priority:** P0

---

### US-7.4: INDEX.md — Lightweight Retrieval Index
**As the** system **I want** to use an `INDEX.md` file as a fast, human-readable catalog of all memory entries **so that** relevant entries can be found without loading all files.

**Acceptance Criteria:**
- [ ] AC1: `INDEX.md` in a user's memory namespace lists all memory entries with: filename, one-line summary, tags (comma-separated), and last-updated date.
- [ ] AC2: The Context Assembler scans `INDEX.md` to find relevant entries by tag and keyword matching against the current task.
- [ ] AC3: Only entries whose tags have at least one match with the task description or agent role are fully loaded.
- [ ] AC4: Scanning `INDEX.md` costs zero LLM calls — it is pure string matching in Python.
- [ ] AC5: `INDEX.md` is regenerated correctly if entries are added, modified, or deleted.

**Priority:** P0

---

### US-7.5: Agent Memory Namespace Isolation
**As the** system **I want** each agent to have its own isolated memory namespace **so that** agent-specific learned patterns don't pollute user or other agent memory.

**Acceptance Criteria:**
- [ ] AC1: Agent memory is stored under `taim-vault/users/{username}/agents/{agent_name}/memory/`.
- [ ] AC2: Agent memory entries follow the same Markdown+frontmatter format as user memory entries.
- [ ] AC3: The Context Assembler loads agent memory (within budget) alongside user memory for context assembly.
- [ ] AC4: Agent memory written during one task is available to the same agent in future tasks.
- [ ] AC5: Agent memory is not accessible cross-user (no shared agent memory in Phase 1).

**Priority:** P1

---

## Epic 8: Token Tracking & Cost Display

### US-8.1: Per-Call Token Tracking
**As the** system **I want** every LLM API call to be logged with its token counts and cost **so that** all downstream reporting is accurate.

**Acceptance Criteria:**
- [ ] AC1: After every successful LLM response, a record is inserted into the `token_tracking` SQLite table with: `call_id`, `agent_run_id`, `task_id`, `model`, `provider`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `timestamp`.
- [ ] AC2: Cost is calculated from a model-to-price mapping stored in `taim-vault/config/providers.yaml` (or a fallback default price table in code).
- [ ] AC3: Failed LLM calls (where no tokens were consumed) are not tracked in `token_tracking` but are logged in the server log.
- [ ] AC4: Token tracking writes are atomic with the associated agent state transition to prevent double-counting.

**Priority:** P0

---

### US-8.2: Real-Time Cost Display in Chat
**As a** user **I want** to see the running token cost of my current task in the chat UI **so that** I am never surprised by the bill.

**Acceptance Criteria:**
- [ ] AC1: Every `agent_progress` and `agent_completed` WebSocket event includes `tokens_used` and `cost` in its metadata.
- [ ] AC2: The status bar in the Dashboard displays the cumulative cost for the current task, updated in real time as events arrive.
- [ ] AC3: Cost is displayed in the user's configured currency (default: USD), formatted as a human-readable value (e.g., "$0.42" not "0.421837").
- [ ] AC4: When the task completes, a final `result` event includes the total cost and total tokens for the entire task.

**Priority:** P0

---

### US-8.3: Monthly Usage Summary
**As a** user **I want** to see a summary of my monthly token usage and costs on the Stats page **so that** I can understand my spending patterns.

**Acceptance Criteria:**
- [ ] AC1: The Stats page displays: total cost current month, total tokens current month, number of tasks run, average cost per task.
- [ ] AC2: Stats are broken down by provider (e.g., "Anthropic: $12.40, OpenAI: $3.20").
- [ ] AC3: A `GET /api/stats/monthly` endpoint returns this data as JSON.
- [ ] AC4: Stats queries run against the SQLite `token_tracking` table using date filtering.
- [ ] AC5: Stats page loads in under 1 second for up to 10,000 tracking records.

**Priority:** P1

---

## Epic 9: Dashboard (Frontend)

### US-9.1: Chat as Primary Dashboard View
**As a** user **I want** the chat interface to be the dominant view when I open the Dashboard **so that** natural language is obviously the primary way to interact with TAIM.

**Acceptance Criteria:**
- [ ] AC1: The Chat view occupies the main content area (minimum 70% of screen width) on all screen sizes above 768px.
- [ ] AC2: The navigation sidebar lists: Chat, Teams, Agents, Stats (Memory, Rules, Audit deferred to Phase 3).
- [ ] AC3: The Dashboard loads within 2 seconds on a local server.
- [ ] AC4: The chat input is focused by default on page load.
- [ ] AC5: New WebSocket messages scroll the chat area into view automatically.

**Priority:** P0

---

### US-9.2: Real-Time Agent Status in Chat
**As a** user **I want** to see live status updates from my running agents appear in the chat conversation **so that** I feel like I'm watching a team work rather than waiting for a response.

**Acceptance Criteria:**
- [ ] AC1: Each `agent_started` event renders a status bubble in the chat (e.g., "Researcher started — PLANNING").
- [ ] AC2: `agent_state` transition events update the existing bubble for that agent (e.g., "Researcher — EXECUTING iteration 1/3").
- [ ] AC3: `agent_progress` events render inline progress text (e.g., "Researcher: Analyzing competitor A...").
- [ ] AC4: `agent_completed` events render a completion bubble with a one-line summary.
- [ ] AC5: Status bubbles are visually distinct from user and TAIM conversational messages.
- [ ] AC6: If 3 or more agents are active, status bubbles are collapsed by default with an expand toggle.

**Priority:** P0

---

### US-9.3: Plan Approval UI Flow
**As a** user **I want** the Dashboard to present the proposed plan visually and let me approve or adjust it with a clear UI interaction **so that** the confirmation step is obvious and frictionless.

**Acceptance Criteria:**
- [ ] AC1: A `plan_proposed` WebSocket event renders a distinct "Plan Card" in the chat with: agent roles listed, estimated time and cost, and two buttons: "Approve" and "Adjust".
- [ ] AC2: Clicking "Approve" sends a WebSocket `approval` message with `approved: true` and the plan card changes to a confirmed state.
- [ ] AC3: Clicking "Adjust" focuses the chat input and pre-fills it with "Change the plan: ".
- [ ] AC4: The user can also approve or adjust by typing in the chat input (no button click required).
- [ ] AC5: The plan card is non-interactive after approval to prevent double-submission.

**Priority:** P0

---

### US-9.4: Status Bar
**As a** user **I want** a persistent status bar at the bottom of the Dashboard showing the number of active agents, current task cost, and elapsed time **so that** I always have operational context visible.

**Acceptance Criteria:**
- [ ] AC1: The status bar shows: number of active agents, cumulative cost of current task (or session total if no task running), elapsed time of current task.
- [ ] AC2: All three values update in real time via WebSocket events without requiring page interaction.
- [ ] AC3: When no task is running, the status bar shows "No active task" and the session total cost.
- [ ] AC4: The status bar is always visible — it does not scroll off screen.

**Priority:** P0

---

### US-9.5: Teams View
**As a** user (or power user) **I want** a Teams view that shows active and recently completed teams **so that** I can monitor running teams and review past results.

**Acceptance Criteria:**
- [ ] AC1: The Teams view lists active teams with: team name, agent count, status, elapsed time, current cost.
- [ ] AC2: The Teams view lists recently completed teams (last 10) with: team name, completion time, total cost, outcome (completed/stopped/failed).
- [ ] AC3: Clicking an active team shows the agent states and their current iteration.
- [ ] AC4: A "Stop Team" button on an active team sends a stop command equivalent to typing "stop" in the chat.
- [ ] AC5: Data is loaded from `GET /api/teams` and updated via WebSocket events.

**Priority:** P1

---

### US-9.6: Agents View
**As a** power user **I want** an Agents view that lists all registered agents with their definitions **so that** I can understand what agents are available and inspect their configuration.

**Acceptance Criteria:**
- [ ] AC1: The Agents view shows all agents from the registry: name, description, model preference, skills.
- [ ] AC2: Clicking an agent shows its full YAML definition in a read-only code view.
- [ ] AC3: A link or instruction is shown for how to add a custom agent (pointing to the vault agents directory).
- [ ] AC4: Data is loaded from `GET /api/agents`.

**Priority:** P2

---

### US-9.7: Stats View
**As a** user **I want** a Stats view showing my token usage and costs **so that** I can track my spending and usage patterns.

**Acceptance Criteria:**
- [ ] AC1: Stats view shows the monthly summary (total cost, total tokens, task count, average cost/task).
- [ ] AC2: Stats view shows a breakdown by provider.
- [ ] AC3: Stats view shows the 10 most recent tasks with their cost and duration.
- [ ] AC4: All data loads from `GET /api/stats/monthly` and `GET /api/tasks`.

**Priority:** P1

---

### US-9.8: WebSocket Connection State Handling
**As a** user **I want** the Dashboard to gracefully handle WebSocket disconnections **so that** my work is not lost and I'm informed if the connection drops.

**Acceptance Criteria:**
- [ ] AC1: A connection indicator (dot or badge) in the UI shows green (connected) or red (disconnected).
- [ ] AC2: On disconnect, the UI attempts automatic reconnection with exponential backoff (5 attempts, max 30 seconds between attempts).
- [ ] AC3: If reconnection succeeds, the chat history is restored from the `session_state` SQLite table and a system message "Connection restored" is shown.
- [ ] AC4: If all reconnection attempts fail, a persistent banner is shown: "Disconnected from TAIM server. Check that the server is running."
- [ ] AC5: Pending messages typed during disconnection are queued and sent on reconnect.

**Priority:** P1

---

## Epic 10: CLI (Power Users)

### US-10.1: CLI — Server Start and Stop
**As a** power user **I want** to start and stop the TAIM server from the command line **so that** I can manage the server process without a launcher or GUI.

**Acceptance Criteria:**
- [ ] AC1: `taim server start` starts the FastAPI server with Uvicorn on the configured host and port (default: `localhost:8000`).
- [ ] AC2: `taim server stop` gracefully shuts down the running server.
- [ ] AC3: `taim server start --port 9000` overrides the default port.
- [ ] AC4: `taim server start --vault /custom/path` overrides the vault path.
- [ ] AC5: Server startup prints the URL to the Dashboard and a brief status summary.

**Priority:** P1

---

### US-10.2: CLI — Submit a Task
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

### US-10.3: CLI — Agent and Team Management
**As a** power user **I want** to list and inspect agents and teams from the CLI **so that** I can manage the system without opening the Dashboard.

**Acceptance Criteria:**
- [ ] AC1: `taim agent list` lists all registered agents with name and description.
- [ ] AC2: `taim agent show researcher` prints the full YAML definition of the named agent.
- [ ] AC3: `taim team list` lists all team blueprints defined in the vault.
- [ ] AC4: `taim team show {name}` prints the full YAML definition of the named team blueprint.
- [ ] AC5: All CLI output uses Rich for formatted, readable terminal output.

**Priority:** P2

---

### US-10.4: CLI — Stats Display
**As a** power user **I want** to view token usage stats from the CLI **so that** I can check costs without opening a browser.

**Acceptance Criteria:**
- [ ] AC1: `taim stats` prints the current month's total cost, total tokens, and task count.
- [ ] AC2: `taim stats --breakdown` additionally prints per-provider cost breakdown.
- [ ] AC3: Output is a clean, readable table formatted with Rich.

**Priority:** P2

---

### US-10.5: CLI — Vault Operations
**As a** power user **I want** CLI commands for basic vault operations **so that** I can inspect and manage the vault from the terminal.

**Acceptance Criteria:**
- [ ] AC1: `taim vault init` creates the vault directory structure (same as server first-start behavior).
- [ ] AC2: `taim vault status` prints the vault path, disk usage, and counts of agents, teams, and memory entries.
- [ ] AC3: `taim vault memory list` lists all warm memory entries for the current user with their tags and last-updated date.

**Priority:** P2

---

## Epic 11: System Setup & Configuration

### US-11.1: TAIM Server — FastAPI Application with WebSocket
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

### US-11.2: Prompts as Vault Files — PromptLoader Utility
**As a** developer **I want** a `PromptLoader` utility that reads prompts from vault YAML files and applies variable substitution **so that** no prompt strings are hardcoded in Python code.

**Acceptance Criteria:**
- [ ] AC1: `PromptLoader.load(prompt_name, variables)` reads from `taim-vault/system/prompts/{prompt_name}.yaml` and substitutes all `{variable}` placeholders.
- [ ] AC2: Missing variable substitutions raise a `PromptVariableError` (not silently inserted as `{variable}`).
- [ ] AC3: Missing prompt file raises a `PromptNotFoundError` with the attempted path.
- [ ] AC4: Prompts are cached in memory after first load; cache is invalidated when the vault file is modified.
- [ ] AC5: `PromptLoader` is unit tested with a mock vault filesystem.
- [ ] AC6: All 20+ prompt files required for Phase 1 exist in the vault before any integration tests run.

**Priority:** P0

---

### US-11.3: SQLite Database Initialization
**As the** system **I want** the SQLite database to be automatically initialized with the correct schema on first run **so that** no manual database setup is required.

**Acceptance Criteria:**
- [ ] AC1: On startup, the server checks if `taim-vault/system/state/taim.db` exists. If not, it runs the schema migration to create all tables.
- [ ] AC2: Tables created: `token_tracking`, `task_state`, `session_state`, `agent_runs` with the columns defined in Architecture Decision 8.
- [ ] AC3: SQLite is opened in WAL mode for better concurrent read performance.
- [ ] AC4: Schema migrations are version-controlled in code (a simple integer version in a `schema_version` table).
- [ ] AC5: Existing databases with an older schema version are migrated, not overwritten.

**Priority:** P0

---

### US-11.4: Environment Variable Configuration
**As an** operator **I want** TAIM's key settings to be configurable via environment variables **so that** I can deploy it in different environments without editing files.

**Acceptance Criteria:**
- [ ] AC1: `TAIM_VAULT_PATH` overrides the default vault path.
- [ ] AC2: `TAIM_HOST` and `TAIM_PORT` override server bind address (defaults: `localhost`, `8000`).
- [ ] AC3: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` are read from environment if not in `providers.yaml`.
- [ ] AC4: A `.env` file in the project root is loaded automatically in development mode (via `python-dotenv`).
- [ ] AC5: `taim server start` with `--env-file .env.prod` loads a specific env file.

**Priority:** P1

---

### US-11.5: Backend Test Coverage
**As a** developer **I want** the core backend logic to have >80% test coverage **so that** the system is reliable and regressions are caught.

**Acceptance Criteria:**
- [ ] AC1: `pytest` runs without errors from the backend directory using `uv run pytest`.
- [ ] AC2: The following modules have individual test files: Intent Interpreter (both stages), Context Assembler, Agent State Machine, Router (tiering + failover), PromptLoader, VaultOps, Token Tracker.
- [ ] AC3: Tests use mocking for LLM calls (no real API calls in unit tests).
- [ ] AC4: Coverage report shows >80% line coverage for `taim/conversation/`, `taim/orchestrator/`, `taim/router/`, `taim/brain/`.
- [ ] AC5: CI-equivalent check: `uv run pytest --cov=taim --cov-report=term-missing` runs cleanly.

**Priority:** P1

---

*Total stories: 52*

*P0 stories (must-have): US-1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 3.1, 3.2, 3.4, 4.1, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 9.1, 9.2, 9.3, 9.4, 11.1, 11.2, 11.3 — 34 stories*

*P1 stories (should-have): US-1.5, 2.4, 3.3, 3.5, 4.2, 6.4, 7.5, 8.3, 9.5, 9.7, 9.8, 10.1, 10.2, 11.4, 11.5 — 15 stories*

*P2 stories (nice-to-have): US-9.6, 10.3, 10.4, 10.5 — 4 stories (not MVP blockers, good first extension targets)*
