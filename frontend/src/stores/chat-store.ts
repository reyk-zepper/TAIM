import { create } from 'zustand'

export interface ChatMessage {
  id: string
  type:
    | 'user'
    | 'assistant'
    | 'system'
    | 'thinking'
    | 'onboarding'
    | 'plan_proposed'
    | 'agent_started'
    | 'agent_state'
    | 'agent_completed'
    | 'tool_execution'
    | 'error'
  content: string
  agentName?: string
  plan?: {
    task_id: string
    objective: string
    agents: Array<{ role: string; agent_name: string }>
    pattern: string
  }
  toState?: string
  category?: string
  confidence?: number
  costEur?: number
  tokensUsed?: number
  durationMs?: number
  step?: string
  timestamp: number
}

interface ChatStore {
  messages: ChatMessage[]
  isConnected: boolean
  isThinking: boolean
  activePlan: ChatMessage['plan'] | null
  addMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => void
  updateAgentBubble: (agentName: string, toState: string, iteration?: number) => void
  setConnected: (connected: boolean) => void
  setThinking: (thinking: boolean) => void
  setActivePlan: (plan: ChatMessage['plan'] | null) => void
  clearMessages: () => void
}

let nextId = 0

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isConnected: false,
  isThinking: false,
  activePlan: null,
  addMessage: (msg) =>
    set((state) => ({
      messages: [
        ...state.messages,
        { ...msg, id: String(++nextId), timestamp: Date.now() },
      ],
    })),
  updateAgentBubble: (agentName, toState, iteration) =>
    set((state) => {
      const msgs = [...state.messages]
      // Find the last agent_started or agent_state for this agent
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (
          (msgs[i].type === 'agent_started' || msgs[i].type === 'agent_state') &&
          msgs[i].agentName === agentName
        ) {
          msgs[i] = {
            ...msgs[i],
            type: 'agent_state',
            toState,
            content: `${agentName}: ${toState}${iteration ? ` (iteration ${iteration})` : ''}`,
          }
          return { messages: msgs }
        }
      }
      return state
    }),
  setConnected: (connected) => set({ isConnected: connected }),
  setThinking: (thinking) => set({ isThinking: thinking }),
  setActivePlan: (plan) => set({ activePlan: plan }),
  clearMessages: () => set({ messages: [] }),
}))
