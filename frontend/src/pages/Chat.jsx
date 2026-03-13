import { useSelector, useDispatch } from 'react-redux'
import { useEffect, useRef } from 'react'
import { sendMessage } from '../store/slices/chatSlice'
import ChatHeader      from '../components/ChatHeader'
import ChatInput       from '../components/ChatInput'
import ChatMessage     from '../components/ChatMessage'
import TypingIndicator from '../components/TypingIndicator'
import { Stethoscope, Pill, CalendarCheck, HeartPulse, WifiOff } from 'lucide-react'

const CARDS = [
  { icon: <Stethoscope size={16} strokeWidth={1.8} />, label: 'Book a consultation',  hint: 'Schedule time with Dr. Rania',         msg: 'I would like to book a consultation' },
  { icon: <Pill        size={16} strokeWidth={1.8} />, label: 'Medication questions',  hint: 'Prescriptions, dosage & side effects',  msg: 'I have a question about medications' },
  { icon: <CalendarCheck size={16} strokeWidth={1.8} />, label: 'Schedule follow-up', hint: 'Plan your next visit',                  msg: 'I need to schedule a follow-up' },
  { icon: <HeartPulse  size={16} strokeWidth={1.8} />, label: 'Check my symptoms',    hint: 'Describe what you are experiencing',     msg: 'I want to check my symptoms' },
]

function dayLabel(ts) {
  if (!ts) return null
  const d = new Date(ts), now = new Date(), yst = new Date()
  yst.setDate(now.getDate() - 1)
  if (d.toDateString() === now.toDateString()) return 'Today'
  if (d.toDateString() === yst.toDateString()) return 'Yesterday'
  return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
}

export default function Chat() {
  const { messages, loading, connectionError } = useSelector(s => s.chat)
  const dispatch = useDispatch()
  const endRef   = useRef(null)
  const isEmpty  = messages.length === 0

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Build render items with grouping + date dividers
  const items = []
  let lastDay = null, lastRole = null

  messages.forEach((msg, i) => {
    const day = dayLabel(msg.createdAt)
    if (day && day !== lastDay) {
      items.push({ type: 'div', label: day, key: `d-${i}` })
      lastDay = day
    }
    const isFirst   = msg.role !== lastRole
    const isGrouped = msg.role === lastRole
    const isLast    = !messages[i + 1] || messages[i + 1].role !== msg.role
    items.push({ type: 'msg', msg, isFirst, isGrouped, isLast, key: msg.id })
    lastRole = msg.role
  })

  return (
    <div className="chat-win">
      <ChatHeader />
      {connectionError && (
        <div className="conn-banner">
          <WifiOff size={14} strokeWidth={2} />
          <span>Assistant is currently unreachable — check your connection and try again.</span>
        </div>
      )}

      <div className="msgs">
        <div className="msgs-inner">

          {isEmpty && !loading ? (
            <div className="welcome">
              <div className="w-orb-wrap">
                <div className="w-orb-halo" />
                <div className="w-orb">
                  <HeartPulse size={32} strokeWidth={1.6} />
                </div>
              </div>

              <div className="w-copy">
                <h2 className="w-title">How can I help you today?</h2>
                <p className="w-desc">
                  Your AI health assistant at Dr.&nbsp;Rania Said's Functional Medicine Clinic.
                  Type a message or choose a topic below.
                </p>
              </div>

              <div className="w-grid">
                {CARDS.map(c => (
                  <button key={c.label} className="card" onClick={() => dispatch(sendMessage(c.msg))}>
                    <span className="card-icon">{c.icon}</span>
                    <span>
                      <div className="card-label">{c.label}</div>
                      <div className="card-hint">{c.hint}</div>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            items.map(item =>
              item.type === 'div' ? (
                <div key={item.key} className="date-sep">{item.label}</div>
              ) : (
                <ChatMessage
                  key={item.key}
                  {...item.msg}
                  isFirst={item.isFirst}
                  isGrouped={item.isGrouped}
                  isLast={item.isLast}
                />
              )
            )
          )}

          {loading && <TypingIndicator />}
          <div ref={endRef} />
        </div>
      </div>

      <ChatInput />
    </div>
  )
}
