import { useState } from 'react'
import {
  checkAvailability,
  bookAppointment
} from '../api/chatApi'

export default function AppointmentModal({ onClose }) {
  const [date, setDate] = useState('')
  const [slots, setSlots] = useState([])
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadSlots = async () => {
    if (!date) return
    setLoading(true)
    try {
      const res = await checkAvailability(date, 'initial')
      setSlots(res.available_slots || [])
    } finally {
      setLoading(false)
    }
  }

  const confirmBooking = async () => {
    if (!selectedSlot) return

    await bookAppointment({
      patient_name: 'Web User',
      patient_phone: '0000000000',
      patient_email: 'web@example.com',
      date,
      time: selectedSlot.start_time,
      appointment_type: 'initial',
      notes: 'Booked via web chatbot'
    })

    alert('✅ Appointment booked successfully')
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 w-96 shadow-lg">
        <h2 className="text-lg font-semibold mb-4">
          Schedule Appointment
        </h2>

        <input
          type="date"
          value={date}
          onChange={e => setDate(e.target.value)}
          className="w-full border px-3 py-2 rounded-lg mb-3"
        />

        <button
          onClick={loadSlots}
          className="mb-3 px-4 py-2 rounded bg-[var(--green-primary)] text-white"
        >
          Check Availability
        </button>

        {loading && <p>Loading slots…</p>}

        {slots.map(slot => (
          <button
            key={slot.start_time}
            onClick={() => setSelectedSlot(slot)}
            className={`block w-full text-left px-3 py-2 rounded mb-2 border ${
              selectedSlot === slot ? 'bg-green-100' : ''
            }`}
          >
            {slot.start_time}
          </button>
        ))}

        <div className="flex justify-end gap-3 mt-4">
          <button onClick={onClose} className="px-4 py-2 border rounded">
            Cancel
          </button>
          <button
            onClick={confirmBooking}
            disabled={!selectedSlot}
            className="px-4 py-2 rounded text-white bg-[var(--green-primary)] disabled:opacity-50"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}