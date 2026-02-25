import { useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { sendMessage } from '../store/slices/chatSlice'
import { Send, Plus } from 'lucide-react'

export default function ChatInput() {
  const [text, setText] = useState('')
  const fileRef = useRef(null)
  const dispatch = useDispatch()

  // 🔥 backend-aligned loading state
  const loading = useSelector(state => state.chat.loading)
  const isDisabled = !text.trim() || loading

  const submit = () => {
    if (isDisabled) return
    dispatch(sendMessage(text))
    setText('')
  }

  // 📎 UI-only upload (backend ready)
  const handleUpload = (e) => {
    const file = e.target.files[0]
    if (!file) return

    dispatch(
      sendMessage(
        `📎 Uploaded document: ${file.name} (${Math.round(
          file.size / 1024
        )} KB)`
      )
    )

    // reset input so same file can be uploaded again
    e.target.value = ''
  }

  return (
    <div
      className="border-t bg-white px-6 py-4"
      style={{ borderColor: 'var(--green-primary)' }}
    >
      <input
        ref={fileRef}
        type="file"
        className="hidden"
        onChange={handleUpload}
      />

      <div className="flex items-center gap-3">
        {/* ➕ Upload */}
        <button
          onClick={() => fileRef.current.click()}
          disabled={loading}
          className="h-11 w-11 rounded-full text-white shadow flex items-center justify-center hover:opacity-90 disabled:opacity-50"
          style={{ backgroundColor: 'var(--green-primary)' }}
        >
          <Plus size={22} strokeWidth={2} />
        </button>

        {/* 💬 Text input */}
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submit()}
          placeholder={loading ? 'Assistant is typing…' : 'Type your message…'}
          className="flex-1 border rounded-lg px-4 py-3 h-11"
          style={{ borderColor: 'var(--green-primary)' }}
          disabled={loading}
        />

        {/* 📅 Appointment intent */}
        <button
          onClick={() =>
            dispatch(
              sendMessage(
                'Book appointment',
                '__INTENT_BOOK_APPOINTMENT__'
              )
            )
          }
          disabled={loading}
          className="h-11 px-4 rounded-lg border font-medium hover:bg-[var(--green-muted)] disabled:opacity-50"
          style={{
            borderColor: 'var(--green-primary)',
            color: 'var(--green-primary)'
          }}
        >
          Book Appointment
        </button>

      
        <button
          onClick={submit}
          disabled={isDisabled}
          className="h-11 px-6 rounded-lg text-white shadow hover:opacity-90 inline-flex items-center gap-2 whitespace-nowrap disabled:opacity-50"
          style={{
            backgroundColor: 'var(--green-primary)',
            cursor: isDisabled ? 'not-allowed' : 'pointer'
          }}
        >
          <Send size={16} strokeWidth={1.75} />
          <span className="text-sm font-medium leading-none">
            Send
          </span>
        </button>
      </div>
    </div>
  )
}