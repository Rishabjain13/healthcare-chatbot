import { useDispatch } from 'react-redux'
import { sendMessage } from '../store/slices/chatSlice'
import { Bot, User } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

export default function ChatMessage({
  role,
  text,
  options,
  actions,
  buttons,
  showDatePicker,
  createdAt
}) {
  const isUser = role === 'user'
  const dispatch = useDispatch()

  /**
   * ✅ Normalize options into:
   * { label: string, payload: string }
   * This is CRITICAL for backend intent handling
   */
  const resolvedOptions = (
    options ||
    buttons?.map(b => ({
      label: b.title ?? b.label ?? b,
      payload: b.payload ?? b.value ?? b.title ?? b
    })) ||
    (actions?.type === 'show_options'
      ? actions.options.map(o => ({
          label: o.label ?? o,
          payload: o.payload ?? o
        }))
      : [])
  )

  /**
   * 📅 Show date picker ONLY when backend explicitly asks
   * and there are no option buttons visible
   */
  const shouldShowDatePicker =
    actions?.type === 'pick_date' &&
    (!resolvedOptions || resolvedOptions.length === 0)

  return (
    <div
      className={`flex gap-3 items-start ${
        isUser ? 'justify-end' : 'justify-start'
      }`}
    >
      {/* 🤖 Bot avatar */}
      {!isUser && (
        <div
          className="h-9 w-9 shrink-0 rounded-full flex items-center justify-center text-white"
          style={{ backgroundColor: 'var(--green-primary)' }}
        >
          <Bot size={18} strokeWidth={1.75} />
        </div>
      )}

      {/* 💬 Message bubble */}
      <div
        className="max-w-[65%] px-4 py-3 rounded-xl text-sm shadow"
        style={{
          backgroundColor: isUser ? 'var(--green-primary)' : '#ffffff',
          color: isUser ? '#ffffff' : 'var(--text-dark)'
        }}
      >
        {/* 🔥 Message text (Markdown for bot, plain for user) */}
        {isUser ? (
          <div>{text}</div>
        ) : (
          <ReactMarkdown
            components={{
              strong: ({ children }) => (
                <strong className="font-semibold">{children}</strong>
              ),
              em: ({ children }) => (
                <em className="italic">{children}</em>
              ),
              ul: ({ children }) => (
                <ul className="list-disc ml-4 mt-2 space-y-1">
                  {children}
                </ul>
              ),
              li: ({ children }) => <li>{children}</li>,
              p: ({ children }) => (
                <p className="mb-1 last:mb-0">{children}</p>
              )
            }}
          >
            {text}
          </ReactMarkdown>
        )}

        {/* 🔘 Option buttons */}
        {resolvedOptions?.length > 0 && (
          <div className="flex gap-2 mt-3 flex-wrap">
            {resolvedOptions.map((opt, index) => (
              <button
                key={`${opt.label}-${index}`}
                onClick={() =>
                  dispatch(
                    sendMessage(
                      opt.label,   // 👈 what user sees
                      opt.payload  // 👈 what backend receives
                    )
                  )
                }
                className="px-3 py-1 rounded-full text-xs border"
                style={{
                  borderColor: 'var(--green-primary)',
                  color: 'var(--green-primary)'
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}

        {/* 📅 Date picker */}
        {shouldShowDatePicker && (
          <div className="mt-3">
            <input
              type="date"
              className="border rounded-lg px-3 py-2 text-sm hover:bg-[var(--green-muted)]"
              onChange={(e) => {
                const raw = e.target.value
                if (!raw) return

                const date = new Date(raw + 'T00:00:00')

                // ✅ Backend-friendly format
                const formatted = date.toLocaleDateString('en-US', {
                  weekday: 'long',
                  month: 'short',
                  day: '2-digit'
                })

                dispatch(sendMessage(formatted))
              }}
            />
          </div>
        )}

        {/* ⏱ Optional timestamp */}
        {createdAt && (
          <div className="mt-1 text-[10px] opacity-50 text-right">
            {new Date(createdAt).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit'
            })}
          </div>
        )}
      </div>

      {/* 👤 User avatar */}
      {isUser && (
        <div
          className="h-9 w-9 shrink-0 rounded-full flex items-center justify-center shadow"
          style={{
            backgroundColor: '#ffffff',
            border: '2px solid var(--green-primary)'
          }}
        >
          <User size={18} strokeWidth={1.75} />
        </div>
      )}
    </div>
  )
}