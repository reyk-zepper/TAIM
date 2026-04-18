import { useEffect, useState } from 'react'
import { BarChart3, Coins, Zap, ListChecks, Loader2 } from 'lucide-react'

interface ProviderStat {
  provider: string
  calls: number
  total_tokens: number
  cost_usd: number
}

interface MonthlyStats {
  period: string
  total_cost_usd: number
  total_tokens: number
  total_calls: number
  task_count: number
  avg_cost_per_task: number
  by_provider: ProviderStat[]
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string
  value: string
  icon: React.ReactNode
}) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <div className="flex items-center gap-2 text-zinc-500 text-xs mb-2">
        {icon}
        {label}
      </div>
      <p className="text-xl font-semibold">{value}</p>
    </div>
  )
}

export default function StatsView() {
  const [stats, setStats] = useState<MonthlyStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/stats/monthly')
      .then((r) => r.json())
      .then((data) => setStats(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="p-6 flex items-center gap-2 text-zinc-500">
        <Loader2 size={16} className="animate-spin" />
        Loading stats...
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="p-6 text-zinc-500">
        Could not load stats. Is the backend running?
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h2 className="text-xl font-semibold mb-6">Monthly Stats</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <StatCard
          label="Total Cost"
          value={`$${stats.total_cost_usd.toFixed(2)}`}
          icon={<Coins size={14} />}
        />
        <StatCard
          label="Total Tokens"
          value={stats.total_tokens.toLocaleString()}
          icon={<Zap size={14} />}
        />
        <StatCard
          label="Tasks"
          value={String(stats.task_count)}
          icon={<ListChecks size={14} />}
        />
        <StatCard
          label="Avg Cost/Task"
          value={`$${stats.avg_cost_per_task.toFixed(4)}`}
          icon={<BarChart3 size={14} />}
        />
      </div>

      {stats.by_provider.length > 0 && (
        <>
          <h3 className="text-sm font-medium text-zinc-400 mb-3">By Provider</h3>
          <div className="space-y-2">
            {stats.by_provider.map((p) => (
              <div
                key={p.provider}
                className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 flex items-center justify-between"
              >
                <span className="text-sm font-medium">{p.provider}</span>
                <div className="flex gap-4 text-xs text-zinc-500">
                  <span>{p.calls} calls</span>
                  <span>{p.total_tokens.toLocaleString()} tokens</span>
                  <span className="text-zinc-300">${p.cost_usd.toFixed(4)}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
