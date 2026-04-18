import { cn } from '../../lib/cn'

const stateColors: Record<string, string> = {
  PLANNING: 'bg-violet-400',
  EXECUTING: 'bg-violet-500 animate-pulse',
  REVIEWING: 'bg-amber-400',
  ITERATING: 'bg-orange-400',
  WAITING: 'bg-amber-500',
  DONE: 'bg-emerald-500',
  FAILED: 'bg-red-500',
}

interface AgentStatusBubbleProps {
  agentName: string
  state: string
  content: string
}

export default function AgentStatusBubble({
  agentName,
  state,
  content: _content,
}: AgentStatusBubbleProps) {
  const dotColor = stateColors[state] || 'bg-zinc-500'

  return (
    <div className="flex items-center gap-2 py-1 text-xs text-zinc-500">
      <div className={cn('w-2 h-2 rounded-full', dotColor)} />
      <span className="text-zinc-400">{agentName}</span>
      <span className="text-zinc-600">— {state}</span>
    </div>
  )
}
