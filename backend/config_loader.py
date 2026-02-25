"""
Configuration Loader - Loads clinic settings from config.yml
Makes the chatbot completely customizable for any healthcare business
"""

import yaml
import os
from typing import Dict, Any, List
from pathlib import Path


class ClinicConfig:
    """Centralized configuration for clinic-specific settings"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), 'config.yml')

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

    # Clinic Info
    @property
    def clinic_name(self) -> str:
        return self.config['clinic']['name']

    @property
    def clinic_type(self) -> str:
        return self.config['clinic']['type']

    # Contact
    @property
    def phone(self) -> str:
        return self.config['contact']['phone']

    @property
    def whatsapp(self) -> str:
        return self.config['contact']['whatsapp']

    @property
    def email(self) -> str:
        return self.config['contact']['email']

    @property
    def website(self) -> str:
        return self.config['contact']['website']

    # Location
    @property
    def location_address(self) -> str:
        return self.config['location']['address']

    @property
    def city(self) -> str:
        return self.config['location']['city']

    @property
    def area(self) -> str:
        return self.config['location']['area']

    # Hours
    @property
    def hours_display(self) -> str:
        return self.config['hours']['display_format']

    @property
    def timezone(self) -> str:
        return self.config['hours']['timezone']

    @property
    def schedule(self) -> List[Dict]:
        return self.config['hours']['schedule']

    # Pricing
    @property
    def currency(self) -> str:
        return self.config['pricing']['currency']

    @property
    def default_location(self) -> str:
        """Get default location for pricing"""
        return self.config['pricing'].get('default_location', 'Dubai')

    @property
    def pricing_locations(self) -> List[str]:
        """Get list of all available pricing locations"""
        return list(self.config['pricing']['locations'].keys())

    def get_location_pricing(self, location: str) -> Dict[str, Any]:
        """
        Get pricing for a specific location

        Args:
            location: City name (e.g., 'Dubai', 'Abu Dhabi', 'India', 'Cairo')

        Returns:
            Pricing dict for that location, or "Other" location if not found
        """
        locations = self.config['pricing']['locations']

        # Try exact match first
        if location in locations:
            return locations[location]

        # Try case-insensitive match
        for loc_key in locations:
            if loc_key.lower() == location.lower():
                return locations[loc_key]

        # Fallback to "Other" location (default for unrecognized locations)
        if "Other" in locations:
            return locations["Other"]

        # Final fallback to default_location if "Other" doesn't exist
        default = self.default_location
        return locations.get(default, list(locations.values())[0])

    # Backwards compatibility - use default location pricing
    @property
    def initial_consultation_price(self) -> int:
        """Get initial consultation price for default location"""
        default_pricing = self.get_location_pricing(self.default_location)
        return default_pricing['consultation']['initial']

    @property
    def followup_consultation_price(self) -> int:
        """Get follow-up consultation price for default location"""
        default_pricing = self.get_location_pricing(self.default_location)
        return default_pricing['consultation']['followup']

    @property
    def emergency_consultation_price(self) -> int:
        """Get emergency consultation price for default location"""
        default_pricing = self.get_location_pricing(self.default_location)
        return default_pricing['consultation']['emergency']

    @property
    def packages(self) -> List[Dict]:
        """Get packages for default location"""
        default_pricing = self.get_location_pricing(self.default_location)
        return default_pricing.get('packages', [])

    # Services
    @property
    def specialties(self) -> List[str]:
        return self.config['services']['specialties']

    @property
    def treatment_methods(self) -> List[str]:
        return self.config['services']['treatment_methods']

    # Lab Testing
    @property
    def available_tests(self) -> List[str]:
        return self.config['lab_testing']['available_tests']

    @property
    def lab_results_timing(self) -> Dict[str, str]:
        return self.config['lab_testing']['results_timing']

    # Appointments
    @property
    def initial_duration(self) -> int:
        return self.config['appointments']['initial_duration_minutes']

    @property
    def followup_duration(self) -> int:
        return self.config['appointments']['followup_duration_minutes']

    @property
    def cancellation_hours(self) -> int:
        return self.config['appointments']['cancellation_hours']

    # Google Calendar
    @property
    def google_calendar_enabled(self) -> bool:
        return self.config['google_calendar']['enabled']

    @property
    def google_calendar_id(self) -> str:
        return self.config['google_calendar']['calendar_id']

    @property
    def google_credentials_file(self) -> str:
        return self.config['google_calendar']['credentials_file']

    @property
    def google_token_file(self) -> str:
        return self.config['google_calendar']['token_file']

    # Bot Settings
    @property
    def use_emojis(self) -> bool:
        return self.config['bot']['use_emojis']

    @property
    def personality(self) -> str:
        return self.config['bot']['personality']

    # Helper methods
    def get_pricing_text(self, location: str = None) -> str:
        """
        Generate pricing display text for a location

        Args:
            location: City name (uses default if not provided)

        Returns:
            Formatted pricing text
        """
        if location is None:
            location = self.default_location

        pricing = self.get_location_pricing(location)
        consultation = pricing['consultation']

        return f"""💰 Consultation Fees ({location}):

• Initial consultation: {consultation['initial']} {self.currency}
• Follow-up consultation: {consultation['followup']} {self.currency}
• Emergency consultation: {consultation['emergency']} {self.currency}

Lab tests and supplements are charged separately."""

    def get_packages_text(self, location: str = None) -> str:
        """
        Generate packages display text for a location

        Args:
            location: City name (uses default if not provided)

        Returns:
            Formatted packages text
        """
        if location is None:
            location = self.default_location

        pricing = self.get_location_pricing(location)
        packages = pricing.get('packages', [])

        if not packages:
            return "Please contact us for package pricing information."

        text = f"Yes! We have packages that save you money! 🎁\n\n**Popular Packages ({location}):**\n"
        for pkg in packages:
            text += f"📦 **{pkg['name']}:** {pkg['description']} = {pkg['price']} {self.currency} (save {pkg['savings']} {self.currency}!)\n"
        text += f"\nPackages valid for {packages[0]['validity_months']} months. Which interests you?"
        return text

    def get_contact_text(self) -> str:
        """Generate contact info text"""
        return f"""📞 Contact Us:

• Phone: {self.phone}
• WhatsApp: {self.whatsapp}
• Email: {self.email}
• Website: {self.website}
• Location: {self.area}, {self.city}

{self.hours_display}"""

    def get_specialties_text(self) -> str:
        """Generate specialties list text"""
        text = "We treat a wide range of conditions: 🏥\n\n"
        for specialty in self.specialties:
            text += f"• {specialty}\n"
        text += "\nAnd more! Contact us to discuss your specific concern."
        return text

    def get_full_config(self) -> Dict[str, Any]:
        """Return complete configuration dictionary"""
        return self.config


# Global config instance
_config_instance = None


def get_config() -> ClinicConfig:
    """Get or create global config instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ClinicConfig()
    return _config_instance


# For easy imports
config = get_config()
