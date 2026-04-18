import { useEffect, useRef } from 'react'
import { useChatStore } from '../../stores/chat-store'
import UserMessage from './UserMessage'
import TaimMessage from './TaimMessage'
import PlanCard from './PlanCard'
import AgentStatusBubble from './AgentStatusBubble'
import OnboardingMessage from './OnboardingMessage'
import ThinkingIndicator from './ThinkingIndicator'
import SystemMessage from './SystemMessage'

export default function MessageList() {
  const messages = useChatStore((s) => s.messages)
  const isThinking = useChatStore((s) => s.isThinking)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-3">
      {messages.map((msg) => {
        switch (msg.type) {
          case 'user':
            return <UserMessage key={msg.id} content={msg.content} />
          case 'assistant':
          case 'agent_completed':
            return (
              <TaimMessage
                key={msg.id}
                content={msg.content}
                agentName={msg.agentName}
                costEur={msg.costEur}
                tokensUsed={msg.tokensUsed}
              />
            )
          case 'plan_proposed':
            return <PlanCard key={msg.id} content={msg.content} plan={msg.plan} />
          case 'agent_started':
          case 'agent_state':
            return (
              <AgentStatusBubble
                key={msg.id}
                agentName={msg.agentName || ''}
                state={msg.toState || 'PLANNING'}
                content={msg.content}
              />
            )
          case 'tool_execution':
            return <SystemMessage key={msg.id} content={msg.content} variant="tool" />
          case 'onboarding':
            return <OnboardingMessage key={msg.id} content={msg.content} />
          case 'system':
            return <SystemMessage key={msg.id} content={msg.content} />
          case 'error':
            return <SystemMessage key={msg.id} content={msg.content} variant="error" />
          default:
            return null
        }
      })}
      {isThinking && <ThinkingIndicator />}
      <div ref={bottomRef} />
    </div>
  )
}
