import { Hospital } from 'lucide-react'

export default function TypingIndicator() {
  return (
    <div className="typing-row">
      <div className="avatar avatar--bot">
        <Hospital size={16} strokeWidth={2} />
      </div>
      <div className="typing-bbl">
        <span /><span /><span />
      </div>
    </div>
  )
}
