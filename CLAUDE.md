# TAIM — Project Instructions for Claude Code

## What is TAIM?

TAIM (Team AI Manager) is an open-source AI team orchestration system. It lets any user — regardless of technical expertise — manage AI agent teams through natural language. "1 employee = 10."

The full project specification is in `docs/TAIM-PROJECT-v2.md`. Read it before making architectural decisions.

## Core Philosophy

1. **Conversation First** — Natural language is the primary interface. No user should need to write YAML or use a CLI to get results. The Conversation Layer is the main entrance; configuration is the opt-in escape hatch for power users.
2. **AI Equalizer** — Every user gets expert-level results regardless of AI knowledge. The system learns the user, not the other way around.
3. **Progressive Disclosure** — Everything has smart defaults. Zero configuration needed to start. Complexity is opt-in.
4. **Compile, Don't Search** — No RAG. Knowledge is compiled ahead of time (noRAG approach). No vectors, no embeddings, no chunking.
5. **Control First** — Humans always have control. Approval gates, time limits, budget limits.

## Architecture (Phase 1 MVP)

```
Dashboard (React + Chat) 
    → Intent Interpreter (NL → structured commands)
    → Orchestrator (Agent Registry, Team Composer, Heartbeat, Tasks)
    → Router (Multi-LLM, Failover, Token Tracking)
    → Brain (Agent Memory using claudianX pattern)
    → API Server (FastAPI + WebSocket)
```

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, Uvicorn, SQLite, Typer (CLI)
- **Frontend:** React, TypeScript, Vite, TailwindCSS, Shadcn/ui
- **LLM Integration:** LiteLLM as transport layer, custom failover logic on top
- **Storage:** Filesystem (Markdown/YAML) as source of truth, SQLite for indexes and state
- **Package Manager:** uv (Python), pnpm (Frontend)

## Project Structure

```
taim/
├── CLAUDE.md                    # This file
├── docs/
│   └── TAIM-PROJECT-v2.md      # Full project specification
├── backend/
│   ├── pyproject.toml
│   └── src/taim/
│       ├── __init__.py
│       ├── main.py              # FastAPI app entry
│       ├── api/                 # REST API routes
│       │   ├── __init__.py
│       │   ├── chat.py          # Conversation Layer endpoint (WebSocket)
│       │   ├── teams.py         # Team management
│       │   ├── agents.py        # Agent registry
│       │   └── stats.py         # Token tracking, analytics
│       ├── conversation/        # Conversation Layer
│       │   ├── __init__.py
│       │   ├── interpreter.py   # Intent Interpreter (NL → commands)
│       │   ├── onboarding.py    # Guided Onboarding flow
│       │   └── defaults.py      # Smart Defaults engine
│       ├── orchestrator/        # Core orchestration
│       │   ├── __init__.py
│       │   ├── registry.py      # Agent Registry
│       │   ├── composer.py      # Team Composer + auto-suggest
│       │   ├── heartbeat.py     # Heartbeat Manager
│       │   ├── tasks.py         # Task Manager
│       │   └── executor.py      # Agent execution engine
│       ├── router/              # LLM Router
│       │   ├── __init__.py
│       │   ├── provider.py      # Multi-provider management
│       │   ├── failover.py      # Failover logic
│       │   ├── tiering.py       # Model tier selection
│       │   └── tracking.py      # Token/cost tracking
│       ├── brain/               # Knowledge & Memory
│       │   ├── __init__.py
│       │   ├── memory.py        # Agent Memory (claudianX pattern)
│       │   ├── assembler.py     # Context Assembler
│       │   └── vault.py         # TAIM Vault filesystem operations
│       ├── models/              # Pydantic models
│       │   ├── __init__.py
│       │   ├── agent.py
│       │   ├── team.py
│       │   ├── task.py
│       │   └── config.py
│       └── cli/                 # CLI (Ebene 2)
│           ├── __init__.py
│           └── main.py
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Chat.tsx         # Conversation Layer UI
│   │   │   ├── TeamView.tsx
│   │   │   ├── AgentView.tsx
│   │   │   ├── StatsView.tsx
│   │   │   └── StatusBar.tsx
│   │   ├── hooks/
│   │   └── lib/
│   └── index.html
├── taim-vault/                  # Default vault location
│   ├── config/
│   │   ├── taim.yaml
│   │   ├── providers.yaml
│   │   └── defaults.yaml
│   ├── agents/                  # Built-in agent definitions
│   ├── teams/
│   ├── rules/
│   ├── shared/
│   ├── users/
│   └── system/
└── tests/
    ├── backend/
    └── frontend/
```

## Existing Code to Integrate

These repositories contain code that TAIM builds upon:

- **noRAG** (https://github.com/reyk-zepper/noRAG) — Knowledge Compiler. Phase 2 integration. Do NOT implement RAG. When knowledge compilation is needed, integrate noRAG's CKU approach.
- **claudianX** (https://github.com/reyk-zepper/claudianX) — The memory pattern. Phase 1: implement the INDEX.md + structured Markdown notes + JIT retrieval pattern for Agent Memory. Do NOT depend on Obsidian.
- **codian** (https://github.com/reyk-zepper/codian) — Proves the claudianX pattern is agent-agnostic.

## Development Conventions

- Python: Use `uv` for package management. Type hints everywhere. Pydantic v2 for models.
- Frontend: Use `pnpm`. Functional components with hooks. TailwindCSS utilities only.
- Tests: pytest for backend, vitest for frontend. Aim for >80% coverage on core logic.
- All config files are YAML. All knowledge files are Markdown. SQLite for indexes.
- API follows REST conventions. WebSocket for real-time (chat, status updates).
- Commit messages: conventional commits (feat:, fix:, docs:, refactor:).
- Language: Code and comments in English. User-facing strings bilingual (DE/EN) where possible.

## What NOT to Build

- No RAG pipeline. No vector database. No embeddings. No chunking.
- No Obsidian dependency. Filesystem operations only.
- No ticket system. Tasks are internal orchestration units.
- No drag-and-drop workflow builder.
- No fine-tuning capabilities.
- No account creation or cloud services. Self-hosted only.

## Current Phase: 1 — Foundation (MVP)

Focus exclusively on Phase 1 scope. Do not implement Phase 2+ features unless explicitly asked.

Phase 1 deliverables:
- [ ] FastAPI server with WebSocket support
- [ ] Conversation Layer with Intent Interpreter
- [ ] Guided Onboarding flow
- [ ] Smart Defaults engine
- [ ] Agent Registry (YAML-based)
- [ ] Team Composer with auto-suggest
- [ ] LLM Router with multi-provider + failover
- [ ] Agent Memory (claudianX pattern, no Obsidian)
- [ ] Heartbeat Manager (time limits, status checks)
- [ ] Token tracking (per agent, per task)
- [ ] React Dashboard with integrated chat
- [ ] CLI for power users
- [ ] Default agent definitions (researcher, coder, reviewer, writer, analyst)
- [ ] TAIM Vault directory structure with defaults
