const BASE_URL = 'http://localhost:3000' // <-- your backend port

async function handleResponse(res, errorMessage) {
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || errorMessage)
  }
  return res.json()
}

/* ---------------- SYSTEM ---------------- */

export async function healthCheck() {
  const res = await fetch(`${BASE_URL}/health`)
  return handleResponse(res, 'Health check failed')
}

export async function getConfig() {
  const res = await fetch(`${BASE_URL}/config`)
  return handleResponse(res, 'Config fetch failed')
}

/* ---------------- CHAT ---------------- */

export async function sendChatMessage({ message, sender, name, payload }) {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      sender,
      name: name || 'Web User',
      payload, // 🔥 THIS WAS MISSING
    }),
  })

  return handleResponse(res, 'Chat failed')
}

/* ---------------- APPOINTMENTS ---------------- */

export async function checkAvailability(date, appointment_type) {
  const res = await fetch(`${BASE_URL}/appointments/availability`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, appointment_type }),
  })

  return handleResponse(res, 'Availability failed')
}

export async function bookAppointment(payload) {
  const res = await fetch(`${BASE_URL}/appointments/book`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  return handleResponse(res, 'Booking failed')
}