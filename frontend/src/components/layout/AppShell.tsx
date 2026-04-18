import { useAppStore } from '../../stores/app-store'
import NavSidebar from './NavSidebar'
import StatusBar from './StatusBar'
import ChatView from '../chat/ChatView'

function PlaceholderView({ name }: { name: string }) {
  return (
    <div className="flex items-center justify-center h-full text-zinc-500">
      <p className="text-lg">{name} view — coming in Step 10b</p>
    </div>
  )
}

export default function AppShell() {
  const activeView = useAppStore((s) => s.activeView)

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100">
      <NavSidebar />
      <main className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-hidden">
          {activeView === 'chat' && <ChatView />}
          {activeView === 'teams' && <PlaceholderView name="Teams" />}
          {activeView === 'agents' && <PlaceholderView name="Agents" />}
          {activeView === 'stats' && <PlaceholderView name="Stats" />}
        </div>
        <StatusBar />
      </main>
    </div>
  )
}
