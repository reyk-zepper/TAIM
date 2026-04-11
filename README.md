# TAIM — Team AI Manager

> **Your AI team. Your rules. Your control.**
>
> *1 employee = 10. An AI-powered orchestration system that works like an entire team — and gets better the more you use it.*

---

## The Problem

AI agents are powerful. Claude Code, Codex, GPT — individual agents can do impressive work. But the path from "AI exists" to "AI works productively for me" is still full of barriers for most people.

**The Access Gap.** Today's multi-agent tools are built for developers and AI experts. Setting up a system requires writing YAML configs, managing API keys, understanding model differences, defining agent roles, and grasping orchestration logic. This excludes the vast majority of knowledge workers — marketing managers, consultants, project leads, creatives, entrepreneurs — who could benefit enormously from AI teams but don't have the technical depth.

**Fragmentation.** Every agent runs in isolation. Claude Code doesn't know what Codex is doing. One AI system can't leverage the results of another. The human becomes a manual router between AI systems.

**Loss of Control.** Agents run autonomously but without central governance. There's no simple way to say "work on this project for 4 hours, then stop." Budget overruns and infinite loops are the norm.

**No Memory.** Every session starts from zero. Learned preferences, past decisions, optimized workflows — all lost. You have to re-brief from scratch every time.

**Vendor Lock-in.** Most orchestration systems are tied to a single LLM provider. Token quota exhausted? Too bad. Want to switch models? Rebuild everything.

## The Vision: AI Equalizer

**TAIM closes the gap between AI experts and everyone else.**

Today, productive use of AI is an expert topic. Those who know how to write prompts, configure agents, select models, and orchestrate workflows get excellent results. Those who don't have this knowledge fall behind. TAIM eliminates this gap.

The goal is not for everyone to become an AI expert — the goal is for everyone to get expert-level results.

**AI learns you. You don't learn AI.**

TAIM gets better through use. The longer you work with it, the more it adapts to your individual needs. A persistent memory system stores insights, preferences, and optimized workflows. Not through model fine-tuning, but through intelligent accumulation of experience — optimized prompts and few-shot learning from its own memory.

A beginner who uses TAIM for two weeks gets results on the level of a power user — because TAIM has learned what they need and how they work.

## How It Works

You open TAIM. You see a chat. You describe what you need, in your own words. TAIM understands the intent, asks follow-up questions if needed, proposes a plan, and executes after your confirmation.

```
You:   "I need a competitive analysis for our product.
        Look at 5 competitors and create a comparison report."

TAIM:  "I'm assembling a research team:
        - 1 Lead Researcher (coordinates the analysis)
        - 3 Web Researchers (research in parallel)
        - 1 Analyst (evaluates and creates the report)

        Estimated effort: ~2 hours, ~150k tokens (~$4.50)

        Should I start?"

You:   "Yes, but maximum 3 hours and no more than $5."

TAIM:  "Understood. Limits set. Team is starting now.
        I'll get back to you when the report is ready
        or if I have a question."
```

You never saw a YAML file. Never heard "Agent Registry." Never selected a model.

## What Makes TAIM Different

### vs. CrewAI, LangGraph, AutoGen
Framework without UI. No dashboard. No memory. No compliance layer. Developer-only. TAIM is a **finished product** with a conversation-first interface that anyone can use.

### vs. Dify.ai
Good accessibility, but focused on single workflows. No autonomous multi-agent teamwork. No heartbeat control. No self-learning. TAIM orchestrates **teams**, not just workflows.

### vs. Paperclip
Ticket-based, company metaphor. No persistent learning. No multi-LLM failover. TAIM is an **assistant, not a company simulator**.

### vs. OpenClaw
Great personal AI assistant — but single agent. No team/swarm orchestration. No multi-user. TAIM **scales from one agent to coordinated teams**.

## Core Principles

### 1. Conversation First
Natural language is the primary interface. No YAML, no CLI, no model names needed. TAIM works like an experienced team lead you can brief in plain language.

### 2. Progressive Disclosure
Everything has smart defaults. Zero configuration needed to start. Want more control? Dive deeper into YAML, CLI, or API. **Simplicity is the default, complexity is opt-in.**

### 3. Control First
Humans always have control. Approval gates determine when human confirmation is needed. Time and budget limits prevent uncontrolled execution. "Work on this for 4 hours, then stop" is a first-class feature.

### 4. Learn by Use
TAIM improves through usage. Prompt optimization, few-shot learning from memory, accumulated experience. No fine-tuning required.

### 5. No Vendor Lock-in
Any LLM with an API can be used. The router abstracts the provider layer completely. Anthropic, OpenAI, local models via Ollama — switch transparently.

### 6. Compile, Don't Search
Knowledge is compiled ahead of time, not searched at runtime (noRAG philosophy). Saves tokens, increases quality, makes everything auditable. **No RAG. No vectors. No embeddings.**

### 7. Transparency & Auditability
Everything is stored in human-readable formats: Markdown, YAML, SQLite. No black-box behavior.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       TAIM DASHBOARD                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              CONVERSATION LAYER                         │  │
│  │  Natural language as primary interface                   │  │
│  │  "I need a market analysis for our product..."          │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Real-time monitoring · Agent status · Token tracking         │
│  Team management · Memory browser · Analytics                │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST API / WebSocket
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              TWO-STAGE INTENT INTERPRETER                     │
│                                                              │
│  Stage 1: Quick Classification (Tier 3, cheap)               │
│  → Categorize: new task? confirmation? status query?         │
│  → Handles 60-70% of messages instantly                      │
│                                                              │
│  Stage 2: Deep Understanding (Tier 2, when needed)           │
│  → Extract parameters, constraints, missing info             │
│  → Enrich with user memory and preferences                   │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR                              │
│                                                              │
│  Agent Registry · Team Composer · Heartbeat Manager           │
│  Task Manager · Agent State Machines                         │
│                                                              │
│  Orchestration Patterns:                                     │
│  Sequential · Parallel · Pipeline · Hierarchical             │
└──────────────────────────┬───────────────────────────────────┘
                           │
             ┌─────────────┼──────────────┐
             ▼             ▼              ▼
┌─────────────────┐ ┌───────────┐ ┌──────────────┐
│   TAIM BRAIN    │ │   TAIM    │ │  TAIM RULES  │
│                 │ │   ROUTER  │ │   ENGINE     │
│ Three-Layer     │ │           │ │              │
│ Memory:         │ │ Multi-LLM │ │ Compliance   │
│ Hot (session)   │ │ Failover  │ │ profiles,    │
│ Warm (prefs)    │ │ Model     │ │ approval     │
│ Cold (history)  │ │ Tiering   │ │ gates        │
│                 │ │           │ │              │
│ Token-Budgeted  │ │ Error-    │ │              │
│ Context         │ │ Type-     │ │              │
│ Assembly        │ │ Aware     │ │              │
│                 │ │ Handling  │ │              │
│ Compiled        │ │           │ │              │
│ Knowledge       │ │           │ │              │
│ (noRAG)         │ │           │ │              │
└─────────────────┘ └───────────┘ └──────────────┘
```

## Two Layers: Conversation & Configuration

```
┌────────────────────────────────────────────────────┐
│  LAYER 1: CONVERSATION (for everyone)              │
│                                                    │
│  Natural language · Smart defaults                 │
│  Guided onboarding · TAIM explains what it does    │
│                                                    │
│  "Create a competitor analysis"                    │
│  "Stop the team, that's enough"                    │
│  "Why did that take so long?"                      │
└────────────────────┬───────────────────────────────┘
                     │ Want more control? Go deeper.
                     ▼
┌────────────────────────────────────────────────────┐
│  LAYER 2: CONFIGURATION (for power users)          │
│                                                    │
│  YAML configuration · CLI · API access             │
│  Manual agent definitions · Custom rules           │
│  Direct model selection · Prompt engineering       │
└────────────────────────────────────────────────────┘
```

Layer 1 is the main entrance. Layer 2 is the escape hatch for experts. Everything the Conversation Layer does automatically can be overridden in Layer 2. Nobody is forced to ever enter Layer 2.

## Key Innovations

### AI Equalizer
The fundamental shift: **AI learns every user, not every user learns AI.** A beginner with two weeks of TAIM usage gets results equal to a power user — because the system has learned their needs, preferences, and patterns.

### Conversation-First Architecture
Not a chatbot bolted onto a config tool. The entire system is designed around natural language interaction. The Intent Interpreter translates plain speech into structured orchestration commands. Smart Defaults fill in everything the user doesn't specify. Guided Onboarding replaces setup wizards with a conversation.

### Two-Stage Intent Interpretation
Most systems use a single LLM call to understand user input. TAIM uses two stages: a fast, cheap classification (Tier 3) that handles 60-70% of messages instantly, and a deep understanding stage (Tier 2) that only activates for complex requests. This mirrors how humans process requests — first categorize, then analyze. The result: ~40% lower interpreter costs with better accuracy where it matters.

### Agents as State Machines
Every agent runs as an explicit state machine: `PLANNING → EXECUTING → REVIEWING → ITERATING → DONE`. Each state has its own optimized prompt — a "plan your approach" prompt is fundamentally different from a "review your result" prompt. This makes agents debuggable (see what state they're in), controllable (heartbeat can intervene per state), and resumable (state serializes to disk for crash recovery).

### Token-Budgeted Context Assembly
Every agent gets a token budget for its context. The Context Assembler prioritizes ruthlessly: task description first, then rules, then relevant memory, then examples — never exceeding the budget. This is fundamentally different from RAG: TAIM selects by relevance to task + agent role + user preferences, not by semantic similarity. No vectors needed.

### Three-Temperature Memory
Memory is organized in three layers: **Hot** (current session, always in RAM), **Warm** (user preferences, loaded on demand via INDEX.md), and **Cold** (historical data, accessed only when needed). Memory cost scales with relevance, not with total memory size.

### Intelligent Model Tiering
TAIM automatically selects the right model for the right task:
- **Tier 1 (Premium):** Complex reasoning, architecture, strategy
- **Tier 2 (Standard):** Code generation, text processing, analysis
- **Tier 3 (Economy):** Classification, formatting, routing

The user never needs to know about tiering. Power users can override.

### Transparent Failover with Error-Type Awareness
Not just "retry then failover." TAIM distinguishes error types: rate limits get retries, safety filters get prompt adjustments, bad formats get format reminders, low quality gets model escalation. Different errors need different responses. When Provider A hits its limit, the router switches transparently to Provider B. All providers down? Local Ollama at $0 cost.

### Prompts as First-Class Citizens
System prompts are not hardcoded strings — they're versioned YAML files in the TAIM Vault. Editable, auditable, improvable without code changes. This is the foundation for the self-learning system: Phase 2's Learning Loop optimizes prompts, not code. The prompts are the product.

### Self-Learning Memory
Based on the [claudianX](https://github.com/reyk-zepper/claudianX) pattern: structured Markdown notes with frontmatter, INDEX.md as entry point, just-in-time retrieval. No Obsidian dependency, no vector databases. Pure filesystem, human-readable, git-versionable.

### Compiled Knowledge (No RAG)
Based on [noRAG](https://github.com/reyk-zepper/noRAG): Documents are compiled into structured knowledge units ahead of time. 80-90% fewer context tokens, no hallucinations at chunk boundaries, exact source references. **Search is a runtime cost. Compilation is a build cost.**

### Configurable Team Orchestration
Teams support four patterns — Sequential, Parallel, Pipeline, and Hierarchical — auto-selected based on task analysis. A research task gets parallel researchers feeding into a sequential analyst. A code task gets a sequential plan-code-review pipeline. The user never picks the pattern; TAIM does. Power users can override.

### Live Team Observability
A rich WebSocket event stream lets you watch your team work in real-time. Not "waiting for a response" — seeing agent state transitions, progress updates, budget consumption, and intermediate results as they happen. Every event is typed, timestamped, and loggable for audit.

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Backend | Python 3.11+, FastAPI, Uvicorn | Async, WebSocket, LLM ecosystem |
| Frontend | React, TypeScript, Vite, TailwindCSS, Zustand | Real-time updates, minimal state management |
| LLM Integration | LiteLLM + custom failover | Unified API for 100+ providers |
| Storage (Files) | Markdown, YAML | Human-readable, git-versionable |
| Storage (State) | SQLite (single DB, WAL mode) | Zero-config, atomic transactions |
| Knowledge | noRAG (CKU-based) | Compiled knowledge, no RAG |
| Memory | claudianX pattern | Structured, persistent, auditable |
| CLI | Typer + Rich | Type-safe, beautiful output |

## Roadmap

### Phase 1 — Foundation (MVP) `<-- current`
The core loop works: User describes task -> TAIM assembles team -> Agents work -> Result delivered.
- Conversation Layer with two-stage Intent Interpreter
- Guided Onboarding + Smart Defaults
- Agent Registry + Team Composer with orchestration patterns
- Agents as state machines (PLANNING -> EXECUTING -> REVIEWING -> DONE)
- Multi-LLM Router with failover + model tiering + error-type-aware handling
- Three-temperature Agent Memory (claudianX pattern)
- Token-budgeted Context Assembly
- Heartbeat Manager (time/budget limits)
- Token tracking with cost display (always in currency, not just tokens)
- Prompts as versioned vault files
- React Dashboard with integrated chat + live team observability
- CLI for power users

### Phase 2 — Intelligence
The system learns and improves through usage.
- noRAG integration (Compiled Knowledge)
- Learning Loop + Prompt Optimization
- Few-Shot Learning from Memory
- Iteration Controller (automated review rounds)
- SWAT Builder (automatic team spawning)
- Rules Engine (compliance via conversation or YAML)

### Phase 3 — Scale
Multi-user, enterprise readiness, hosted deployment.
- Multi-user with isolated memory
- Role-based access control
- Full dashboard (Memory Browser, Audit Trail)
- Docker + docker-compose
- PostgreSQL support

### Phase 4 — Enterprise
Production-grade for business deployment.
- SSO (SAML/OIDC)
- Kubernetes Helm Chart
- AWS Bedrock / Azure OpenAI native
- MCP server integration
- A2A protocol support

## Building On

TAIM builds on proven, battle-tested components:

- **[noRAG](https://github.com/reyk-zepper/noRAG)** — Knowledge Compiler. Apache 2.0, production-ready. CKU-based knowledge compilation that replaces RAG entirely.
- **[claudianX](https://github.com/reyk-zepper/claudianX)** — Memory Pattern. The structured Markdown + INDEX.md + JIT retrieval pattern that powers TAIM's self-learning memory.
- **[codian](https://github.com/reyk-zepper/codian)** — Proves the claudianX pattern is agent-agnostic. One vault per agent becomes one namespace per agent.

## License

**Apache 2.0** — Free. Open. Forever.

No crippled free tier, no proprietary enterprise extensions. The entire core is freely available, modifiable, and self-hostable.

## Philosophy

> The future of productivity doesn't belong to those who can prompt the best. It belongs to everyone who has ideas and wants results. TAIM makes the difference between "I know AI" and "AI knows me" irrelevant.

---

**TAIM — Team AI Manager**

*Because the future of productivity isn't a better chatbot — it's an intelligent team that works for you, no matter how much you know about AI.*
