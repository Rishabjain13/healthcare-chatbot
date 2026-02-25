# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

from typing import Any, Text, Dict, List
import requests
from datetime import datetime

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


class ActionBookAppointment(Action):
    """Custom action to book appointments via backend API"""

    def name(self) -> Text:
        return "action_book_appointment"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Get slot values
        consultation_type = tracker.get_slot('consultation_type')
        patient_name = tracker.get_slot('patient_name')
        patient_email = tracker.get_slot('patient_email')
        patient_phone = tracker.get_slot('patient_phone')
        appointment_date = tracker.get_slot('appointment_date')
        appointment_time = tracker.get_slot('appointment_time')

        # Validate required information
        if not all([consultation_type, patient_name, patient_email, patient_phone,
                   appointment_date, appointment_time]):
            dispatcher.utter_message(text="Sorry, I'm missing some information. Let's start over.")
            return []

        # Prepare booking data
        booking_data = {
            "patient_name": patient_name,
            "patient_email": patient_email,
            "patient_phone": patient_phone,
            "date": appointment_date,
            "time": appointment_time,
            "appointment_type": "initial",
            "notes": f"Type: {'Online Consultation' if consultation_type == 'online' else 'Offline (In-person)'} | Booked via Rasa chatbot"
        }

        try:
            # Call backend API (update URL to match your backend)
            response = requests.post(
                "http://localhost:3000/appointments/book",
                json=booking_data,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()

                # Build success message based on consultation type
                if consultation_type == 'online' and result.get('zoom_join_url'):
                    # Online consultation with Zoom link
                    message = f"""🎥 **ZOOM MEETING CREATED!**
━━━━━━━━━━━━━━━━━━━━━━

Join URL: {result['zoom_join_url']}
Meeting ID: {result.get('zoom_meeting_id', 'N/A')}
Password: {result.get('zoom_password', 'No password')}

⚠️ Zoom link also sent to your email!

━━━━━━━━━━━━━━━━━━━━━━

✅ **APPOINTMENT BOOKED SUCCESSFULLY!**

👤 Patient: {patient_name}
🏥 Type: Online Consultation
📅 Date: {appointment_date}
⏰ Time: {appointment_time}

You'll receive a confirmation email shortly.

💡 **Reminders:**
• Check your email for Zoom link
• Test your camera/microphone beforehand
• Have previous lab results ready (digital)
• Ensure stable internet connection
• Join 5 minutes early

Looking forward to seeing you! 🌟"""

                elif consultation_type == 'offline':
                    # Offline/in-person consultation
                    message = f"""📍 **LOCATION**
Dubai Healthcare City

━━━━━━━━━━━━━━━━━━━━━━

✅ **APPOINTMENT BOOKED SUCCESSFULLY!**

👤 Patient: {patient_name}
🏥 Type: In-Clinic Consultation
📅 Date: {appointment_date}
⏰ Time: {appointment_time}

You'll receive a confirmation email shortly.

💡 **Reminders:**
• Bring previous lab results (if any)
• Arrive 10 minutes early
• Bring your insurance card

Looking forward to seeing you! 🌟"""

                else:
                    # Fallback success message
                    message = f"""✅ **APPOINTMENT BOOKED SUCCESSFULLY!**

👤 Patient: {patient_name}
🏥 Type: {'Online' if consultation_type == 'online' else 'In-Clinic'} Consultation
📅 Date: {appointment_date}
⏰ Time: {appointment_time}

You'll receive a confirmation email shortly."""

                dispatcher.utter_message(text=message)
            else:
                dispatcher.utter_message(
                    text=f"Sorry, there was an error booking your appointment. Please contact us at [Phone Number]."
                )

        except requests.exceptions.RequestException as e:
            dispatcher.utter_message(
                text=f"Sorry, I couldn't connect to the booking system. Please try again or contact us directly at [Phone Number]."
            )
            print(f"Booking API error: {e}")

        # Clear slots after booking
        return [
            SlotSet("consultation_type", None),
            SlotSet("patient_name", None),
            SlotSet("patient_email", None),
            SlotSet("patient_phone", None),
            SlotSet("appointment_date", None),
            SlotSet("appointment_time", None)
        ]
