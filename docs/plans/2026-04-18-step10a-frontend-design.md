# Step 10a: React Dashboard — Chat UI — Design

> Version: 1.0
> Date: 2026-04-18
> Status: Reviewed
> Scope: US-9.1 (Chat as primary view), US-9.2 (Agent status in chat), US-9.3 (Plan approval), US-9.4 (StatusBar), US-9.8 partial (basic WS)

---

## 1. Overview

Step 10a builds the **functional Chat UI** — the primary way users interact with tAIm.

```
┌──────────────────────────────────────────────────────┐
│  tAIm                                                 │
├──────────┬───────────────────────────────────────────┤
│          │                                            │
│  Nav     │    Chat View (70%+ width)                  │
│          │    ┌──────────────────────────┐            │
│  Chat ●  │    │ MessageList              │            │
│  Teams   │    │  - UserMessage           │            │
│  Agents  │    │  - TaimMessage           │            │
│  Stats   │    │  - PlanCard              │            │
│          │    │  - AgentStatusBubble     │            │
│          │    │  - OnboardingMessage     │            │
│          │    └──────────────────────────┘            │
│          │    ┌──────────────────────────┐            │
│          │    │ ChatInput                │            │
│          │    └──────────────────────────┘            │
├──────────┴───────────────────────────────────────────┤
│  StatusBar: Active agents: 0 | Cost: €0.00 | Idle    │
└──────────────────────────────────────────────────────┘
```

## 2. Tech Stack Setup

```bash
pnpm add zustand lucide-react
pnpm add -D @tailwindcss/vite tailwindcss
# Shadcn init after Tailwind is configured
```

**Tailwind CSS v4** (plugin-based, no PostCSS config file needed — uses `@tailwindcss/vite`).

**Zustand** stores (AD-9):
- `useChatStore` — messages, WebSocket state, input
- `useAppStore` — navigation, active view

## 3. File Structure

```
frontend/src/
├── main.tsx
├── App.tsx
├── index.css                    # Tailwind directives
├── lib/
│   ├── websocket.ts             # WS connection manager
│   └── cn.ts                    # class merge utility
├── stores/
│   ├── chat-store.ts            # Messages, WS state
│   └── app-store.ts             # Navigation, active view
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx
│   │   ├── NavSidebar.tsx
│   │   └── StatusBar.tsx
│   ├── chat/
│   │   ├── ChatView.tsx
│   │   ├── ChatInput.tsx
│   │   ├── MessageList.tsx
│   │   ├── UserMessage.tsx
│   │   ├── TaimMessage.tsx
│   │   ├── PlanCard.tsx
│   │   ├── AgentStatusBubble.tsx
│   │   ├── OnboardingMessage.tsx
│   │   ├── ThinkingIndicator.tsx
│   │   └── SystemMessage.tsx
│   └── ui/                      # Shared primitives
│       └── button.tsx
└── types/
    └── ws-events.ts             # WebSocket event types
```

## 4. WebSocket Manager (`lib/websocket.ts`)

```typescript
type WSEvent = {
  type: string
  content?: string
  session_id?: string
  [key: string]: unknown
}

type EventHandler = (event: WSEvent) => void

class WebSocketManager {
  private ws: WebSocket | null = null
  private sessionId: string
  private handlers: Map<string, EventHandler[]> = new Map()

  constructor(sessionId: string) { this.sessionId = sessionId }

  connect(url: string): void {
    this.ws = new WebSocket(`${url}/ws/${this.sessionId}`)
    this.ws.onmessage = (e) => {
      const event: WSEvent = JSON.parse(e.data)
      const handlers = this.handlers.get(event.type) || []
      handlers.forEach(h => h(event))
      // Also fire catch-all
      this.handlers.get('*')?.forEach(h => h(event))
    }
  }

  send(content: string): void {
    this.ws?.send(JSON.stringify({ content }))
  }

  on(type: string, handler: EventHandler): void {
    if (!this.handlers.has(type)) this.handlers.set(type, [])
    this.handlers.get(type)!.push(handler)
  }

  disconnect(): void { this.ws?.close() }
}
```

## 5. Zustand Stores

### chat-store.ts
```typescript
interface ChatMessage {
  id: string
  type: 'user' | 'assistant' | 'system' | 'thinking' | 'onboarding'
       | 'plan_proposed' | 'agent_started' | 'agent_state'
       | 'agent_completed' | 'tool_execution' | 'error'
  content: string
  agentName?: string
  plan?: object
  category?: string
  confidence?: number
  costEur?: number
  tokensUsed?: number
  timestamp: number
}

interface ChatStore {
  messages: ChatMessage[]
  isConnected: boolean
  isThinking: boolean
  activePlan: object | null   // pending plan_proposed
  addMessage: (msg: ChatMessage) => void
  setConnected: (connected: boolean) => void
  setThinking: (thinking: boolean) => void
  setActivePlan: (plan: object | null) => void
  clearMessages: () => void
}
```

### app-store.ts
```typescript
type View = 'chat' | 'teams' | 'agents' | 'stats'

interface AppStore {
  activeView: View
  setActiveView: (view: View) => void
  activeAgents: number
  currentCostEur: number
  setActiveAgents: (n: number) => void
  setCurrentCost: (c: number) => void
}
```

## 6. Key Components

### AppShell
- Sidebar (fixed left, 200px) + main content area + StatusBar (fixed bottom)
- Active view from `useAppStore`
- Dark theme: zinc-950 background, zinc-100 text

### ChatView
- Connects WebSocket on mount
- Routes events to store via handlers
- Auto-scrolls on new messages
- Shows OnboardingMessage for `onboarding` events

### ChatInput
- Textarea with Enter to send (Shift+Enter for newline)
- Disabled while thinking
- Auto-focus on mount

### PlanCard
- Rendered when `plan_proposed` event arrives
- Shows agent names, pattern, estimated cost
- "Approve" button sends confirmation message
- "Adjust" button focuses input with "Change the plan: " prefix
- Non-interactive after approval

### AgentStatusBubble
- Rendered for `agent_started` / `agent_state` events
- Shows agent name + current state with colored dot
- Updates in-place (same agent = update, not new bubble)

### StatusBar
- Fixed bottom bar
- Shows: active agents count, current cost (€), elapsed time or "Idle"
- Updated from store via WebSocket events

## 7. Design Language

- **Dark theme** with zinc-950 base, violet accents for agent states
- **Agent state colors** per PRD Section 7: PLANNING=violet, EXECUTING=violet-pulse, REVIEWING=amber, DONE=emerald, FAILED=red
- **Minimal chrome** — chat is the hero, UI gets out of the way
- **No gradients/shadows** — flat, clean, monospace-friendly

## 8. Implementation Plan

### Task 1: Setup (Tailwind + Zustand + base files)
- Install deps, configure Tailwind v4, create stores, cn utility
- Clean up Vite scaffold (remove default App.tsx content)

### Task 2: AppShell + NavSidebar + StatusBar
- Layout components with dark theme

### Task 3: ChatView + ChatInput + MessageList + basic message types
- WebSocket connection, message rendering, input handling

### Task 4: PlanCard + AgentStatusBubble + OnboardingMessage + ThinkingIndicator
- Specialized message types for all event categories

### Task 5: Wire everything + smoke test with running backend

---

*End of Step 10a Design.*
