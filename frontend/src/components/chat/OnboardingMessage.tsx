import { Sparkles } from 'lucide-react'

interface OnboardingMessageProps {
  content: string
}

export default function OnboardingMessage({ content }: OnboardingMessageProps) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] bg-violet-950/40 border border-violet-500/20 rounded-lg px-4 py-3">
        <div className="flex items-center gap-2 mb-2">
          <Sparkles size={14} className="text-violet-400" />
          <span className="text-xs font-medium text-violet-400">Setup</span>
        </div>
        <p className="text-sm whitespace-pre-wrap">{content}</p>
      </div>
    </div>
  )
}
