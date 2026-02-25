import { Bot } from 'lucide-react'

export default function TypingIndicator() {
  return (
    <div className="flex items-end gap-3">
      {/* Bot avatar */}
      <div
        className="h-9 w-9 rounded-full flex items-center justify-center text-white shrink-0"
        style={{ backgroundColor: 'var(--green-primary)' }}
      >
        <Bot size={18} strokeWidth={1.75} />
      </div>

      {/* Typing pill */}
      <div className="typing-icon-pill">
        <span />
        <span />
        <span />
      </div>
    </div>
  )
}