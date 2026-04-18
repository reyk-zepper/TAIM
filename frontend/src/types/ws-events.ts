export interface WSEvent {
  type: string
  content?: string
  session_id?: string
  agent_name?: string
  tool_name?: string
  tool_status?: string
  from_state?: string | null
  to_state?: string
  iteration?: number
  reason?: string
  category?: string
  confidence?: number
  plan?: {
    task_id: string
    objective: string
    agents: Array<{ role: string; agent_name: string }>
    pattern: string
  }
  intent?: Record<string, unknown> | null
  tokens_used?: number
  cost_eur?: number
  duration_ms?: number
  step?: string
  error?: string
}
