import Logo from './Logo'
import { useDispatch } from 'react-redux'
import { resetChat } from '../store/slices/chatSlice'

export default function ChatHeader() {
  const dispatch = useDispatch()

  return (
    <header
      className="flex items-center justify-between px-6 h-16 shadow"
      style={{ backgroundColor: 'var(--green-primary)' }}
    >
      <div className="flex items-center gap-3 text-white">
        <Logo />
        <div>
          <div className="font-semibold">Dr Rania Said</div>
          <div className="text-xs opacity-90">
            Functional Medicine Clinics
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm text-white font-medium">
            AI Medical Assistant
        </span>

        <button
            onClick={() => dispatch(resetChat())}
            className="
            h-8 px-3 rounded-md
            text-xs font-medium
            border border-white/40
            text-white
            hover:bg-white/10
            transition
            "
        >
            New Chat
        </button>
      </div>
    </header>
  )
}