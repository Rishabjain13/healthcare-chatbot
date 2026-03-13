import { useEffect } from 'react'
import { useDispatch } from 'react-redux'
import Chat from './pages/Chat'
import { healthCheck, getConfig } from './api/chatApi'
import { setConnectionError } from './store/slices/chatSlice'

export default function App() {
  const dispatch = useDispatch()

  useEffect(() => {
    healthCheck()
      .then(() => dispatch(setConnectionError(false)))
      .catch(() => dispatch(setConnectionError(true)))
    getConfig()
      .catch(() => console.warn('Could not load clinic config'))
  }, [dispatch])

  return (
    <div className="app-shell">
      <Chat />
    </div>
  )
}
