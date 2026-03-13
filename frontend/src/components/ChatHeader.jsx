import logo from '../assets/logo.png'
import { useDispatch } from 'react-redux'
import { resetChat } from '../store/slices/chatSlice'
import { RotateCcw } from 'lucide-react'

export default function ChatHeader() {
  const dispatch = useDispatch()
  return (
    <header className="hdr">
      <div className="hdr-inner">
        <div className="hdr-brand">
          <div className="hdr-logo">
            <img src={logo} alt="Dr. Rania Said" />
          </div>
          <div>
            <div className="hdr-name">Dr. Rania Said</div>
            <div className="hdr-sub">Functional Medicine Clinics</div>
          </div>
        </div>

        <div className="hdr-right">
          <div className="online-pill">
            <span className="online-dot" />
            <span className="online-lbl">AI Medical Assistant</span>
          </div>
          <button className="btn-new" onClick={() => dispatch(resetChat())}>
            <RotateCcw size={12} strokeWidth={2.3} />
            New Chat
          </button>
        </div>
      </div>
    </header>
  )
}
