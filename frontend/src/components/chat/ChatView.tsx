import { useEffect, useRef } from 'react'
import { WebSocketManager } from '../../lib/websocket'
import { useChatStore } from '../../stores/chat-store'
import { useAppStore } from '../../stores/app-store'
import ChatInput from './ChatInput'
import MessageList from './MessageList'

function generateSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export default function ChatView() {
  const wsRef = useRef<WebSocketManager | null>(null)
  const addMessage = useChatStore((s) => s.addMessage)
  const updateAgentBubble = useChatStore((s) => s.updateAgentBubble)
  const setConnected = useChatStore((s) => s.setConnected)
  const setThinking = useChatStore((s) => s.setThinking)
  const setActivePlan = useChatStore((s) => s.setActivePlan)
  const setActiveAgents = useAppStore((s) => s.setActiveAgents)
  const setCurrentCost = useAppStore((s) => s.setCurrentCost)

  useEffect(() => {
    const sessionId = generateSessionId()
    const ws = new WebSocketManager(sessionId)
    wsRef.current = ws

    let wasConnected = false
    ws.on('_connected', () => {
      setConnected(true)
      if (wasConnected) {
        addMessage({ type: 'system', content: 'Connection restored.' })
      }
      wasConnected = true
    })

    ws.on('_disconnected', () => setConnected(false))

    ws.on('_reconnecting', (e) => {
      addMessage({ type: 'system', content: e.content || 'Reconnecting...' })
    })

    ws.on('_reconnect_failed', () => {
      addMessage({
        type: 'error',
        content: 'Disconnected from tAIm server. Check that the server is running and refresh the page.',
      })
    })

    ws.on('thinking', () => setThinking(true))

    ws.on('onboarding', (e) => {
      setThinking(false)
      addMessage({ type: 'onboarding', content: e.content || '', step: e.step })
    })

    ws.on('system', (e) => {
      setThinking(false)
      addMessage({ type: 'system', content: e.content || '' })
    })

    ws.on('intent', (e) => {
      setThinking(false)
      addMessage({
        type: 'assistant',
        content: e.content || '',
        category: e.category,
        confidence: e.confidence,
      })
    })

    ws.on('plan_proposed', (e) => {
      setThinking(false)
      setActivePlan(e.plan || null)
      addMessage({
        type: 'plan_proposed',
        content: e.content || '',
        plan: e.plan,
      })
    })

    ws.on('agent_started', (e) => {
      setActiveAgents(1)
      addMessage({
        type: 'agent_started',
        content: e.content || '',
        agentName: e.agent_name,
      })
    })

    ws.on('agent_state', (e) => {
      if (e.agent_name && e.to_state) {
        updateAgentBubble(e.agent_name, e.to_state, e.iteration)
      }
    })

    ws.on('tool_execution', (e) => {
      addMessage({
        type: 'tool_execution',
        content: e.content || `${e.agent_name}: ${e.tool_name} (${e.tool_status})`,
        agentName: e.agent_name,
      })
    })

    ws.on('agent_completed', (e) => {
      setThinking(false)
      setActiveAgents(0)
      if (e.cost_eur !== undefined) setCurrentCost(e.cost_eur)
      addMessage({
        type: 'agent_completed',
        content: e.content || '',
        agentName: e.agent_name,
        costEur: e.cost_eur,
        tokensUsed: e.tokens_used,
        durationMs: e.duration_ms,
      })
    })

    ws.on('error', (e) => {
      setThinking(false)
      addMessage({ type: 'error', content: e.content || 'An error occurred.' })
    })

    ws.connect()

    return () => {
      ws.disconnect()
    }
  }, [addMessage, updateAgentBubble, setConnected, setThinking, setActivePlan, setActiveAgents, setCurrentCost])

  const handleSend = (text: string) => {
    if (!wsRef.current) return
    addMessage({ type: 'user', content: text })
    setThinking(true)
    wsRef.current.send(text)
  }

  return (
    <div className="flex flex-col h-full">
      <MessageList />
      <ChatInput onSend={handleSend} />
    </div>
  )
}
