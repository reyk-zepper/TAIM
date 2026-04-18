import { MessageSquare, Users, Bot, BarChart3 } from 'lucide-react'
import { useAppStore, type View } from '../../stores/app-store'
import { cn } from '../../lib/cn'

const navItems: Array<{ view: View; label: string; icon: React.ReactNode }> = [
  { view: 'chat', label: 'Chat', icon: <MessageSquare size={18} /> },
  { view: 'teams', label: 'Teams', icon: <Users size={18} /> },
  { view: 'agents', label: 'Agents', icon: <Bot size={18} /> },
  { view: 'stats', label: 'Stats', icon: <BarChart3 size={18} /> },
]

export default function NavSidebar() {
  const activeView = useAppStore((s) => s.activeView)
  const setActiveView = useAppStore((s) => s.setActiveView)

  return (
    <nav className="w-48 border-r border-zinc-800 flex flex-col bg-zinc-950">
      <div className="p-4 border-b border-zinc-800">
        <h1 className="text-lg font-bold">
          t<span className="text-violet-400">AI</span>m
        </h1>
      </div>
      <div className="flex-1 py-2">
        {navItems.map((item) => (
          <button
            key={item.view}
            onClick={() => setActiveView(item.view)}
            className={cn(
              'w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
              activeView === item.view
                ? 'text-violet-400 bg-violet-400/10 border-r-2 border-violet-400'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
            )}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </div>
      <div className="p-4 border-t border-zinc-800 text-xs text-zinc-600">
        v0.1.0
      </div>
    </nav>
  )
}
