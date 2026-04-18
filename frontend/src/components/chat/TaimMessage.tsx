interface TaimMessageProps {
  content: string
  agentName?: string
  costEur?: number
  tokensUsed?: number
}

export default function TaimMessage({
  content,
  agentName,
  costEur,
  tokensUsed,
}: TaimMessageProps) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%]">
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3 text-sm whitespace-pre-wrap">
          {content}
        </div>
        {(agentName || costEur !== undefined) && (
          <div className="flex gap-3 mt-1 text-xs text-zinc-600">
            {agentName && <span>{agentName}</span>}
            {costEur !== undefined && <span>€{costEur.toFixed(4)}</span>}
            {tokensUsed !== undefined && <span>{tokensUsed} tokens</span>}
          </div>
        )}
      </div>
    </div>
  )
}
