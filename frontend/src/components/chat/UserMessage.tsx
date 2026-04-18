interface UserMessageProps {
  content: string
}

export default function UserMessage({ content }: UserMessageProps) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[70%] bg-violet-600/20 border border-violet-500/30 rounded-lg px-4 py-2.5 text-sm">
        {content}
      </div>
    </div>
  )
}
