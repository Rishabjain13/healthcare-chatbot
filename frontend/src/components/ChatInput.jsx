import { useRef, useState, useCallback } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { sendMessage } from '../store/slices/chatSlice'
import { Send, Paperclip, CalendarPlus } from 'lucide-react'

export default function ChatInput() {
  const [text, setText] = useState('')
  const fileRef         = useRef(null)
  const taRef           = useRef(null)
  const dispatch        = useDispatch()
  const loading         = useSelector(s => s.chat.loading)
  const canSend         = text.trim().length > 0 && !loading

  const grow = useCallback(() => {
    const el = taRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 110) + 'px'
  }, [])

  const onChange = e => { setText(e.target.value); grow() }

  const submit = () => {
    if (!canSend) return
    dispatch(sendMessage(text.trim()))
    setText('')
    if (taRef.current) taRef.current.style.height = 'auto'
  }

  const onKey = e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }

  const onFile = e => {
    const f = e.target.files[0]
    if (!f) return
    dispatch(sendMessage(`📎 Uploaded: ${f.name} (${Math.round(f.size / 1024)} KB)`))
    e.target.value = ''
  }

  return (
    <div className="inp-bar">
      <input ref={fileRef} type="file" style={{ display: 'none' }} onChange={onFile} />

      <div className="inp-inner">
        <div className="inp-box">
          <button className="btn-att" onClick={() => fileRef.current.click()} disabled={loading} title="Attach file">
            <Paperclip size={16} strokeWidth={2} />
          </button>

          <div className="vr" />

          <textarea
            ref={taRef}
            className="inp-ta"
            rows={1}
            value={text}
            onChange={onChange}
            onKeyDown={onKey}
            placeholder={loading ? 'Assistant is typing…' : 'Ask anything about your health…'}
            disabled={loading}
          />

          <div className="vr" />

          <button
            className="btn-book"
            onClick={() => dispatch(sendMessage('Book appointment', '__INTENT_BOOK_APPOINTMENT__'))}
            disabled={loading}
          >
            <CalendarPlus size={14} strokeWidth={2} />
            Book Appointment
          </button>

          <button className="btn-send" onClick={submit} disabled={!canSend}>
            <Send size={14} strokeWidth={2.2} />
            Send
          </button>
        </div>

        <p className="inp-hint">
          <strong>Enter</strong> to send &nbsp;·&nbsp; <strong>Shift + Enter</strong> for new line
        </p>
      </div>
    </div>
  )
}
