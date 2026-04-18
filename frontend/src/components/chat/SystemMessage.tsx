import { cn } from '../../lib/cn'

interface SystemMessageProps {
  content: string
  variant?: 'default' | 'error' | 'tool'
}

export default function SystemMessage({
  content,
  variant = 'default',
}: SystemMessageProps) {
  return (
    <div
      className={cn(
        'text-xs py-1 px-2',
        variant === 'error' && 'text-red-400',
        variant === 'tool' && 'text-zinc-500 italic',
        variant === 'default' && 'text-zinc-500'
      )}
    >
      {content}
    </div>
  )
}
