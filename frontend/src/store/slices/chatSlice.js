import { createSlice, nanoid } from '@reduxjs/toolkit'
import { sendChatMessage } from '../../api/chatApi'

const SESSION_ID = `web-${nanoid()}`

const getWelcomeMessages = () => ([
  {
    id: nanoid(),
    role: 'assistant',
    text: 'Welcome to Dr Rania Said – Functional Medicine Clinics'
  }
])

const chatSlice = createSlice({
  name: 'chat',
  initialState: {
    messages: getWelcomeMessages(),
    loading: false,
    intent: null,
    confidence: null
    // ❌ DO NOT store actions globally
  },
  reducers: {
    resetChat(state) {
      state.messages = getWelcomeMessages()
      state.loading = false
      state.intent = null
      state.confidence = null
    },

    addUserMessage(state, action) {
      state.messages.push({
        id: nanoid(),
        role: 'user',
        text: action.payload
      })
    },

    addBotMessage(state, action) {
      const {
        reply,
        intent,
        confidence,
        actions,
        buttons
      } = action.payload || {}

      state.messages.push({
        id: nanoid(),
        role: 'assistant',
        text: reply || 'I’m here to help.',
        confidence: confidence >= 0.2 ? confidence : null,
        actions: actions || null,
        buttons: Array.isArray(buttons) ? buttons : []
      })

      // 🔒 ONLY meta info stays global
      state.intent = intent || null
      state.confidence = confidence ?? null
      state.loading = false
    },

    setLoading(state) {
      state.loading = true
    }
  }
})

export const {
  resetChat,
  addUserMessage,
  addBotMessage,
  setLoading
} = chatSlice.actions

export const sendMessage =
  (uiText, backendPayload = null) =>
  async (dispatch) => {
    dispatch(addUserMessage(uiText))
    dispatch(setLoading())

    try {
      const response = await sendChatMessage({
        message: uiText,
        payload: backendPayload,
        sender: SESSION_ID,
        name: 'Web User',
      })

      dispatch(addBotMessage(response))
    } catch (error) {
      dispatch(
        addBotMessage({
          reply:
            '⚠️ I’m having trouble connecting right now. Please try again shortly.',
          confidence: null,
          actions: null,
          buttons: []
        })
      )
    }
  }

export default chatSlice.reducer