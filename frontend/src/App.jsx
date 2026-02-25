import { useEffect } from 'react'
import Chat from './pages/Chat'
import { healthCheck, getConfig } from './api/chatApi'

export default function App() {
  useEffect(() => {
    // 🔍 Backend health check
    healthCheck()
      .then(res => {
        console.log('Backend healthy:', res)
      })
      .catch(() => {
        alert('Healthcare assistant is currently unavailable')
      })

    // 🏥 Load clinic config (for header, pricing later)
    getConfig()
      .then(cfg => {
        console.log('Clinic config:', cfg)
      })
      .catch(() => {
        console.warn('Could not load clinic config')
      })
  }, [])

  return (
    <div className="h-screen bg-slate-50">
      <Chat />
    </div>
  )
}