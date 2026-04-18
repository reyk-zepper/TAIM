import { create } from 'zustand'

export type View = 'chat' | 'teams' | 'agents' | 'stats'

interface AppStore {
  activeView: View
  setActiveView: (view: View) => void
  activeAgents: number
  currentCostEur: number
  elapsedMs: number
  setActiveAgents: (n: number) => void
  setCurrentCost: (c: number) => void
  setElapsedMs: (ms: number) => void
}

export const useAppStore = create<AppStore>((set) => ({
  activeView: 'chat',
  setActiveView: (view) => set({ activeView: view }),
  activeAgents: 0,
  currentCostEur: 0,
  elapsedMs: 0,
  setActiveAgents: (n) => set({ activeAgents: n }),
  setCurrentCost: (c) => set({ currentCostEur: c }),
  setElapsedMs: (ms) => set({ elapsedMs: ms }),
}))
