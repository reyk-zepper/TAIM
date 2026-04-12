# TAIM Phase 1 MVP — API Contracts & Data Models

> Status: Draft for PRD integration
> Date: 2026-04-12

---

## 1. REST API Endpoints

### POST /api/chat/sessions

**Description:** Create a new chat session. Returns a session ID used to open the WebSocket connection.

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

---

### GET /api/chat/sessions/{session_id}/history

**Description:** Returns chat message history for a session.

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

---

### GET /api/teams

**Description:** List all teams.

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

---

### POST /api/teams

**Description:** Create a team directly (Layer 2).

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

**Response (201):** Team object with status `blueprint`.

---

### GET /api/teams/{team_id}

**Description:** Get full team details with per-agent status and token usage.

**Response (200):** Full team object including agents array with state machine states, tasks array, and token_summary.

---

### POST /api/teams/{team_id}/start

**Description:** Start a blueprint/paused team.

**Request Body:**
```json
{
  "task_description": "Analysiere 5 Wettbewerber",
  "constraints": { "time_limit_minutes": 180, "budget_eur": 5.00 },
  "session_id": "sess_01J5XYZ"
}
```

---

### POST /api/teams/{team_id}/stop

**Description:** Stop a running team.

**Request Body:**
```json
{ "mode": "graceful", "reason": "User requested stop" }
```

---

### GET /api/agents

**Description:** List all agents from registry.

**Query Parameters:** `skills` (comma-separated filter), `available_only` (bool)

---

### GET /api/agents/{agent_name}

**Description:** Get full agent definition with runtime stats.

---

### GET /api/stats/tokens

**Description:** Token usage statistics by period, filterable by team/agent.

**Query Parameters:** `period` (today|week|month|all), `team_id`, `agent_name`

---

### GET /api/stats/costs

**Description:** Cost breakdown in EUR with provider-level detail and budget tracking.

---

### GET /api/health

**Description:** Health check with subsystem status (database, vault, providers, orchestrator).

---

### POST /api/setup/init

**Description:** Initialize TAIM vault. Idempotent.

---

### POST /api/setup/provider

**Description:** Register/update an LLM provider. Tests connection.

---

## 2. WebSocket Protocol

**Endpoint:** `ws://{host}/ws/chat/{session_id}`

### Server → Client Events

```typescript
type WSEvent = {
  type: "thinking" | "plan_proposed" | "agent_started" | "agent_progress" |
        "agent_state" | "agent_completed" | "question" | "result" |
        "budget_warning" | "error" | "system"
  content: string
  timestamp: string
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
    progress?: number        // 0-100
    plan?: TeamPlan
    budget_threshold_pct?: number
    error_type?: string
    retry_in_seconds?: number
  }
}
```

### Client → Server Messages

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

---

## 3. Pydantic Models (29 models)

### Agent Models (agent.py)
- `AgentStateEnum` — PLANNING, EXECUTING, REVIEWING, ITERATING, WAITING, DONE, FAILED
- `ModelTierEnum` — tier1_premium, tier2_standard, tier3_economy
- `Agent` — Registry definition (name, model_preference, skills, tools, max_iterations, model_tier)
- `AgentState` — Runtime state (current_state, iteration, tokens_used, cost_eur, state_history)
- `AgentRun` — Execution record (final_state, tokens, cost, provider, failover_occurred)
- `MemoryLayer` — HOT, WARM, COLD
- `MemoryEntry` — Markdown note with frontmatter (title, category, tags, confidence, source)
- `MemoryIndex` — In-memory INDEX.md representation
- `MemoryIndexEntry` — One line in INDEX.md

### Team Models (team.py)
- `OrchestrationPattern` — sequential, parallel, pipeline, hierarchical
- `OnLimitReached` — graceful_stop, immediate_stop, notify_only
- `TeamStatus` — blueprint, active, paused, completed, failed
- `TeamConfig` — Constraints (time_limit, token_budget, budget_eur, iterations, heartbeat)
- `TeamAgentSlot` — Role-to-agent mapping
- `TeamPlan` — Proposed plan for user approval
- `Team` — Full team definition

### Task Models (task.py)
- `TaskStatus` — pending, in_progress, waiting_approval, completed, failed, cancelled
- `TaskResult` — Output with content, type, quality_score
- `Task` — Internal orchestration unit

### Chat & Intent Models (chat.py)
- `ChatMessage` — Single message with metadata
- `ChatSession` — Session with summary support
- `IntentCategory` — new_task, confirmation, follow_up, status_query, configuration, stop_command, onboarding_response
- `IntentClassification` — Stage 1 output (category, confidence, needs_deep_analysis)
- `TaskConstraints` — Extracted constraints (time, budget, specific agents)
- `IntentResult` — Stage 2 output (task_type, parameters, constraints, missing_info, suggested_team)

### Config & Tracking Models (config.py)
- `ProviderConfig` — Provider definition (name, api_key_env, models, priority, budget)
- `TokenUsage` — Per-call tracking record
- `CostEntry` — Aggregated cost for reporting
- `VaultConfig` — Runtime vault paths
- `SystemConfig` — Merged configuration

### WebSocket Models (chat.py)
- `WSEvent` — Server→Client envelope
- `WSMessage` — Client→Server envelope
