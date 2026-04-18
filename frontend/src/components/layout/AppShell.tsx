import { useAppStore } from '../../stores/app-store'
import NavSidebar from './NavSidebar'
import StatusBar from './StatusBar'
import ChatView from '../chat/ChatView'
import TeamsView from '../teams/TeamsView'
import AgentsView from '../agents/AgentsView'
import StatsView from '../stats/StatsView'

export default function AppShell() {
  const activeView = useAppStore((s) => s.activeView)

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100">
      <NavSidebar />
      <main className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-hidden">
          {activeView === 'chat' && <ChatView />}
          {activeView === 'teams' && <TeamsView />}
          {activeView === 'agents' && <AgentsView />}
          {activeView === 'stats' && <StatsView />}
        </div>
        <StatusBar />
      </main>
    </div>
  )
}
