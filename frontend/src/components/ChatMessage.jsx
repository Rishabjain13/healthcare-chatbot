import { useState } from 'react'
import { useDispatch } from 'react-redux'
import { sendMessage } from '../store/slices/chatSlice'
import { Hospital, User } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

export default function ChatMessage({
  role, text, options, actions, buttons, createdAt,
  isFirst = true, isGrouped = false, isLast = true,
}) {
  const isUser = role === 'user'
  const dispatch = useDispatch()
  const [pillUsed, setPillUsed] = useState(false)

  const opts = (
    options ||
    buttons?.map(b => ({
      label:   b.title   ?? b.label   ?? b,
      payload: b.payload ?? b.value   ?? b.title ?? b,
    })) ||
    (actions?.type === 'show_options'
      ? actions.options.map(o => ({ label: o.label ?? o, payload: o.payload ?? o }))
      : [])
  )

  const showDate = actions?.type === 'pick_date' && (!opts || opts.length === 0)

  const rowCls = [
    'row',
    isUser    ? 'row--user'    : 'row--bot',
    isFirst   ? 'row--first'   : '',
    isGrouped ? 'row--grouped' : '',
  ].filter(Boolean).join(' ')

  const time = createdAt
    ? new Date(createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null

  return (
    <div className={rowCls}>

      {/* Bot avatar — always in DOM, hidden when grouped (preserves spacing) */}
      {!isUser && (
        <div className="avatar avatar--bot">
          <Hospital size={16} strokeWidth={2} />
        </div>
      )}

      {/* Bubble + timestamp */}
      <div className="bcol">
        <div className={`bubble ${isUser ? 'bubble--user' : 'bubble--bot'}`}>

          {isUser ? (
            <span>{text}</span>
          ) : (
            <ReactMarkdown
              components={{
                strong: ({ children }) => <strong>{children}</strong>,
                em:     ({ children }) => <em>{children}</em>,
                ul:     ({ children }) => <ul>{children}</ul>,
                ol:     ({ children }) => <ol>{children}</ol>,
                li:     ({ children }) => <li>{children}</li>,
                p:      ({ children }) => <p>{children}</p>,
                a:      ({ href, children }) => (
                  <a href={href} target="_blank" rel="noreferrer">{children}</a>
                ),
              }}
            >
              {text}
            </ReactMarkdown>
          )}

          {opts?.length > 0 && (
            <div className="pills">
              {opts.map((opt, i) => (
                <button
                  key={`${opt.label}-${i}`}
                  className={`pill${pillUsed ? ' pill--used' : ''}`}
                  disabled={pillUsed}
                  onClick={() => {
                    if (pillUsed) return
                    setPillUsed(true)
                    dispatch(sendMessage(opt.label, opt.payload))
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}

          {showDate && (
            <input
              type="date"
              onChange={e => {
                if (!e.target.value) return
                const d = new Date(e.target.value + 'T00:00:00')
                dispatch(sendMessage(
                  d.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: '2-digit' })
                ))
              }}
            />
          )}
        </div>

        {time && isLast && <div className="ts">{time}</div>}
      </div>

      {/* User avatar — always in DOM */}
      {isUser && (
        <div className="avatar avatar--user">
          <User size={15} strokeWidth={2} />
        </div>
      )}

    </div>
  )
}
