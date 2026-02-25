"""
Zoom Meeting Service for Healthcare Chatbot
Creates Zoom meetings for online consultations
"""

import os
import requests
import base64
from datetime import datetime, timedelta
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()


class ZoomService:
    """Manages Zoom meeting creation for online consultations"""

    def __init__(self):
        self.account_id = os.getenv('ZOOM_ACCOUNT_ID')
        self.client_id = os.getenv('ZOOM_CLIENT_ID')
        self.client_secret = os.getenv('ZOOM_CLIENT_SECRET')
        self.access_token = None
        self.token_expiry = None

        # Check if credentials are configured
        self.enabled = all([self.account_id, self.client_id, self.client_secret])

        if not self.enabled:
            print("⚠️  Zoom not configured - online consultations will not have video links")
        else:
            print("✅ Zoom service initialized")

    def _get_access_token(self) -> str:
        """Get OAuth access token from Zoom"""
        # Check if we have a valid token
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        # Get new token
        url = "https://zoom.us/oauth/token"

        # Create Basic Auth header
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "grant_type": "account_credentials",
            "account_id": self.account_id
        }

        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data['access_token']

            # Token expires in 1 hour, refresh 5 minutes early
            expires_in = token_data.get('expires_in', 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)

            print("✅ Zoom access token obtained")
            return self.access_token

        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting Zoom access token: {e}")
            raise Exception(f"Failed to authenticate with Zoom: {str(e)}")

    def create_meeting(
        self,
        topic: str,
        start_datetime: datetime,
        duration_minutes: int = 60,
        patient_name: str = "",
        patient_email: str = ""
    ) -> Dict:
        """
        Create a Zoom meeting for online consultation

        Args:
            topic: Meeting topic (e.g., "Consultation with John Doe")
            start_datetime: ISO format datetime string
            duration_minutes: Meeting duration (default: 60)
            patient_name: Patient's name
            patient_email: Patient's email (optional)

        Returns:
            Dictionary with meeting details:
            - join_url: URL for participants to join
            - start_url: URL for host to start meeting
            - meeting_id: Zoom meeting ID
            - password: Meeting password
        """
        if not self.enabled:
            return {
                'success': False,
                'error': 'Zoom not configured'
            }

        try:
            # Get access token
            access_token = self._get_access_token()

            # Zoom API endpoint
            url = "https://api.zoom.us/v2/users/me/meetings"

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Parse datetime for Zoom format (must be in UTC)
            # Your start_datetime should be in ISO format with timezone
            if isinstance(start_datetime, datetime):
                dt = start_datetime
            else:
                dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
            zoom_start_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            # Meeting settings
            payload = {
                "topic": topic,
                "type": 2,  # Scheduled meeting
                "start_time": zoom_start_time,
                "duration": duration_minutes,
                "timezone": "UTC",
                "agenda": f"Online consultation with Dr. Rania Said",
                "settings": {
                    "host_video": True,
                    "participant_video": True,
                    "join_before_host": False,  # Patient must wait for doctor
                    "mute_upon_entry": False,
                    "watermark": False,
                    "use_pmi": False,
                    "approval_type": 2,  # No registration required
                    "audio": "both",  # Telephone and computer audio
                    "auto_recording": "none",  # No auto recording (privacy)
                    "waiting_room": True,  # Enable waiting room for security
                    "meeting_authentication": False  # No auth required to join
                }
            }

            print(f"📞 Creating Zoom meeting for: {topic}")

            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()

            meeting_data = response.json()

            print(f"✅ Zoom meeting created: {meeting_data.get('id')}")

            return {
                'success': True,
                'join_url': meeting_data.get('join_url'),
                'start_url': meeting_data.get('start_url'),
                'meeting_id': str(meeting_data.get('id')),
                'password': meeting_data.get('password', ''),
                'meeting_data': meeting_data
            }

        except requests.exceptions.RequestException as e:
            print(f"❌ Error creating Zoom meeting: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def delete_meeting(self, meeting_id: str) -> Dict:
        """
        Delete a Zoom meeting

        Args:
            meeting_id: Zoom meeting ID

        Returns:
            Dictionary with success status
        """
        if not self.enabled:
            return {'success': False, 'error': 'Zoom not configured'}

        try:
            access_token = self._get_access_token()

            url = f"https://api.zoom.us/v2/meetings/{meeting_id}"

            headers = {
                "Authorization": f"Bearer {access_token}"
            }

            response = requests.delete(url, headers=headers, timeout=10)
            response.raise_for_status()

            print(f"✅ Zoom meeting deleted: {meeting_id}")

            return {'success': True}

        except requests.exceptions.RequestException as e:
            print(f"❌ Error deleting Zoom meeting: {e}")
            return {'success': False, 'error': str(e)}


# Global instance
_zoom_service = None


def get_zoom_service() -> ZoomService:
    """Get or create global Zoom service instance"""
    global _zoom_service
    if _zoom_service is None:
        _zoom_service = ZoomService()
    return _zoom_service
