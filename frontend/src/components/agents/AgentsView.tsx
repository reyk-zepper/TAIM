import { useEffect, useState } from 'react'
import { Bot, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'

interface Agent {
  name: string
  description: string
  skills: string[]
  model_preference?: string[]
  tools?: string[]
  max_iterations?: number
}

export default function AgentsView() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/agents')
      .then((r) => r.json())
      .then((data) => setAgents(data.agents || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const toggleExpand = (name: string) => {
    if (expanded === name) {
      setExpanded(null)
    } else {
      fetch(`/api/agents/${name}`)
        .then((r) => r.json())
        .then((full) => {
          setAgents((prev) =>
            prev.map((a) => (a.name === name ? { ...a, ...full } : a))
          )
          setExpanded(name)
        })
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h2 className="text-xl font-semibold mb-6">Agents</h2>
      {loading && (
        <div className="flex items-center gap-2 text-zinc-500">
          <Loader2 size={16} className="animate-spin" />
          Loading...
        </div>
      )}
      <div className="space-y-2">
        {agents.map((agent) => (
          <div
            key={agent.name}
            className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden"
          >
            <button
              onClick={() => toggleExpand(agent.name)}
              className="w-full px-4 py-3 flex items-center gap-3 text-left hover:bg-zinc-800/50 transition-colors"
            >
              <Bot size={16} className="text-violet-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{agent.name}</p>
                <p className="text-xs text-zinc-500 truncate">{agent.description}</p>
              </div>
              {expanded === agent.name ? (
                <ChevronDown size={14} className="text-zinc-500" />
              ) : (
                <ChevronRight size={14} className="text-zinc-500" />
              )}
            </button>
            {expanded === agent.name && (
              <div className="px-4 py-3 border-t border-zinc-800 space-y-2 text-xs">
                <div>
                  <span className="text-zinc-500">Skills: </span>
                  <span className="text-zinc-300">
                    {agent.skills?.join(', ') || 'none'}
                  </span>
                </div>
                {agent.tools && agent.tools.length > 0 && (
                  <div>
                    <span className="text-zinc-500">Tools: </span>
                    <span className="text-zinc-300">{agent.tools.join(', ')}</span>
                  </div>
                )}
                {agent.model_preference && (
                  <div>
                    <span className="text-zinc-500">Model preference: </span>
                    <span className="text-zinc-300">
                      {agent.model_preference.join(' → ')}
                    </span>
                  </div>
                )}
                {agent.max_iterations && (
                  <div>
                    <span className="text-zinc-500">Max iterations: </span>
                    <span className="text-zinc-300">{agent.max_iterations}</span>
                  </div>
                )}
                <p className="text-zinc-600 mt-2">
                  Custom agents: add YAML to taim-vault/agents/
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
