import { Activity, DollarSign } from 'lucide-react'
import { useAppStore } from '../../stores/app-store'
import { useChatStore } from '../../stores/chat-store'

export default function StatusBar() {
  const activeAgents = useAppStore((s) => s.activeAgents)
  const costEur = useAppStore((s) => s.currentCostEur)
  const isConnected = useChatStore((s) => s.isConnected)

  return (
    <div className="h-8 border-t border-zinc-800 bg-zinc-950 flex items-center px-4 gap-6 text-xs text-zinc-500">
      <div className="flex items-center gap-1.5">
        <div
          className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-red-500'}`}
        />
        <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <Activity size={12} />
        <span>
          {activeAgents > 0
            ? `${activeAgents} agent${activeAgents > 1 ? 's' : ''} active`
            : 'Idle'}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <DollarSign size={12} />
        <span>€{costEur.toFixed(4)}</span>
      </div>
    </div>
  )
}
