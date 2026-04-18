export default function ThinkingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3">
        <div className="flex gap-1">
          <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce [animation-delay:0ms]" />
          <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce [animation-delay:150ms]" />
          <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  )
}
