import { useEffect, useState } from 'react'
import { Clock, CheckCircle2, XCircle, Loader2 } from 'lucide-react'

interface Task {
  task_id: string
  status: string
  objective: string
  token_total: number
  cost_total_eur: number
  created_at: string
  completed_at: string | null
}

const statusConfig: Record<string, { icon: React.ReactNode; color: string }> = {
  completed: { icon: <CheckCircle2 size={14} />, color: 'text-emerald-400' },
  running: { icon: <Loader2 size={14} className="animate-spin" />, color: 'text-violet-400' },
  failed: { icon: <XCircle size={14} />, color: 'text-red-400' },
  stopped: { icon: <XCircle size={14} />, color: 'text-amber-400' },
  pending: { icon: <Clock size={14} />, color: 'text-zinc-400' },
}

export default function TeamsView() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/tasks?limit=20')
      .then((r) => r.json())
      .then((data) => setTasks(data.tasks || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h2 className="text-xl font-semibold mb-6">Recent Tasks</h2>
      {loading && (
        <div className="flex items-center gap-2 text-zinc-500">
          <Loader2 size={16} className="animate-spin" />
          Loading...
        </div>
      )}
      {!loading && tasks.length === 0 && (
        <p className="text-zinc-500">No tasks yet. Start one from the Chat view.</p>
      )}
      <div className="space-y-2">
        {tasks.map((task) => {
          const cfg = statusConfig[task.status] || statusConfig.pending
          return (
            <div
              key={task.task_id}
              className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 flex items-center justify-between"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{task.objective || 'Untitled task'}</p>
                <p className="text-xs text-zinc-500 mt-1">
                  {task.created_at ? new Date(task.created_at).toLocaleString() : ''}
                </p>
              </div>
              <div className="flex items-center gap-4 ml-4">
                <span className="text-xs text-zinc-500">
                  €{(task.cost_total_eur || 0).toFixed(4)}
                </span>
                <div className={`flex items-center gap-1 text-xs ${cfg.color}`}>
                  {cfg.icon}
                  <span>{task.status}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
