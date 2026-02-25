import { useSelector } from 'react-redux'
import { useEffect, useRef } from 'react'
import ChatHeader from '../components/ChatHeader'
import ChatInput from '../components/ChatInput'
import ChatMessage from '../components/ChatMessage'
import TypingIndicator from '../components/TypingIndicator'

export default function Chat() {
  const { messages, loading } = useSelector(state => state.chat)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  return (
    <div className="flex flex-col h-screen">
      <ChatHeader />

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map(msg => (
          <ChatMessage key={msg.id} {...msg} />
        ))}

        {loading && <TypingIndicator />}

        <div ref={bottomRef} />
      </div>

      <ChatInput />
    </div>
  )
}