import { useState } from 'react'
import { Check, Pencil } from 'lucide-react'

interface PlanCardProps {
  content: string
  plan?: {
    task_id: string
    objective: string
    agents: Array<{ role: string; agent_name: string }>
    pattern: string
  }
}

export default function PlanCard({ content: _content, plan }: PlanCardProps) {
  const [approved, setApproved] = useState(false)

  if (!plan) return null

  return (
    <div className="max-w-[80%] bg-zinc-900 border border-violet-500/40 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-800">
        <p className="text-sm font-medium text-violet-300">Team Plan</p>
        <p className="text-xs text-zinc-400 mt-1">{plan.objective}</p>
      </div>
      <div className="px-4 py-3 space-y-1.5">
        {plan.agents.map((a, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <div className="w-2 h-2 rounded-full bg-violet-400" />
            <span className="text-zinc-300">{a.agent_name}</span>
            <span className="text-zinc-600 text-xs">({a.role})</span>
          </div>
        ))}
        <p className="text-xs text-zinc-500 mt-2">
          Pattern: {plan.pattern} · {plan.agents.length} agent{plan.agents.length > 1 ? 's' : ''}
        </p>
      </div>
      {!approved && (
        <div className="px-4 py-2.5 border-t border-zinc-800 flex gap-2">
          <button
            onClick={() => setApproved(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-emerald-600 text-white rounded hover:bg-emerald-500 transition-colors"
          >
            <Check size={12} />
            Approve
          </button>
          <button
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-zinc-800 text-zinc-300 rounded hover:bg-zinc-700 transition-colors"
          >
            <Pencil size={12} />
            Adjust
          </button>
        </div>
      )}
      {approved && (
        <div className="px-4 py-2 border-t border-zinc-800 text-xs text-emerald-400">
          Plan approved — starting execution
        </div>
      )}
    </div>
  )
}
