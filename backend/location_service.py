"""
Location Service for Healthcare Chatbot
Handles GPS coordinates to location conversion and pricing lookup
"""

import os
from typing import Dict, Optional
from datetime import datetime
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import requests


class LocationService:
    """Service for handling location-based operations"""

    def __init__(self):
        """Initialize location service with geocoding providers"""
        self.nominatim = Nominatim(user_agent="healthcare_chatbot_v2")
        self.google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')

        # In-memory storage for user locations (use Redis/DB for production)
        self.user_locations = {}

    def get_location_from_coordinates(
        self,
        latitude: float,
        longitude: float,
        use_google: bool = False
    ) -> Dict[str, str]:
        """
        Convert GPS coordinates to city/area information

        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            use_google: Use Google Maps API if available (more accurate)

        Returns:
            Dict with city, area, country, and full_address
        """
        # Try Google Maps API if key is available and requested
        if use_google and self.google_maps_api_key:
            try:
                return self._reverse_geocode_google(latitude, longitude)
            except Exception as e:
                print(f"⚠️  Google Maps API failed: {e}, falling back to Nominatim")

        # Use free Nominatim (OpenStreetMap) as default
        try:
            return self._reverse_geocode_nominatim(latitude, longitude)
        except Exception as e:
            print(f"❌ Geocoding failed: {e}")
            # Return default location
            return {
                'city': 'Dubai',
                'area': '',
                'country': 'UAE',
                'full_address': 'Dubai, UAE'
            }

    def _reverse_geocode_nominatim(
        self,
        latitude: float,
        longitude: float
    ) -> Dict[str, str]:
        """Reverse geocode using free OpenStreetMap Nominatim"""
        try:
            location = self.nominatim.reverse(
                f"{latitude}, {longitude}",
                language='en',
                timeout=10
            )

            if location:
                address = location.raw.get('address', {})

                # Extract city (try multiple fields)
                city = (
                    address.get('city') or
                    address.get('town') or
                    address.get('municipality') or
                    address.get('state') or
                    'Unknown'
                )

                # Extract area/suburb
                area = (
                    address.get('suburb') or
                    address.get('neighbourhood') or
                    address.get('district') or
                    ''
                )

                country = address.get('country', 'UAE')

                return {
                    'city': city,
                    'area': area,
                    'country': country,
                    'full_address': location.address
                }

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"⚠️  Nominatim timeout/error: {e}")

        # Fallback
        return {
            'city': 'Dubai',
            'area': '',
            'country': 'UAE',
            'full_address': 'Dubai, UAE'
        }

    def _reverse_geocode_google(
        self,
        latitude: float,
        longitude: float
    ) -> Dict[str, str]:
        """Reverse geocode using Google Maps API (requires API key)"""
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'latlng': f"{latitude},{longitude}",
            'key': self.google_maps_api_key,
            'language': 'en'
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data['status'] == 'OK' and data['results']:
            components = data['results'][0]['address_components']

            city = None
            area = None
            country = None

            for component in components:
                types = component['types']
                if 'locality' in types:
                    city = component['long_name']
                elif 'sublocality' in types or 'sublocality_level_1' in types:
                    area = component['long_name']
                elif 'country' in types:
                    country = component['long_name']

            return {
                'city': city or 'Unknown',
                'area': area or '',
                'country': country or 'UAE',
                'full_address': data['results'][0]['formatted_address']
            }

        raise Exception(f"Google Maps API error: {data.get('status')}")

    def store_user_location(
        self,
        user_id: str,
        location_info: Dict[str, str]
    ) -> None:
        """
        Store user location in session

        Args:
            user_id: Unique user identifier (phone number)
            location_info: Location information dict
        """
        self.user_locations[user_id] = {
            'location': location_info,
            'timestamp': datetime.now().isoformat(),
            'latitude': location_info.get('latitude'),
            'longitude': location_info.get('longitude')
        }

        print(f"📍 Stored location for {user_id}: {location_info['city']}")

    def get_user_location(self, user_id: str) -> Optional[Dict]:
        """
        Get stored user location

        Args:
            user_id: Unique user identifier

        Returns:
            Location dict or None if not found
        """
        return self.user_locations.get(user_id)

    def clear_user_location(self, user_id: str) -> None:
        """Clear stored location for a user"""
        if user_id in self.user_locations:
            del self.user_locations[user_id]


# Singleton instance
_location_service = None

def get_location_service() -> LocationService:
    """Get or create singleton location service instance"""
    global _location_service
    if _location_service is None:
        _location_service = LocationService()
    return _location_service
