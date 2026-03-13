import { createSlice, nanoid } from '@reduxjs/toolkit'
import { sendChatMessage } from '../../api/chatApi'

const SESSION_ID = `web-${nanoid()}`

const chatSlice = createSlice({
  name: 'chat',
  initialState: {
    messages: [],
    loading: false,
    intent: null,
    confidence: null,
    connectionError: false,
    // ❌ DO NOT store actions globally
  },
  reducers: {
    resetChat(state) {
      state.messages = []
      state.loading = false
      state.intent = null
      state.confidence = null
      state.connectionError = false
    },

    setConnectionError(state, action) {
      state.connectionError = action.payload
    },

    addUserMessage(state, action) {
      state.messages.push({
        id: nanoid(),
        role: 'user',
        text: action.payload,
        createdAt: new Date().toISOString(),
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
        text: reply || 'I\’m here to help.',
        confidence: confidence >= 0.2 ? confidence : null,
        actions: actions || null,
        buttons: Array.isArray(buttons) ? buttons : [],
        createdAt: new Date().toISOString(),
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
  setLoading,
  setConnectionError,
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

      dispatch(setConnectionError(false))
      dispatch(addBotMessage(response))
    } catch (error) {
      dispatch(setConnectionError(true))
      dispatch(
        addBotMessage({
          reply: 'I\’m having trouble connecting right now. Please try again shortly.',
          confidence: null,
          actions: null,
          buttons: []
        })
      )
    }
  }

export default chatSlice.reducer