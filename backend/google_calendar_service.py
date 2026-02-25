"""
Google Calendar Integration for Appointment Booking
Handles appointment creation, availability checking, and calendar management
"""

import os
import pickle
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config_loader import get_config
from zoom_service import get_zoom_service

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']


class GoogleCalendarService:
    """Manages Google Calendar operations for appointment booking"""

    def __init__(self):
        self.config = get_config()
        self.creds = None
        self.service = None
        self.calendar_id = self.config.google_calendar_id
        self.zoom_service = get_zoom_service()

        if self.config.google_calendar_enabled:
            self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Calendar API"""
        token_file = self.config.google_token_file
        credentials_file = self.config.google_credentials_file

        # Load existing token
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                self.creds = pickle.load(token)

        # If no valid credentials, authenticate
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists(credentials_file):
                    raise FileNotFoundError(
                        f"Google credentials file not found: {credentials_file}\n"
                        "Please follow Google Calendar API setup instructions."
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file, SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            # Save credentials for next time
            with open(token_file, 'wb') as token:
                pickle.dump(self.creds, token)

        # Build service
        self.service = build('calendar', 'v3', credentials=self.creds)

    def get_available_slots_for_date(self, date: str):
        if not self.config.google_calendar_enabled:
            return self._get_mock_slots(date)

        try:
            hours = self.config.config['hours']

            target_date = datetime.strptime(date, '%Y-%m-%d')
            day_name = target_date.strftime('%A')

            working_hours = self._get_working_hours(day_name)
            if not working_hours:
                return []

            duration_minutes = self.config.initial_duration

            slots = self._generate_slots(
                date,
                working_hours['open'],
                working_hours['close'],
                duration_minutes
            )

            return [
                slot for slot in slots
                if self._is_slot_available(slot['start_datetime'], slot['end_datetime'])
            ]

        except Exception as e:
            print(f"Error getting available slots: {e}")
            return []
    

    
    def _get_working_hours(self, day_name: str):
        hours = self.config.config['hours']

        for schedule in hours['schedule']:
            if schedule['day'] == day_name:
                return {
                    'open': schedule['open'],
                    'close': schedule['close'],
                    'appointment_type': schedule.get('appointment_type')
                }
        return None

    def _generate_slots(
        self,
        date: str,
        open_time: str,
        close_time: str,
        duration_minutes: int
    ) -> List[Dict[str, str]]:
        """Generate all possible time slots for a day"""
        slots = []
        timezone = ZoneInfo(self.config.timezone)

        # Parse times
        open_hour, open_minute = map(int, open_time.split(':'))
        close_hour, close_minute = map(int, close_time.split(':'))

        # Create datetime objects
        current_date = datetime.strptime(date, '%Y-%m-%d')
        current_time = datetime(
            current_date.year,
            current_date.month,
            current_date.day,
            open_hour,
            open_minute,
            tzinfo=timezone
        )
        end_of_day = datetime(
            current_date.year,
            current_date.month,
            current_date.day,
            close_hour,
            close_minute,
            tzinfo=timezone
        )

        # Generate slots
        while current_time + timedelta(minutes=duration_minutes) <= end_of_day:
            slot_end = current_time + timedelta(minutes=duration_minutes)

            slots.append({
                'start_time': current_time.strftime('%I:%M %p'),
                'end_time': slot_end.strftime('%I:%M %p'),
                'start_datetime': current_time.isoformat(),
                'end_datetime': slot_end.isoformat(),
                'date': date
            })

            # Move to next slot (30-minute intervals)
            current_time += timedelta(minutes=30)

        return slots

    def _is_slot_available(self, start_datetime: str, end_datetime: str) -> bool:
        """Check if a time slot is available (not already booked)"""
        if not self.service:
            return True

        try:
            # Query calendar for events in this time range
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_datetime,
                timeMax=end_datetime,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # Slot is available if no events found
            return len(events) == 0

        except HttpError as e:
            print(f"Error checking slot availability: {e}")
            return False
    def get_events_between(self, start_dt, end_dt):
        """
        Returns Google Calendar events overlapping a time range
        """
        events_result = self.service.events().list(
            calendarId=self.calendar_id,
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        return events_result.get('items', [])
    def book_appointment(
        self,
        patient_name: str,
        patient_phone: str,
        patient_email: str,
        start_datetime: str,
        end_datetime: str,
        appointment_type: str = 'initial',
        notes: str = ""
    ) -> Dict[str, any]:
        """
        Book an appointment in Google Calendar

        Args:
            patient_name: Patient's full name
            patient_phone: Patient's phone number
            patient_email: Patient's email
            start_datetime: Start time in ISO format
            end_datetime: End time in ISO format
            appointment_type: 'initial', 'followup', or 'emergency'
            notes: Additional notes

        Returns:
            Dictionary with booking details and status
        """
        if not self.config.google_calendar_enabled:
            return self._create_mock_booking(
                patient_name, patient_phone, start_datetime
            )

        try:
            # Check if this is an online consultation (from notes)
            is_online = 'online' in notes.lower() or 'Online Consultation' in notes

            zoom_meeting = None
            zoom_link = ""

            if isinstance(start_datetime, str):
                start_datetime = datetime.fromisoformat(start_datetime)

            if isinstance(end_datetime, str):
                end_datetime = datetime.fromisoformat(end_datetime)

            duration_minutes = int(
                (end_datetime - start_datetime).total_seconds() / 60
            )

            # Create Zoom meeting for online consultations
            if is_online and self.zoom_service.enabled:
                print(f"🎥 Creating Zoom meeting for online consultation...")

                # Get doctor name from config
                doctor_name = self.config.config.get('doctors', [{}])[0].get('name', 'Doctor')

                zoom_result = self.zoom_service.create_meeting(
                    topic=f"{doctor_name} - Consultation with {patient_name}",
                    start_datetime=start_datetime,
                    duration_minutes=duration_minutes,
                    patient_name=patient_name,
                    patient_email=patient_email
                )

                if zoom_result.get('success'):
                    zoom_meeting = zoom_result
                    zoom_link = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎥 ZOOM MEETING DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Join URL: {zoom_result['join_url']}
Meeting ID: {zoom_result['meeting_id']}
Password: {zoom_result.get('password', 'No password')}

Please join a few minutes before your appointment time.
The doctor will admit you from the waiting room.
                    """
                    print(f"✅ Zoom meeting created: {zoom_result['meeting_id']}")
                else:
                    print(f"⚠️  Failed to create Zoom meeting: {zoom_result.get('error')}")

            # Create event description
            description = f"""
Patient: {patient_name}
Phone: {patient_phone}
Email: {patient_email}
Type: {appointment_type.title()} Consultation {'(Online)' if is_online else '(In-person)'}

{notes}
{zoom_link}

Booked via: Healthcare Chatbot
            """.strip()

            # Create event
            event = {
                'summary': f'{appointment_type.title()} Consultation - {patient_name} {"🎥" if is_online else "🏥"}',
                'description': description,
                'location': zoom_meeting['join_url'] if zoom_meeting else self.config.config['location']['address'],
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': self.config.timezone,
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': self.config.timezone,
                },
                'attendees': [
                    {'email': patient_email}
                ],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 60},  # 1 hour before
                    ],
                },
            }

            # Insert event
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event,
                sendUpdates='all'  # Send email notifications
            ).execute()

            result = {
                'success': True,
                'event_id': created_event['id'],
                'event_link': created_event.get('htmlLink'),
                'message': 'Appointment booked successfully!',
                'start_time': start_datetime,
                'end_time': end_datetime,
                'is_online': is_online
            }

            # Add Zoom details if online consultation
            if zoom_meeting:
                result['zoom_join_url'] = zoom_meeting['join_url']
                result['zoom_meeting_id'] = zoom_meeting['meeting_id']
                result['zoom_password'] = zoom_meeting.get('password', '')

            return result

        except HttpError as e:
            print(f"Error booking appointment: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to book appointment. Please try again or contact us directly.'
            }
    def book_appointment_fast(
        self,
        patient_name: str,
        patient_phone: str,
        patient_email: str,
        start_datetime: datetime,
        end_datetime: datetime,
        appointment_type: str,
        notes: str
    ) -> Dict[str, any]:
        """
        FAST booking:
        - Calendar event only
        - No Zoom
        - No email
        """

        event = {
            "summary": f"{appointment_type.title()} Consultation - {patient_name}",
            "description": f"""
    Patient: {patient_name}
    Phone: {patient_phone}
    Email: {patient_email}
    Type: {appointment_type.title()} Consultation

    {notes}

    Booked via: Healthcare Chatbot
            """.strip(),
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": self.config.timezone,
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": self.config.timezone,
            },
            "attendees": [{"email": patient_email}],
        }

        created_event = self.service.events().insert(
            calendarId=self.calendar_id,
            body=event,
            sendUpdates="none"   # 🔥 KEY FIX
        ).execute()

        return {
            "success": True,
            "event_id": created_event["id"],
            "message": "Appointment booked successfully!",
            "start_time": start_datetime,
            "end_time": end_datetime,
            "is_online": appointment_type == "online"
        }    

    def finalize_online_booking(
        self,
        event_id: str,
        booking,
        start_datetime: datetime,
        end_datetime: datetime
    ):
        """
        Background task:
        - Create Zoom meeting
        - Update calendar
        - Send email
        """
        try:
            if not self.zoom_service.enabled:
                return

            duration_minutes = int(
                (end_datetime - start_datetime).total_seconds() / 60
            )

            doctor_name = self.config.config.get(
                "doctors", [{}]
            )[0].get("name", "Doctor")

            zoom_result = self.zoom_service.create_meeting(
                topic=f"{doctor_name} - Consultation with {booking.patient_name}",
                start_datetime=start_datetime,
                duration_minutes=duration_minutes,
                patient_name=booking.patient_name,
                patient_email=booking.patient_email
            )

            if not zoom_result.get("success"):
                return

            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()

            event["location"] = zoom_result["join_url"]
            event["description"] += f"""

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    🎥 ZOOM MEETING DETAILS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Join URL: {zoom_result['join_url']}
    Meeting ID: {zoom_result['meeting_id']}
    Password: {zoom_result.get('password', '')}
            """

            self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates="all"   # email sent now
            ).execute()

        except Exception as e:
            print("Finalize booking error:", e)
            
    def cancel_appointment(self, event_id: str) -> Dict[str, any]:
        """Cancel an appointment"""
        if not self.config.google_calendar_enabled:
            return {'success': True, 'message': 'Appointment cancelled (mock mode)'}

        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id,
                sendUpdates='all'
            ).execute()

            return {
                'success': True,
                'message': 'Appointment cancelled successfully'
            }

        except HttpError as e:
            print(f"Error cancelling appointment: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to cancel appointment'
            }

    def reschedule_appointment(
        self,
        event_id: str,
        new_start_datetime: str,
        new_end_datetime: str
    ) -> Dict[str, any]:
        """Reschedule an existing appointment"""
        if not self.config.google_calendar_enabled:
            return {'success': True, 'message': 'Appointment rescheduled (mock mode)'}

        try:
            # Get existing event
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()

            # Update times
            event['start']['dateTime'] = new_start_datetime
            event['end']['dateTime'] = new_end_datetime

            # Update event
            updated_event = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()

            return {
                'success': True,
                'event_id': updated_event['id'],
                'message': 'Appointment rescheduled successfully',
                'new_start_time': new_start_datetime
            }

        except HttpError as e:
            print(f"Error rescheduling appointment: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to reschedule appointment'
            }

    # Mock methods for testing without Google Calendar API
    def _get_mock_slots(self, date: str) -> List[Dict[str, str]]:
        """Generate mock slots for testing"""
        target_date = datetime.strptime(date, '%Y-%m-%d')
        day_name = target_date.strftime('%A')

        working_hours = self._get_working_hours(day_name)
        if not working_hours:
            return []

        return self._generate_slots(date, working_hours['open'], working_hours['close'], 60)

    def _create_mock_booking(
        self,
        patient_name: str,
        patient_phone: str,
        start_datetime: str
    ) -> Dict[str, any]:
        """Create mock booking for testing"""
        return {
            'success': True,
            'event_id': f'mock_{datetime.now().timestamp()}',
            'event_link': '#',
            'message': f'Mock booking created for {patient_name}',
            'start_time': start_datetime
        }

    def list_appointments(
        self,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 50
    ) -> List[Dict[str, any]]:
        """
        List appointments from Google Calendar

        Args:
            time_min: Start time in ISO format (defaults to now)
            time_max: End time in ISO format (defaults to 30 days from now)
            max_results: Maximum number of events to return

        Returns:
            List of appointment dictionaries
        """
        if not self.config.google_calendar_enabled:
            return self._get_mock_appointments()

        try:
            # Default to upcoming appointments (next 30 days)
            if not time_min:
                time_min = datetime.now(ZoneInfo(self.config.timezone)).isoformat()

            if not time_max:
                future_date = datetime.now(ZoneInfo(self.config.timezone)) + timedelta(days=30)
                time_max = future_date.isoformat()

            # Query calendar
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # Format appointments
            appointments = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))

                # Parse datetime
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))

                # Extract patient info from description
                description = event.get('description', '')
                patient_info = self._parse_patient_info(description)

                appointments.append({
                    'event_id': event['id'],
                    'summary': event.get('summary', 'No title'),
                    'patient_name': patient_info.get('patient_name', 'Unknown'),
                    'patient_phone': patient_info.get('patient_phone', ''),
                    'patient_email': patient_info.get('patient_email', ''),
                    'appointment_type': patient_info.get('appointment_type', 'initial'),
                    'start_time': start_dt.strftime('%Y-%m-%d %I:%M %p'),
                    'end_time': end_dt.strftime('%I:%M %p'),
                    'start_datetime': start,
                    'end_datetime': end,
                    'status': event.get('status', 'confirmed'),
                    'link': event.get('htmlLink', '')
                })

            return appointments

        except HttpError as e:
            print(f"Error listing appointments: {e}")
            return []

    def _parse_patient_info(self, description: str) -> Dict[str, str]:
        """Parse patient information from event description"""
        info = {}

        lines = description.split('\n')
        for line in lines:
            if 'Patient:' in line:
                info['patient_name'] = line.split('Patient:')[1].strip()
            elif 'Phone:' in line:
                info['patient_phone'] = line.split('Phone:')[1].strip()
            elif 'Email:' in line:
                info['patient_email'] = line.split('Email:')[1].strip()
            elif 'Type:' in line:
                type_text = line.split('Type:')[1].strip().lower()
                info['appointment_type'] = type_text.split()[0]  # Get first word

        return info

    def _get_mock_appointments(self) -> List[Dict[str, any]]:
        """Get mock appointments for testing"""
        now = datetime.now(ZoneInfo(self.config.timezone))

        return [
            {
                'event_id': 'mock_1',
                'summary': 'Initial Consultation - John Doe',
                'patient_name': 'John Doe',
                'patient_phone': '+971501234567',
                'patient_email': 'john@example.com',
                'appointment_type': 'initial',
                'start_time': (now + timedelta(days=1)).strftime('%Y-%m-%d %I:%M %p'),
                'end_time': (now + timedelta(days=1, hours=1)).strftime('%I:%M %p'),
                'status': 'confirmed',
                'link': '#'
            },
            {
                'event_id': 'mock_2',
                'summary': 'Follow-up Consultation - Jane Smith',
                'patient_name': 'Jane Smith',
                'patient_phone': '+971509876543',
                'patient_email': 'jane@example.com',
                'appointment_type': 'followup',
                'start_time': (now + timedelta(days=3)).strftime('%Y-%m-%d %I:%M %p'),
                'end_time': (now + timedelta(days=3, minutes=30)).strftime('%I:%M %p'),
                'status': 'confirmed',
                'link': '#'
            }
        ]


# Global instance
_calendar_service = None


def get_calendar_service() -> GoogleCalendarService:
    """Get or create global calendar service instance"""
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = GoogleCalendarService()
    return _calendar_service
