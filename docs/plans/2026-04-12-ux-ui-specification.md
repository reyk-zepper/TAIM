# TAIM — UX/UI Specification (Phase 1 MVP)

> Created: 2026-04-12
> Status: Approved — basis for frontend implementation
> Scope: Phase 1 dashboard views only (Chat, Teams, Agents, Stats)

---

## Table of Contents

1. [User Journeys](#1-user-journeys)
2. [Guided Onboarding Flow](#2-guided-onboarding-flow)
3. [Dashboard UI Specification](#3-dashboard-ui-specification)
4. [Conversation Patterns](#4-conversation-patterns)
5. [WebSocket Event → UI Mapping](#5-websocket-event--ui-mapping)
6. [Responsive Behavior](#6-responsive-behavior)
7. [Component Inventory](#7-component-inventory)

---

## 1. User Journeys

Each journey documents: the conversation exchange, what the UI shows, and the state transitions involved.

---

### Journey 1: First-Time User (Guided Onboarding)

**Entry point:** User opens TAIM for the first time. No profile exists. `taim-vault/users/` is empty.

**UI state on load:**
- Full-screen welcome overlay fades in over the chat view
- No sidebar nav items are clickable except Chat
- StatusBar shows: "Not configured"

**Full flow:**

```
[UI: Welcome overlay with TAIM logo and "Let's get you set up" heading]

TAIM (system):  "Welcome. I'm TAIM — your AI team manager.
                 I'll have you set up in 3 minutes.
                 
                 What kind of work do you mainly do?"

[User sees: Single large input field, no distractions]

User:           "I'm a marketing manager at a B2B SaaS company."

TAIM:           "Good to know. Content creation, competitive research,
                 and campaign planning are where I'll help most.
                 
                 Do you have API keys for AI services like Anthropic
                 or OpenAI?"

User:           "I have an Anthropic API key."

[UI: Inline API key input field appears directly in the chat bubble]
[User pastes key — masked with asterisks]
[UI: Small "Key saved securely (local only)" confirmation appears]

TAIM:           "Are there any rules I should follow? Data privacy
                 requirements, brand guidelines, things I must
                 never do?"

User:           "We're GDPR-compliant. No customer data in outputs.
                 Always use formal 'You' in German texts."

TAIM:           "Got it. Here's what I've set up for you:
                 
                 ✓ Anthropic / Claude as primary model
                 ✓ GDPR rule: no customer data in outputs
                 ✓ Style rule: formal 'You' in German texts
                 ✓ Marketing-optimized agent selection
                 
                 You're ready. What do you need?"

[UI: Welcome overlay dismisses. Full dashboard appears.]
[UI: StatusBar updates to show "Ready · 0 agents active · Budget: €0.00"]
[UI: Nav items unlock — Chat active, Teams/Agents/Stats now accessible]
```

**What gets written to vault after onboarding:**

```
taim-vault/users/{username}/INDEX.md
taim-vault/users/{username}/memory/user-profile.md
  — name, role, industry, language preferences
taim-vault/users/{username}/memory/preferences.md
  — output format preferences, verbosity level (default: normal)
taim-vault/config/providers.yaml
  — anthropic key reference (key stored in env/keychain, not in vault)
taim-vault/rules/compliance/session-rules.yaml
  — GDPR: no-customer-data-in-outputs (strict)
taim-vault/rules/behavior/style-rules.yaml
  — German formal address
```

---

### Journey 2: Simple Task (Single Agent)

**Precondition:** User is onboarded. TAIM has a user profile.

**Scenario:** User wants a short email drafted.

```
User:           "Write a follow-up email for a demo call I had with
                 Acme Corp. The call went well, they're evaluating
                 us versus Competitor X. Keep it short."

[UI: "Thinking..." indicator appears — animated dots in chat]

TAIM:           "On it. One moment."

[UI: Agent card appears in the right panel: "Writer · Working"]
[UI: Agent state label: EXECUTING]

[~15 seconds later]

TAIM:           "Here's the draft:
                 
                 ---
                 Subject: Great connecting with you — next steps
                 
                 Hi [Name],
                 
                 Thank you for the time today. It was good to see
                 how [Product] maps to what Acme is building...
                 [full email]
                 ---
                 
                 Want me to adjust the tone, length, or add
                 specific points?"

[UI: Agent card disappears. Cost shown: "€0.02"]
[UI: Copy button appears next to the email block]
```

**UI changes during execution:**
- Agent card in right panel: name, state badge, elapsed time
- Chat shows TAIM's interim acknowledgement immediately
- Result delivered inline in chat as formatted text block
- Copy-to-clipboard button on code/text blocks

---

### Journey 3: Team Task (Multi-Agent)

**Scenario:** Competitive analysis requiring research, analysis, and a written report.

```
User:           "Do a competitive analysis for 5 competitors:
                 Notion, Coda, Confluence, Linear, and Monday.
                 I need a comparison table and a strategic summary."

[UI: "Thinking..." dots appear]

TAIM:           "I'll put together a research team for this:
                 
                 Proposed team:
                 ┌─────────────────────────────────────────────┐
                 │ Research Team                                │
                 │                                             │
                 │ • Lead Researcher     — coordinates the     │
                 │                         analysis            │
                 │ • 3× Web Researcher   — work in parallel    │
                 │   on each competitor                        │
                 │ • Analyst             — synthesizes and     │
                 │                         writes report       │
                 └─────────────────────────────────────────────┘
                 
                 Estimated: ~90 minutes · ~120k tokens · ~€3.60
                 
                 Shall I start?"

[UI: Plan approval card appears in chat with two buttons: "Start" and "Modify"]
```

**User approves:**

```
User:           "Start — but max €5 budget and 2 hours."

TAIM:           "Limits set: €5 max, 2-hour cutoff.
                 Research team is starting now.
                 I'll check in if I have questions."

[UI: Teams view auto-updates — "Research Team" appears as active]
[UI: 5 agent cards appear in chat right panel]
[UI: StatusBar: "5 agents active · Budget: €0.00/€5.00 · 0:00h"]

--- (30 minutes later) ---

[UI: Agent progress updates on cards]
[UI: Budget tracker in StatusBar: €1.20/€5.00]

TAIM (progress): "Researchers have finished the data collection phase.
                  Analyst is now synthesizing findings. About 40 minutes
                  remaining."

--- (70 minutes later) ---

TAIM:           "The competitive analysis is ready.
                 
                 [Comparison Table: Notion / Coda / Confluence / Linear / Monday]
                 [5×5 table with features, pricing, positioning]
                 
                 [Strategic Summary]
                 Based on the analysis, your strongest competitive
                 angle is against Confluence (enterprise migration)
                 and Monday (workflow complexity)...
                 
                 Full report also saved to: reports/competitive-analysis-2026-04-12.md"

[UI: All agent cards show DONE state, then fade out]
[UI: StatusBar: "0 agents active · €3.40 used · 1:10h"]
```

---

### Journey 4: Task with Constraints

**Scenario:** User explicitly defines time and budget limits upfront.

```
User:           "Research the top 3 AI coding assistants. Quick
                 overview — max 20 minutes and max €1."

[UI: Thinking...]

TAIM:           "Got it. Given the tight budget and time:
                 
                 • 1 Researcher (not 3) — covers all three tools
                 • Summary format, not a full report
                 • Economy model tier
                 
                 Estimated: 15–20 minutes · €0.60–€0.90
                 
                 Starting now."

[UI: 1 agent card appears: "Researcher · PLANNING"]
[UI: StatusBar: "1 agent active · Budget: €0.00/€1.00 · 0:00h"]

--- (18 minutes later) ---

TAIM:           "Quick overview of the top 3 AI coding assistants:
                 
                 **GitHub Copilot** — Best IDE integration, large
                 adoption, Microsoft/OpenAI. $10–$19/month.
                 
                 **Cursor** — AI-first IDE, context-aware editing,
                 strong for large codebases. $20/month.
                 
                 **Claude Code** — Terminal-native, strong at complex
                 reasoning and full-repo tasks. $20+/month.
                 
                 Want a deeper dive on any of these?"

[UI: Cost shown: €0.72 · Time: 18:24]
```

**Budget warning scenario (if approaching limit):**

```
[UI: StatusBar turns amber when 80% budget used]
[UI: Budget bar shows orange fill]

TAIM (system):  "Note: 80% of your €1 budget used. I'll wrap up
                 shortly and deliver what's ready."
```

---

### Journey 5: Approval Flow (TAIM Proposes, User Modifies)

**Scenario:** TAIM proposes a team plan. User modifies before approving.

```
User:           "Build out the onboarding flow for our app. 
                 Write the copy, create component specs, and
                 review the existing code."

TAIM:           "This needs three types of work. Here's my plan:
                 
                 Phase 1 (parallel):
                 • UX Writer — drafts onboarding copy
                 • UI Analyst — specifies components
                 
                 Phase 2 (after Phase 1):
                 • Code Reviewer — reviews existing onboarding code
                   against the new specs
                 
                 Estimated: ~3 hours · ~200k tokens · ~€6.00
                 
                 [Start] [Modify Plan] [Cancel]"

User:           "Modify plan — skip the code review, I'll do that
                 myself. Also, use the cheapest model."

TAIM:           "Updated plan:
                 
                 Phase 1 (parallel):
                 • UX Writer — drafts onboarding copy (Economy tier)
                 • UI Analyst — specifies components (Economy tier)
                 
                 Code Review: removed (you'll handle it)
                 
                 Revised estimate: ~1.5 hours · ~80k tokens · ~€1.20
                 
                 [Start] [Modify Again] [Cancel]"

User:           "Start."

TAIM:           "Running the two-agent team now."

[UI: 2 agent cards appear. Plan approval card replaced with progress view.]
```

**Approval flow UI rules:**
- Plan card always has: Start, Modify, Cancel buttons
- After "Modify": user types their changes in the chat input, TAIM regenerates the plan
- Maximum 3 modification rounds before TAIM asks if user wants to start from scratch
- Approved plan is logged to SQLite for audit trail

---

### Journey 6: Stop / Interrupt Running Team

**Scenario:** User wants to stop a running team mid-execution.

```
[UI: Research team has been running for 45 minutes. StatusBar shows 4 agents active.]

User:           "Stop the research team."

TAIM:           "Stopping the research team.
                 
                 Agents finishing current sentences...
                 
                 Team stopped.
                 
                 Here's what was completed before stopping:
                 • Researcher 1: Notion analysis ✓
                 • Researcher 2: Coda analysis ✓  
                 • Researcher 3: Confluence — partially done (60%)
                 • Analyst: not started
                 
                 Partial results saved to:
                 reports/competitive-analysis-partial-2026-04-12.md
                 
                 Cost so far: €1.80 · Time: 0:45h
                 
                 Want to resume later or start fresh?"

[UI: Agent cards fade out with "Stopped" state]
[UI: StatusBar: "0 agents active · €1.80 used · 0:45h (stopped)"]
```

**Emergency stop:**

```
User:           "Stop everything now."

TAIM:           "Stopping all active agents immediately.
                 2 agents stopped. Work saved where possible."

[UI: All agent cards immediately show FAILED/STOPPED state]
[UI: Red stop banner dismisses after 3 seconds]
```

**Stop via UI button:**
- Each agent card has a stop button (square icon)
- Clicking it triggers the same graceful stop sequence
- StatusBar has a global "Stop All" button when agents are active

---

### Journey 7: Status Check During Execution

**Scenario:** User asks what's happening while agents are running.

```
[UI: Research team running. User hasn't watched the UI.]

User:           "What's happening?"

TAIM:           "Here's the current status:
                 
                 Research Team — running 32 minutes
                 
                 • Lead Researcher  REVIEWING   (checking research plan)
                 • Researcher 1     EXECUTING   (analyzing Notion's pricing)
                 • Researcher 2     DONE        (Coda analysis complete)
                 • Researcher 3     EXECUTING   (Linear feature comparison)
                 • Analyst          WAITING     (waiting for researchers)
                 
                 Budget: €1.40 of €5.00 used
                 Estimated completion: ~55 minutes remaining"

User:           "Is Researcher 2's Coda work good?"

TAIM:           "Researcher 2 completed a solid Coda analysis:
                 pricing model, 12 key features, 3 differentiators
                 versus your product noted.
                 
                 Want me to show you the draft now, or wait for
                 the full report?"
```

---

### Journey 8: Error Scenario (Provider Failover)

**Scenario:** Anthropic API fails mid-execution. TAIM failovers transparently.

```
[Researcher is in EXECUTING state. Anthropic returns HTTP 503.]

[UI: Agent card briefly shows orange "Reconnecting..." badge]

--- (internal: TAIM failovers to OpenAI GPT-4o-mini, same tier) ---

[UI: Agent card returns to EXECUTING, orange badge disappears]
[UI: No interruption to the user]
```

**If failover is noticeable (>5 second delay):**

```
TAIM (system):  "Anthropic briefly unavailable. Switched to OpenAI.
                 Continuing — no action needed."

[UI: Small system message in chat, subdued styling]
```

**If all providers fail:**

```
[UI: Agent card shows RED "Failed" state]
[UI: Error banner at top of chat]

TAIM:           "I hit a problem. The AI provider is currently
                 unavailable and the backup also failed.
                 
                 Work saved up to this point.
                 
                 What to do:
                 1. Check your API keys in Settings
                 2. Try again in a few minutes
                 3. Or ask me to continue with a local model (Ollama)
                    — slower, but free
                 
                 What would you like to do?"

[UI: 3 action buttons appear below the error message]
```

**Error UI rules:**
- Never show raw error codes or stack traces in the chat
- Always suggest a human-readable next action
- Error banner is dismissible
- Partial results are always preserved and referenced

---

## 2. Guided Onboarding Flow

### Complete Conversation Script

**Trigger:** First launch — no user profile detected.

---

**Step 1: Welcome**

```
TAIM:   "Welcome. I'm TAIM — your AI team manager.
         
         I help you get expert-level results from AI without
         needing to know how it works.
         
         Let's get you set up in 3 minutes.
         
         What kind of work do you mainly do?"
```

UI: Full-screen centered chat. Single pulsing input field. No navigation visible.

---

**Step 2: Work Context**

User answers with their role/domain. TAIM extracts: industry, role type, likely task types.

```
TAIM:   "[Reflects what TAIM heard — 1 sentence]
         
         Based on that, I'll optimize for [task type A], [task type B],
         and [task type C].
         
         Do you have API keys for AI services like Anthropic
         or OpenAI? (Or I can use local AI if you have Ollama.)"
```

If user says no keys:
```
TAIM:   "No problem. If you have Ollama installed locally, I can use
         that for free — it'll be slower but costs nothing.
         
         Otherwise, you can add keys later in Settings.
         
         For now, let's continue the setup."
```

---

**Step 3: API Key Setup**

```
TAIM:   "Paste your [Anthropic/OpenAI] API key here.
         
         It stays on your machine — never sent anywhere except
         directly to [Anthropic/OpenAI] when agents need to work."
```

UI: Inline password-style input field appears in the chat bubble, not in a modal or form. Paste-and-confirm interaction. After confirmation:

```
TAIM:   "Key saved. [Provider] is ready as your primary AI."
```

Multiple keys: TAIM asks if they have additional keys (one prompt, not a loop).

---

**Step 4: Rules and Compliance**

```
TAIM:   "Last thing: are there any rules I should follow?
         
         For example:
         • Data privacy (GDPR, HIPAA, no customer data in outputs)
         • Brand guidelines (tone, language, style)
         • Things I must never do
         
         If you have nothing specific, just say 'no rules' and
         I'll use sensible defaults."
```

User answers. TAIM extracts and reflects back:

```
TAIM:   "Got it. Rules I've set:
         [• Each rule as a bullet point]
         
         You can always add more rules later by just telling me."
```

---

**Step 5: Confirmation**

```
TAIM:   "You're all set:
         
         ✓ [Provider] ready as primary model
         [✓ Backup: [Provider 2] if listed]
         ✓ [Rule 1 if any]
         ✓ [Rule 2 if any]
         ✓ Optimized for [work context]
         
         What do you need?"
```

UI: Welcome overlay smoothly transitions out. Full dashboard reveals. Navigation unlocks.

---

### What Gets Written to Vault

| File | Content |
|------|---------|
| `taim-vault/users/{name}/INDEX.md` | Warm memory index, initially empty |
| `taim-vault/users/{name}/memory/user-profile.md` | name, role, industry, language, detected timezone |
| `taim-vault/users/{name}/memory/preferences.md` | output format (markdown default), verbosity (normal default) |
| `taim-vault/config/providers.yaml` | Provider name, model list, priority order (no raw keys — those go to env) |
| `taim-vault/rules/compliance/onboarding-rules.yaml` | All compliance rules from Step 4 |
| `taim-vault/rules/behavior/style-rules.yaml` | All style/brand rules from Step 4 |

**API keys are never written to vault.** They are stored in:
- macOS: Keychain via the `keyring` Python library
- Linux/Windows: OS credential store via `keyring`
- Fallback: `.env` file in the TAIM install directory (not in vault)

---

## 3. Dashboard UI Specification

### Overall Layout (Desktop)

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
- Background: `zinc-950` (#09090b)
- Surface: `zinc-900` (#18181b)
- Surface elevated: `zinc-800` (#27272a)
- Border: `zinc-800` (#27272a)
- Text primary: `zinc-50` (#fafafa)
- Text secondary: `zinc-400` (#a1a1aa)
- Text muted: `zinc-600` (#52525b)
- Accent: `violet-500` (#8b5cf6)
- Success: `emerald-500` (#10b981)
- Warning: `amber-500` (#f59e0b)
- Error: `red-500` (#ef4444)
- Agent active: `violet-500`
- Agent done: `emerald-500`
- Agent waiting: `amber-500`
- Agent failed: `red-500`

---

### View: Chat (Main)

This is the default and primary view. It occupies the full main content area.

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│  Chat                              [Clear] [Export]  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  MESSAGE LIST (scrollable, newest at bottom)         │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ TAIM                                         │   │
│  │ Welcome back. Ready for your next task.      │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │                         You                 │    │
│  │  Do a competitive analysis...               │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ TAIM                               [Plan card]│   │
│  │ I'll put together a research team...         │   │
│  │                                              │   │
│  │  ┌────────────────────────────────────────┐  │   │
│  │  │ PLAN                                   │  │   │
│  │  │ • Lead Researcher                      │  │   │
│  │  │ • 3× Web Researcher (parallel)          │  │   │
│  │  │ • Analyst                              │  │   │
│  │  │ Est: 90 min · €3.60                   │  │   │
│  │  │ [  Start  ] [Modify] [Cancel]          │  │   │
│  │  └────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
├─────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────┐    │
│  │ What do you need?                    [Send] │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Context Panel (right, shown when agents active):**

```
┌─────────────────────┐
│ Active Agents  [×]  │
├─────────────────────┤
│ ┌─────────────────┐ │
│ │ Lead Researcher │ │
│ │ ● EXECUTING     │ │
│ │ ████████░░ 80%  │ │
│ │ 0:32h · [Stop]  │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ Researcher 1    │ │
│ │ ● EXECUTING     │ │
│ │ █████░░░░░ 50%  │ │
│ │ 0:28h · [Stop]  │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ Analyst         │ │
│ │ ○ WAITING       │ │
│ │ Waiting for     │ │
│ │ researchers     │ │
│ └─────────────────┘ │
├─────────────────────┤
│ Budget: €1.40/€5    │
│ ████████░░░ 28%     │
│ Time: 0:32h         │
└─────────────────────┘
```

**Message types and their visual treatment:**

| Message Type | Visual Treatment |
|-------------|-----------------|
| User message | Right-aligned, `zinc-800` background, no avatar |
| TAIM response | Left-aligned, `zinc-900` background, TAIM dot avatar |
| Plan card | Inline card with border `violet-500/30`, action buttons |
| Progress update | Subdued, `zinc-700` background, smaller text |
| System notice | Full-width subtle banner, `zinc-800`, centered text |
| Error message | `red-950` background, `red-400` text, action buttons |
| Result/output | `zinc-900` with syntax highlighting if code, copy button |
| Budget warning | `amber-950` background, `amber-400` text |

**Input field:**
- Placeholder: "What do you need?" (first load) / "Continue..." (subsequent)
- Keyboard: `Enter` to send, `Shift+Enter` for newline
- Max height: 6 lines before scroll
- Send button: disabled when empty, violet when active
- Shows character/token estimate (optional, power user setting)

**Thinking indicator:**
- Animated 3-dot loader in TAIM message bubble
- Appears immediately after user sends, before any response
- Replaced by actual content when content starts streaming

**Streaming:**
- TAIM responses stream token by token
- Cursor visible at end of streaming text
- Plan cards appear atomically (not streamed) — wait for full plan before rendering

**Copy button behavior:**
- Appears on hover over any text block
- For code/tables: copies raw content
- For full messages: copies full message text

---

### View: Teams

Shows active and saved team configurations.

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│  Teams                              [+ New Team]     │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ACTIVE                                              │
│  ┌──────────────────────────────────────────────┐   │
│  │ ● Research Team                    RUNNING   │   │
│  │   5 agents · 0:32h · €1.40/€5.00            │   │
│  │   [View Details] [Stop Team]                 │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  SAVED                                              │
│  ┌──────────────────────────────────────────────┐   │
│  │ Frontend Redesign Team              IDLE     │   │
│  │   3 agents · Last run: 3 days ago            │   │
│  │   [Start] [Edit] [Delete]                    │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │ Content Pipeline                    IDLE     │   │
│  │   2 agents · Last run: 1 week ago            │   │
│  │   [Start] [Edit] [Delete]                    │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

**Team Detail Panel (slide-in from right, or expand inline):**

```
┌──────────────────────────────────────────────────────┐
│  Research Team                          [×] Close   │
├──────────────────────────────────────────────────────┤
│  Status: RUNNING · 0:32h elapsed                    │
│                                                      │
│  AGENTS                                              │
│  ┌────────────────────────────────────────────────┐ │
│  │ Lead Researcher  ● REVIEWING   iter 2/3   ⏱ 12m │ │
│  │ Researcher 1     ● EXECUTING   Notion     ⏱ 28m │ │
│  │ Researcher 2     ✓ DONE        Coda       ⏱ 22m │ │
│  │ Researcher 3     ● EXECUTING   Linear     ⏱ 18m │ │
│  │ Analyst          ○ WAITING     pending    ⏱  0m │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  BUDGET                                              │
│  €1.40 of €5.00 · ██████████░░░░░░░░░░░░ 28%       │
│  Tokens: 47,200 of ~120,000 expected                │
│                                                      │
│  TIME                                                │
│  0:32h elapsed · ~55 min estimated remaining        │
│  Time limit: 2:00h · ████████░░░░░░░░ 27% of limit │
│                                                      │
│  [Stop Team]  [Pause]  [Adjust Limits]              │
└──────────────────────────────────────────────────────┘
```

**Components needed:**
- `TeamCard` — summary card with status badge, key metrics, actions
- `TeamDetailPanel` — slide-in detail view
- `AgentStateRow` — single agent in team view (name, state badge, current action, elapsed time)
- `BudgetBar` — dual-bar (cost used / time used)
- `TeamStatusBadge` — RUNNING (green), IDLE (gray), STOPPED (red), DONE (teal)

**WebSocket events affecting this view:**
- `agent_state` → update agent's state badge in team detail
- `agent_progress` → update progress percentage in agent row
- `budget_warning` → turn budget bar amber
- `agent_completed` → agent row shows DONE, check-mark
- `team_completed` → team card updates to DONE, confetti effect optional

---

### View: Agents

Agent Registry browser — read-only for Layer 1, editable for Layer 2.

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│  Agents                  [Search...]   [+ Custom]   │
├──────────────────────────────────────────────────────┤
│  BUILT-IN                                            │
│                                                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐       │
│  │Researcher  │ │Writer      │ │Analyst     │       │
│  │            │ │            │ │            │       │
│  │Web research│ │Long-form   │ │Data and    │       │
│  │data collec-│ │content,    │ │insight     │       │
│  │tion, source│ │reports,    │ │synthesis   │       │
│  │validation  │ │summaries   │ │            │       │
│  │            │ │            │ │            │       │
│  │Tier 2      │ │Tier 2      │ │Tier 2      │       │
│  └────────────┘ └────────────┘ └────────────┘       │
│                                                      │
│  ┌────────────┐ ┌────────────┐                       │
│  │Coder       │ │Reviewer    │                       │
│  │            │ │            │                       │
│  │Code genera-│ │Code review,│                       │
│  │tion, debug │ │security,   │                       │
│  │refactoring │ │quality     │                       │
│  │            │ │            │                       │
│  │Tier 1/2    │ │Tier 2      │                       │
│  └────────────┘ └────────────┘                       │
└──────────────────────────────────────────────────────┘
```

**Agent Detail Card (expanded on click):**

```
┌──────────────────────────────────────────────────────┐
│  Researcher                              [×] Close  │
├──────────────────────────────────────────────────────┤
│  Web research, data collection, source validation   │
│                                                      │
│  CAPABILITIES                                        │
│  • Web browsing and source analysis                 │
│  • Multi-source synthesis                           │
│  • Citation tracking                               │
│  • Fact verification                               │
│                                                      │
│  MODEL PREFERENCE                                    │
│  Primary: Claude Haiku (Tier 2)                     │
│  Fallback: GPT-4o-mini                             │
│                                                      │
│  DEFAULTS                                            │
│  Max iterations: 3                                  │
│  Requires approval for: none                        │
│                                                      │
│  USAGE (this month)                                  │
│  Used in 7 tasks · 14 total runs · avg €0.42/run   │
│                                                      │
│  [Use in Chat] [View YAML ↗]                        │
└──────────────────────────────────────────────────────┘
```

**"View YAML" is Layer 2.** It opens the raw YAML file path in the user's browser or system default. Not an inline editor in Phase 1.

**Components needed:**
- `AgentGrid` — CSS grid of agent cards
- `AgentCard` — compact card with name, capabilities summary, tier badge
- `AgentDetailPanel` — expanded detail view
- `TierBadge` — Tier 1 / Tier 2 / Tier 3 label with color coding

---

### View: Stats

Token usage and cost analytics. Simple, human-readable, no raw token numbers without context.

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│  Stats                                 [This month ▼]│
├──────────────────────────────────────────────────────┤
│                                                      │
│  OVERVIEW                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │Total     │  │Tasks     │  │Avg cost  │           │
│  │€23.40    │  │47        │  │€0.50     │           │
│  │This month│  │completed │  │per task  │           │
│  └──────────┘  └──────────┘  └──────────┘           │
│                                                      │
│  COST OVER TIME                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ Bar chart: daily cost, last 30 days             │ │
│  │ [simple bar chart, zinc + violet colors]        │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  BREAKDOWN BY AGENT                                  │
│  ┌────────────────────────────────────────────────┐ │
│  │ Researcher      ████████████████  €12.40  53%  │ │
│  │ Writer          ████████          €6.80   29%  │ │
│  │ Analyst         ████              €3.20   14%  │ │
│  │ Coder           █                 €1.00    4%  │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  RECENT TASKS                                        │
│  ┌────────────────────────────────────────────────┐ │
│  │ Competitive analysis  2026-04-12  €3.40   90m  │ │
│  │ Email draft           2026-04-11  €0.02    15s │ │
│  │ Code review           2026-04-10  €1.20   45m  │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

**Numbers always shown in EUR (or USD based on user preference). Never raw tokens as primary metric.** Tokens shown as secondary/tooltip information.

**Time period selector:** This month (default), Last 7 days, Last 30 days, All time.

**Components needed:**
- `StatCard` — single metric card (number + label + period)
- `CostBarChart` — simple bar chart using recharts or similar lightweight library
- `AgentBreakdownBar` — horizontal bar list with percentage
- `RecentTaskList` — table of recent tasks with cost + duration

**No real-time updates on Stats view.** Refreshes when navigating to it. No WebSocket connection needed for this view.

---

### View: StatusBar (Footer)

Always visible. Fixed at the bottom of the dashboard.

```
┌────────────────────────────────────────────────────────────────────┐
│  ● 5 agents active    Budget: €1.40 / €5.00 ██████░░░░    0:32h  │
└────────────────────────────────────────────────────────────────────┘
```

**States:**

| State | Display |
|-------|---------|
| Idle, no budget | "Ready · No active tasks" |
| Idle, budget set | "Ready · Budget: €0.00 / €10.00" |
| Running, no budget set | "● 3 agents active · 0:15h · €0.60 used" |
| Running, budget set | "● 3 agents active · Budget: €0.60/€5.00 █████░ · 0:15h" |
| Budget warning (80%) | Amber background · "⚠ 3 agents · Budget: €4.00/€5.00 ████████████████░░ · 0:45h" |
| All done | "✓ Task complete · €3.40 used · 1:10h" (fades after 10s) |
| Error | Red background · "✗ Error — 1 agent failed · [View]" |

**Components needed:**
- `StatusBar` — full-width footer bar
- `AgentCountDot` — animated green dot + count
- `BudgetMiniBar` — compact inline progress bar
- `ElapsedTimer` — counts up while agents are running

---

## 4. Conversation Patterns

### Personality

TAIM communicates as a capable, calm team manager. It is:
- **Direct.** No filler phrases, no "Great question!", no sycophantic openers.
- **Concise.** Says what's needed, nothing more. Uses bullet points for lists, never prose paragraphs for structured data.
- **Confident but not arrogant.** Makes decisions and explains them briefly. Asks for confirmation on big actions, not small ones.
- **Transparent.** Always tells the user what it's doing and what it costs. No hidden actions.
- **Friendly but professional.** Like a senior colleague, not a chatbot.

### Greeting Patterns

**First-ever session:**
```
"Welcome. I'm TAIM — your AI team manager.
 What kind of work do you mainly do?"
```

**Returning user, same day:**
```
"What do you need?"
```

**Returning user, next day (morning):**
```
"Good morning. What are we working on today?"
```

**Returning user after a task left running:**
```
"The competitive analysis from yesterday finished overnight.
 Want to see the results first?"
```

### Follow-Up Questions

TAIM asks follow-up questions only when:
1. A task is ambiguous in a way that would change the team composition
2. A constraint is missing that would affect cost by >50%
3. A required input is genuinely unavailable

TAIM does NOT ask follow-ups for:
- Minor style preferences (it uses defaults from memory)
- Format decisions (it uses what worked before)
- Details it can research itself

**Good follow-up:**
```
TAIM:   "Which 5 competitors should I analyze? (I can suggest
         some if you're not sure.)"
```

**Bad follow-up (TAIM should just decide):**
```
TAIM:   "Would you like the report in bullet points or paragraphs?"
        [TAIM already knows the user's preference from memory]
```

**When genuinely unsure:**
```
TAIM:   "Two ways I can approach this:
         A) Quick summary (15 min, ~€0.40)
         B) Full analysis with sources (90 min, ~€3.00)
         
         Which fits what you need?"
```

### Plan Proposal Format

Plans are always presented as structured cards, not prose:

```
Proposed team:

• [Agent Role] — [1-line purpose]
• [Agent Role] — [1-line purpose]
• [Agent Role] — [1-line purpose]

Estimated: [time] · [token count simplified, e.g. "~120k tokens"] · ~€[cost]

[Start] [Modify] [Cancel]
```

Rules for plan cards:
- Always show the cost estimate in EUR
- Time estimate uses human language: "~15 minutes", "~2 hours", not "1h 47m"
- Token count is shown but never as the primary metric
- Never more than 6 agents in a plan card — if more needed, show summary ("3× Researcher")
- Approval buttons always: Start (primary/violet), Modify (secondary), Cancel (ghost)

### Progress Reporting (During Execution)

TAIM sends proactive progress updates for tasks longer than 5 minutes. Shorter tasks get no mid-execution updates.

**5-minute checkpoint:**
```
"Research is going well. 2 of 5 competitors analyzed.
 About 45 minutes remaining."
```

**On reaching 50% of time limit:**
```
"Halfway through the time limit. 3 researchers done,
 analyst is writing the synthesis now."
```

**When an agent transitions to a new state:**
- Sent only as a system message (subdued styling), not as a full TAIM message
- Example: "Analyst moved from EXECUTING to REVIEWING"

### Result Delivery

Results are delivered inline in chat. Format:

```
[Task summary sentence]

---
[The actual result — formatted appropriately]
---

[Optional: where it was saved]
[Optional: follow-up offer]
```

For long results (>500 words), TAIM provides a summary + link:
```
"Analysis complete.

 TL;DR: Notion and Confluence are your main competitive threats.
 Linear is not a direct competitor.

 [View full report in chat ↓] [Open file]
 
 Full report also saved to: reports/competitive-analysis-2026-04-12.md"
```

### Error Handling Responses

**Provider rate limit (transparent failover, no user action needed):**
```
"Switched providers temporarily. Continuing."
[Subdued system message styling]
```

**Agent failed mid-task:**
```
"The writer hit a problem and stopped working.

 What was done: [summary of completed work]
 
 Options:
 • Retry (I'll try again with a different approach)
 • Continue without this step
 • Cancel the task
 
 What would you like to do?"
```

**No providers available:**
```
"I can't reach any AI provider right now.
 
 Likely causes: API key issue, network problem, or provider outage.
 
 To fix:
 1. Check Settings → Providers
 2. Try again in a few minutes
 3. Or: use a local model if Ollama is running"
```

### Verbosity Levels

Users can set verbosity in Settings or tell TAIM directly ("be more concise").

**Minimal:**
```
User:   "Research the top Python web frameworks."

TAIM:   "Done.
         
         FastAPI (async, high-perf), Django (batteries-included),
         Flask (lightweight). FastAPI currently most popular for
         new projects."
```

**Normal (default):**
```
User:   "Research the top Python web frameworks."

TAIM:   "Here's a summary of the top Python web frameworks:
         
         **FastAPI** — Modern, async, high-performance. Best for
         APIs and microservices. Currently the most-recommended
         for new projects.
         
         **Django** — Full-featured, batteries-included. Best for
         content-heavy apps, admin interfaces, established projects.
         
         **Flask** — Minimal and flexible. Good for simple apps or
         when you want full control over the stack.
         
         Which are you building for?"
```

**Detailed:**
```
[Same task — TAIM provides full comparison table, usage statistics,
 GitHub stars, performance benchmarks, community size, and a
 recommendation with reasoning]
```

---

## 5. WebSocket Event → UI Mapping

Full mapping of all WebSocket event types (from Architecture Decision 6) to UI changes.

### Incoming Events (Server → Client)

| Event | Payload Key Fields | UI Change |
|-------|-------------------|-----------|
| `thinking` | — | Animated 3-dot indicator appears in chat at TAIM position |
| `plan_proposed` | agents[], estimate{time, tokens, cost}, team_id | Plan approval card renders in chat. Context panel shows proposed agents (grayed out, not started). Buttons: Start, Modify, Cancel. |
| `agent_started` | agent_name, task_id, team_id | New agent card appears in context panel (right side). Badge: PLANNING. Toast: "[Agent] started" (3s, auto-dismiss). StatusBar agent count increments. |
| `agent_progress` | agent_name, progress (0-100), message | Progress bar on agent card updates. Optional: last-action text updates below progress bar. |
| `agent_state` | agent_name, state, previous_state | Agent card badge updates (color + label). If state=WAITING: badge turns amber, message "Waiting for input". If state=DONE: badge turns green. |
| `agent_completed` | agent_name, summary, tokens_used, cost | Agent card: badge=DONE (green), progress=100%. Summary text appears below badge. Cost delta shown in context panel budget tracker. Card fades out after 30s unless user has hovered it. |
| `question` | message, options[] | TAIM message appears in chat with optional inline buttons for quick-reply options. Input field focuses. |
| `result` | content, format, task_id, file_path? | Result block renders in chat. Copy button appears. If file_path present: "Saved to [path]" link shown. All agent cards fade to DONE state. |
| `budget_warning` | threshold (0-100), cost_used, cost_limit | StatusBar background: amber. Budget bar turns orange. If in context panel: budget section highlights. Chat system message: "Budget at [X]%". |
| `error` | message, error_type, recoverable, options[] | Agent card: badge=FAILED (red). If recoverable: action buttons appear in chat (Retry, Skip, Cancel). If not recoverable: full error message card with diagnostic info. StatusBar: error state. |
| `system` | message, level (info/warn/error) | Small system message in chat (subdued styling). info: zinc, warn: amber, error: red. |

### Outgoing Messages (Client → Server)

| User Action | Message Sent | Additional Logic |
|-------------|-------------|-----------------|
| Send chat message | `{type: "user_message", content: "..."}` | Clear input field, disable send button until `thinking` received |
| Click "Start" on plan | `{type: "approval", approved: true, metadata: {team_id}}` | Replace plan card with "Starting..." state |
| Click "Cancel" on plan | `{type: "approval", approved: false, metadata: {team_id}}` | Plan card dismisses with animation |
| Click "Modify" on plan | Opens modification input in chat | User types, sends as `user_message` |
| Click Stop on agent card | `{type: "stop", metadata: {task_id}}` | Agent card immediately shows "Stopping..." |
| Click "Stop Team" | `{type: "stop", metadata: {team_id}}` | All agent cards show "Stopping..." |
| Send "Stop everything" in chat | `{type: "stop", content: "stop_all"}` | Handled same as Stop Team |
| Window ping | `{type: "ping"}` | Sent every 30s to keep WebSocket alive |

### Zustand Store Updates per Event

```typescript
// useChatStore
thinking        → set isThinking=true
plan_proposed   → add PlanMessage to messages[]
question        → add QuestionMessage to messages[]
result          → add ResultMessage to messages[], set isThinking=false
error           → add ErrorMessage to messages[], set isThinking=false
system          → add SystemMessage to messages[]

// useTeamStore
agent_started   → add AgentCard to activeAgents[]
agent_progress  → update AgentCard.progress
agent_state     → update AgentCard.state
agent_completed → update AgentCard.state=DONE, set completedAt
plan_proposed   → set pendingPlan

// useStatsStore
agent_completed → increment totalCost by cost delta
budget_warning  → set budgetWarning=true, set warningThreshold
result          → update lastTaskCost, increment taskCount

// useAppStore
agent_started   → increment activeAgentCount
agent_completed → decrement activeAgentCount (if all done: set=0)
error           → set hasError=true
```

---

## 6. Responsive Behavior

### Desktop (primary, ≥1280px)

- Full 3-column layout: nav sidebar (56px collapsed / 200px expanded) + main content + context panel (280px)
- Context panel visible by default when agents are active, hidden otherwise
- StatusBar always visible at full width
- Chat messages max-width: 760px centered in main content area

### Tablet (768px–1279px)

- 2-column layout: nav sidebar (56px, icon-only, always collapsed) + main content
- Context panel: hidden by default, accessible via slide-in toggle button
- StatusBar: condensed — shows only agent count + budget bar + timer
- Chat messages max-width: 100% of main content area minus padding
- Teams/Agents views: 2-column card grids instead of 3-column

### Mobile (<768px)

- Single column. No sidebar.
- Bottom navigation bar (fixed, 56px): Chat, Teams, Agents, Stats icons
- StatusBar: becomes a compact floating pill above the bottom nav
- Chat is the primary/default view on mobile
- Context panel (agent cards): accessible via bottom sheet that slides up
- Plan cards: full-width, scroll vertically
- Teams/Agents views: single-column card lists

**Mobile-specific behaviors:**
- Chat input: full-width, keyboard-aware (viewport adjusts when keyboard opens)
- Agent cards in bottom sheet: swipe down to dismiss
- Thinking indicator: centered in chat view
- Stop button: always accessible via bottom sheet even when context panel not open

### Breakpoints

```typescript
const breakpoints = {
  mobile: 0,      // <768px
  tablet: 768,    // 768px–1279px
  desktop: 1280,  // ≥1280px
}
```

---

## 7. Component Inventory

Complete list of React components needed for Phase 1.

### Layout Components

| Component | Purpose | Location |
|-----------|---------|---------|
| `AppShell` | Overall layout wrapper, handles column layout | `components/layout/AppShell.tsx` |
| `NavSidebar` | Left navigation with icons + labels | `components/layout/NavSidebar.tsx` |
| `NavItem` | Single nav item with icon, label, active state | `components/layout/NavItem.tsx` |
| `ContextPanel` | Right-side collapsible panel | `components/layout/ContextPanel.tsx` |
| `StatusBar` | Footer bar with live metrics | `components/layout/StatusBar.tsx` |
| `MobileNav` | Bottom tab bar for mobile | `components/layout/MobileNav.tsx` |

### Chat Components

| Component | Purpose | Location |
|-----------|---------|---------|
| `ChatView` | Main chat container | `components/Chat.tsx` |
| `MessageList` | Scrollable message history | `components/chat/MessageList.tsx` |
| `UserMessage` | User message bubble | `components/chat/UserMessage.tsx` |
| `TaimMessage` | TAIM response bubble | `components/chat/TaimMessage.tsx` |
| `PlanCard` | Team plan proposal with action buttons | `components/chat/PlanCard.tsx` |
| `SystemMessage` | System notices (small, subdued) | `components/chat/SystemMessage.tsx` |
| `ErrorMessage` | Error display with action buttons | `components/chat/ErrorMessage.tsx` |
| `ResultBlock` | Formatted result output with copy button | `components/chat/ResultBlock.tsx` |
| `ThinkingIndicator` | Animated 3-dot loader | `components/chat/ThinkingIndicator.tsx` |
| `ChatInput` | Message input + send button | `components/chat/ChatInput.tsx` |
| `BudgetWarningBanner` | Inline budget warning in chat | `components/chat/BudgetWarningBanner.tsx` |

### Agent / Context Panel Components

| Component | Purpose | Location |
|-----------|---------|---------|
| `AgentCard` | Single agent card with state + progress | `components/agents/AgentCard.tsx` |
| `AgentStateBadge` | State label with color indicator dot | `components/agents/AgentStateBadge.tsx` |
| `AgentProgressBar` | Thin progress bar | `components/agents/AgentProgressBar.tsx` |
| `ContextBudgetTracker` | Budget mini-display in context panel | `components/agents/ContextBudgetTracker.tsx` |

### Teams View Components

| Component | Purpose | Location |
|-----------|---------|---------|
| `TeamsView` | Teams page container | `components/TeamView.tsx` |
| `TeamCard` | Summary card for a team | `components/teams/TeamCard.tsx` |
| `TeamDetailPanel` | Expanded team details | `components/teams/TeamDetailPanel.tsx` |
| `AgentStateRow` | Single agent in team detail | `components/teams/AgentStateRow.tsx` |
| `TeamStatusBadge` | RUNNING / IDLE / DONE / STOPPED | `components/teams/TeamStatusBadge.tsx` |

### Agents View Components

| Component | Purpose | Location |
|-----------|---------|---------|
| `AgentsView` | Agents registry page | `components/AgentView.tsx` |
| `AgentGrid` | CSS grid container for agent cards | `components/agents/AgentGrid.tsx` |
| `AgentRegistryCard` | Compact card in registry browser | `components/agents/AgentRegistryCard.tsx` |
| `AgentDetailPanel` | Expanded agent detail | `components/agents/AgentDetailPanel.tsx` |
| `TierBadge` | Tier 1 / 2 / 3 colored badge | `components/agents/TierBadge.tsx` |

### Stats View Components

| Component | Purpose | Location |
|-----------|---------|---------|
| `StatsView` | Stats page container | `components/StatsView.tsx` |
| `StatCard` | Single KPI card | `components/stats/StatCard.tsx` |
| `CostBarChart` | Daily cost bar chart | `components/stats/CostBarChart.tsx` |
| `AgentBreakdownBar` | Horizontal cost breakdown by agent | `components/stats/AgentBreakdownBar.tsx` |
| `RecentTaskList` | Table of recent tasks | `components/stats/RecentTaskList.tsx` |

### Onboarding Components

| Component | Purpose | Location |
|-----------|---------|---------|
| `OnboardingOverlay` | Full-screen onboarding wrapper | `components/onboarding/OnboardingOverlay.tsx` |
| `ApiKeyInput` | Masked API key input (inline in chat) | `components/onboarding/ApiKeyInput.tsx` |

### Shared / Primitive Components

| Component | Purpose | Location |
|-----------|---------|---------|
| `Button` | Button with variants (primary/secondary/ghost/danger) | `components/ui/button.tsx` (shadcn) |
| `Badge` | Small label badge | `components/ui/badge.tsx` (shadcn) |
| `Progress` | Progress bar | `components/ui/progress.tsx` (shadcn) |
| `Tooltip` | Hover tooltip | `components/ui/tooltip.tsx` (shadcn) |
| `Sheet` | Slide-in panel | `components/ui/sheet.tsx` (shadcn) |
| `Separator` | Divider line | `components/ui/separator.tsx` (shadcn) |
| `CostDisplay` | Formats cost values in EUR/USD with right precision | `components/shared/CostDisplay.tsx` |
| `ElapsedTimer` | Live counting timer | `components/shared/ElapsedTimer.tsx` |
| `CopyButton` | Copy-to-clipboard with visual feedback | `components/shared/CopyButton.tsx` |

---

## Appendix: Agent State Color Reference

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

*This specification covers all Phase 1 views and interactions. Memory Browser, Rules Editor, and Audit views are explicitly out of Phase 1 scope.*
