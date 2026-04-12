# TAIM Phase 1 MVP — Technical Requirements

> Status: Draft for PRD integration
> Date: 2026-04-12

---

## 1. Non-Functional Requirements (21 NFRs)

| ID | Name | Target | Rationale |
|----|------|--------|-----------|
| NFR-01 | Intent Stage 1 Latency | p95 < 500ms | Stage 1 handles 60-70% of messages; slowness makes everything feel sluggish |
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
| NFR-17 | Code Style | ruff check + format pass with zero violations | Consistent style, already configured |
| NFR-18 | Type Safety | Zero `Any` in non-test code, complete annotations | Especially critical for state machine serialization |
| NFR-19 | Structured Logging | JSON format, every LLM call logged with tokens/latency | Enable post-hoc debugging of multi-agent sessions |
| NFR-20 | Token Tracking | Per-call recording within 100ms, granular by agent/task/team | Dashboard stats require granular data from day one |
| NFR-21 | Audit Trail | All user actions and system decisions append-only | Transparency principle |

---

## 2. Missing Dependencies

### Backend (must add to pyproject.toml)
| Package | Purpose |
|---------|---------|
| `python-frontmatter>=1.1.0` | Parse Markdown+YAML frontmatter for memory notes |
| `tiktoken>=0.7.0` | Token counting for context budget enforcement |
| `python-dotenv>=1.0.0` | Load .env file for development |
| `structlog>=24.1.0` | Structured JSON logging |
| `pytest-mock>=3.14.0` (dev) | Mock fixtures for LLM mocking |
| `respx>=0.21.0` (dev) | HTTP request mocking for LiteLLM |

### Frontend (must add)
| Package | Purpose |
|---------|---------|
| `zustand ^5.0.0` | State management |
| `@tailwindcss/vite ^4.0.0` | TailwindCSS v4 |
| `class-variance-authority ^0.7.0` | Component variants (Shadcn) |
| `clsx ^2.1.0` | Conditional class merging |
| `tailwind-merge ^3.0.0` | Tailwind class deduplication |
| `lucide-react ^0.400.0` | Icons |
| `zod ^3.23.0` | Schema validation for WS messages |
| `vitest ^3.0.0` (dev) | Test runner |
| `@testing-library/react ^16.0.0` (dev) | Component testing |
| `msw ^2.3.0` (dev) | WebSocket mocking |

---

## 3. Infrastructure

### SQLite Configuration
- Single DB at `taim-vault/system/state/taim.db`
- WAL mode, foreign keys ON, busy_timeout 5000ms
- Tables: `token_tracking`, `task_state`, `session_state`, `agent_runs`
- Schema-as-code (created on startup, no migration tool in Phase 1)

### Environment Variables
**Required:** `ANTHROPIC_API_KEY` (or another provider key)
**Optional:** `TAIM_VAULT_PATH`, `TAIM_HOST`, `TAIM_PORT`, `TAIM_LOG_LEVEL`, `TAIM_CORS_ORIGINS`, `TAIM_SESSION_TOKEN`, `TAIM_ENV`

### Ports
- Backend: 8000 (configurable)
- Frontend dev: 5173
- Ollama: 11434 (external)

---

## 4. Technical Constraints (Hard Rules)

1. **No RAG, ever.** No vectors, no embeddings, no chunking, no similarity search.
2. **No Obsidian dependency.** Plain filesystem via pathlib + aiofiles.
3. **Prompts never hardcoded.** All in `taim-vault/system/prompts/*.yaml`.
4. **LiteLLM as transport only.** Failover/retry/tiering are TAIM's own logic.
5. **SQLite for state only.** YAML = config source of truth. Markdown = memory source of truth.
6. **Python 3.11+ required.** May use match statements, TaskGroup, etc.
7. **All config YAML, all memory Markdown.** No JSON configs, no plain text memory.
8. **No cloud services.** Self-hosted, no telemetry, no external auth in Phase 1.

---

## 5. Testing Strategy

### Backend (pytest)
- Unit tests: interpreter, state machine, context assembler, memory, failover, tracking, composer, vault
- Integration tests: WebSocket round-trip, REST endpoints, full flow (message → team → result)
- LLM mocking: `pytest-mock` for unit, `respx` for integration (mock HTTP responses)
- Coverage: 75% overall floor, 80% per core module

### Frontend (vitest)
- Unit tests: Zustand stores, key components
- Integration: MSW WebSocket mock → store → component render
- Coverage: 70% line coverage

---

## 6. Development Workflow

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

## 7. Risk Register (7 Risks)

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| RISK-01 | LiteLLM API instability | Medium | High | Pin version, isolate behind single interface, test HTTP shapes |
| RISK-02 | WebSocket connection management | Medium | High | ConnectionManager class, decouple agents from WS, client auto-reconnect |
| RISK-03 | Prompt quality = system quality | High | High | Test cases in prompt YAML, manual eval script, document tested model |
| RISK-04 | SQLite write contention | Low | Medium | WAL mode, asyncio.Lock, busy_timeout, best-effort for tracking |
| RISK-05 | Context budget without exact token counting | Medium | Medium | tiktoken cl100k_base + 10% safety margin, log estimate vs actual |
| RISK-06 | Vault filesystem corruption | Low | High | Atomic writes (.tmp + rename), startup integrity check, CLI check command |
| RISK-07 | Stage 1 intent misclassification | Medium | High | Confidence threshold (< 0.80 → escalate to Stage 2), log all classifications |
