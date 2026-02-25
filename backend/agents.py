"""
Multi-Agent System for Healthcare Chatbot (v2.2 - Bilingual)
Improved with contextual responses, dynamic templating, smart fallbacks, and Arabic support
"""

from typing import Dict, List, Optional
import random
from datetime import datetime, timedelta
import re
import pytz

from config_loader import get_config
from google_calendar_service import get_calendar_service
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError


# Language Detection Helper
def detect_language(text: str) -> str:
    """Detect if text is Arabic or English"""
    # Count Arabic characters
    arabic_chars = len([c for c in text if '\u0600' <= c <= '\u06FF'])
    total_chars = len([c for c in text if c.isalpha()])

    # If more than 30% Arabic characters, consider it Arabic
    if total_chars > 0 and (arabic_chars / total_chars) > 0.3:
        return 'ar'
    return 'en'


# Bilingual Response Templates
RESPONSES = {
    'greeting': {
        'en': [
            "Hello! 👋 Welcome to {clinic_name}.\n\nHow can I help you today?",
            "Hi there! 😊 Welcome to {clinic_name}. What would you like to know?",
        ],
        'ar': [
            "مرحباً! 👋 أهلاً بك في {clinic_name}.\n\nكيف يمكنني مساعدتك اليوم؟",
            "أهلاً وسهلاً! 😊 مرحباً بك في {clinic_name}. ماذا تريد أن تعرف؟",
        ]
    },
    'book_appointment': {
        'en': "📅 **Great! Let's book your appointment.**\n\n**Step 1/4:** Would you like an online or offline consultation?",
        'ar': "📅 **رائع! لنحجز موعدك.**\n\n**الخطوة 1 من 4:** هل تريد استشارة عبر الإنترنت أم في العيادة؟"
    },
    'online_button': {
        'en': "Online Consultation",
        'ar': "استشارة عبر الإنترنت"
    },
    'offline_button': {
        'en': "Offline (In-person)",
        'ar': "في العيادة (حضورياً)"
    },
    'select_date': {
        'en': "📅 **Appointment Type:** {type}\n\n**Step 2/4:** Select a date:",
        'ar': "📅 **نوع الموعد:** {type}\n\n**الخطوة 2 من 4:** اختر التاريخ المناسب:"
    },
    'select_time': {
        'en': "⏰ **Appointment Type:** {type}\n**Selected Date:** {date}\n\n**Step 3/4:** Choose a time slot:",
        'ar': "⏰ **نوع الموعد:** {type}\n**التاريخ المحدد:** {date}\n\n**الخطوة 3 من 4:** اختر الوقت المناسب:"
    },
    'ask_name': {
        'en': "📝 Great choice!\n\nTo complete your booking, what's your full name?",
        'ar': "📝 اختيار رائع!\n\nلإكمال حجزك، ما هو اسمك الكامل؟"
    },
    'ask_email': {
        'en': "Thanks! What's your email address?",
        'ar': "شكراً! ما هو بريدك الإلكتروني؟"
    },
    'ask_phone': {
        'en': "Perfect! And your phone number?",
        'ar': "ممتاز! وما هو رقم هاتفك؟"
    },
    'confirm_button_yes': {
        'en': "Yes, confirm booking",
        'ar': "نعم، تأكيد الحجز"
    },
    'confirm_button_no': {
        'en': "No, cancel",
        'ar': "لا، إلغاء"
    },
    'booking_success': {
        'en': "✅ **APPOINTMENT BOOKED SUCCESSFULLY!**",
        'ar': "✅ **تم حجز الموعد بنجاح!**"
    },
    'patient_label': {
        'en': "👤 Patient:",
        'ar': "👤 المريض:"
    },
    'type_label': {
        'en': "🏥 Type:",
        'ar': "🏥 النوع:"
    },
    'date_label': {
        'en': "📅 Date:",
        'ar': "📅 التاريخ:"
    },
    'time_label': {
        'en': "⏰ Time:",
        'ar': "⏰ الوقت:"
    },
    'location_label': {
        'en': "📍 **LOCATION**",
        'ar': "📍 **الموقع**"
    },
    'zoom_meeting_label': {
        'en': "🎥 **ZOOM MEETING**",
        'ar': "🎥 **اجتماع زوم**"
    },
    'existing_booking': {
        'en': "✅ You already have an appointment booked!\n\n**Your Current Booking:**\n🏥 {type}\n📅 {date} at {time}\n\n**Would you like to:**\n• Keep this appointment\n• Book an additional appointment\n• Reschedule this one\n\nPlease let me know!",
        'ar': "✅ لديك موعد محجوز بالفعل!\n\n**موعدك الحالي:**\n🏥 {type}\n📅 {date} في {time}\n\n**هل تريد:**\n• الاحتفاظ بهذا الموعد\n• حجز موعد إضافي\n• إعادة جدولة هذا الموعد\n\nأخبرني من فضلك!"
    },
    'appointment_summary': {
        'en': "📋 **APPOINTMENT SUMMARY**",
        'ar': "📋 **ملخص الموعد**"
    },
    'confirm_step': {
        'en': "**Step 4/4:** Confirm your booking",
        'ar': "**الخطوة 4 من 4:** تأكيد حجزك"
    },
    'email_confirmation': {
        'en': "You'll receive a confirmation email shortly.",
        'ar': "ستتلقى رسالة تأكيد عبر البريد الإلكتروني قريباً."
    },
    'looking_forward': {
        'en': "Looking forward to seeing you! 🌟",
        'ar': "نتطلع إلى رؤيتك! 🌟"
    }
}


class ConversationContext:
    """Manages conversation state and context across agents"""

    def __init__(self):
        self.contexts: Dict[str, Dict] = {}

    def get_context(self, sender_id: str) -> Dict:
        """Get conversation context for a user"""
        if sender_id not in self.contexts:
            self.contexts[sender_id] = {
                'sender_id': sender_id,    # NEW: Include sender_id in context for agent use
                'history': [],
                'last_agent': None,
                'last_intent': None,
                'last_response': None,
                'current_flow': None,      # NEW: Track active conversation flow (e.g., 'booking')
                'flow_data': {},           # NEW: Store flow-specific data (e.g., booking info)
                'user_info': {},           # Store name, email, phone, etc.
                'language': 'en',          # NEW: User's preferred language (en/ar)
                'timestamp': datetime.now()
            }
        # Always ensure sender_id is set (in case old contexts don't have it)
        self.contexts[sender_id]['sender_id'] = sender_id
        return self.contexts[sender_id]

    def update_context(self, sender_id: str, agent_name: str, intent: str, message: str, response: str = None):
        """Update conversation context"""
        context = self.get_context(sender_id)

        # Detect and store language preference
        detected_lang = detect_language(message)
        context['language'] = detected_lang

        context['history'].append({
            'agent': agent_name,
            'intent': intent,
            'user_message': message,
            'bot_response': response,
            'timestamp': datetime.now()
        })
        context['last_agent'] = agent_name
        context['last_intent'] = intent
        context['last_response'] = response
        context['timestamp'] = datetime.now()

        # Extract user info from message
        self._extract_user_info(context, message)

        # Keep more history for OpenAI context (20 messages instead of 10)
        if len(context['history']) > 20:
            context['history'] = context['history'][-20:]

    def get_recent_messages(self, sender_id: str, count: int = 4) -> List[Dict]:
        """Get last N messages from history"""
        context = self.get_context(sender_id)
        return context['history'][-count:] if context['history'] else []

    def _extract_user_info(self, context: Dict, message: str):
        """Extract user information from messages"""
        # Extract name (if not already set)
        if 'name' not in context['user_info']:
            # Excluded words that are greetings, not names
            excluded_greetings = ['hello', 'hi', 'hey', 'greetings', 'good', 'morning', 'afternoon', 'evening', 'bye', 'goodbye', 'thanks', 'thank', 'yes', 'no', 'okay', 'ok', 'online', 'offline', 'consultation', 'person']

            # Try common name patterns first
            name_patterns = [
                r"(?:my name is|i'm|i am|this is|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",  # "My name is John Doe"
                r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*$",  # Just "John Doe" alone
                r"^([A-Z][a-z]+)$",  # Just "John" alone
            ]
            for pattern in name_patterns:
                name_match = re.search(pattern, message, re.IGNORECASE)
                if name_match:
                    extracted_name = name_match.group(1).strip()

                    # Skip if it's a common greeting or contains excluded words
                    name_words = extracted_name.lower().split()
                    if extracted_name.lower() in excluded_greetings or any(word in excluded_greetings for word in name_words):
                        continue

                    # Capitalize properly (in case user typed lowercase)
                    extracted_name = ' '.join(word.capitalize() for word in extracted_name.split())
                    context['user_info']['name'] = extracted_name
                    break

        # Extract email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message)
        if email_match:
            context['user_info']['email'] = email_match.group()

        # Extract phone (simple pattern)
        phone_match = re.search(r'\+?\d[\d\s\-\(\)]{8,}\d', message)
        if phone_match:
            context['user_info']['phone'] = phone_match.group()

    def set_flow(self, sender_id: str, flow_name: str, flow_data: Dict = None):
        """Set the current conversation flow (e.g., 'booking')"""
        context = self.get_context(sender_id)
        context['current_flow'] = flow_name
        if flow_data:
            context['flow_data'].update(flow_data)
        print(f"   🔄 Flow set: {flow_name}")

    def clear_flow(self, sender_id: str):
        """Clear the current conversation flow"""
        context = self.get_context(sender_id)
        flow_name = context.get('current_flow')
        context['current_flow'] = None
        context['flow_data'] = {}
        if flow_name:
            print(f"   ✅ Flow cleared: {flow_name}")

    def get_flow(self, sender_id: str) -> Optional[str]:
        """Get the current conversation flow"""
        context = self.get_context(sender_id)
        return context.get('current_flow')

    def validate_flow_state(self, sender_id: str) -> Dict:
        """Validate and return current flow state for debugging"""
        context = self.get_context(sender_id)

        return {
            'has_flow': context.get('current_flow') is not None,
            'flow_name': context.get('current_flow'),
            'flow_step': context.get('flow_data', {}).get('booking_step'),
            'collected_info': list(context.get('user_info', {}).keys()),
            'history_count': len(context.get('history', []))
        }


class BaseAgent:
    """Base class for all specialized agents"""

    def __init__(self, name: str, context_manager: 'ConversationContext' = None):
        self.name = name
        self.config = get_config()
        self.context_manager = context_manager  # NEW: Access to context manager for flow control

    def handle(self, intent: str, message: str, context: Dict) -> str:
        """Handle the intent and return a natural response"""
        raise NotImplementedError("Each agent must implement handle()")

    def set_booking_flow(self, context: Dict):
        """Helper to set booking flow from context"""
        if self.context_manager and 'sender_id' in context:
            self.context_manager.set_flow(context['sender_id'], 'booking')

    def clear_booking_flow(self, context: Dict):
        """Helper to clear booking flow from context"""
        if self.context_manager and 'sender_id' in context:
            self.context_manager.clear_flow(context['sender_id'])

    def emoji(self, emoji_str: str) -> str:
        """Return emoji if enabled in config"""
        return emoji_str if self.config.use_emojis else ""

    def get_response(self, key: str, context: Dict, **kwargs) -> str:
        """Get bilingual response based on user's language"""
        lang = context.get('language', 'en')
        template = RESPONSES.get(key, {})

        if isinstance(template, dict):
            response = template.get(lang, template.get('en', ''))
            if isinstance(response, list):
                response = random.choice(response)
        else:
            response = template

        # Format with kwargs if provided
        if kwargs:
            try:
                response = response.format(**kwargs)
            except KeyError:
                pass  # Ignore missing format keys

        return response

    def get_user_name(self, context: Dict) -> str:
        """Get user name from context or use friendly default"""
        return context['user_info'].get('name', '')

    def personalize_greeting(self, context: Dict) -> str:
        """Create personalized greeting based on context"""
        user_name = self.get_user_name(context)
        if user_name:
            return f"{user_name}, "
        return ""

    def suggest_next_agent(self, agent_type: str) -> str:
        """Suggest transitioning to another agent"""
        suggestions = {
            'appointment': f"Would you like to book an appointment now? {self.emoji('📅')}",
            'pricing': f"Would you like to know about our pricing? {self.emoji('💰')}",
            'lab_test': f"Do you have questions about lab tests? {self.emoji('🔬')}",
            'treatment': f"Curious about our treatment approach? {self.emoji('🩺')}",
        }
        return suggestions.get(agent_type, "What else can I help you with?")

    def get_available_slots(self, days_ahead=7, appointment_type=None):
        """
        FAST version for UI / chat flow
        - NO Google Calendar calls
        - Only checks clinic schedule
        - Returns dates that *can* have slots
        """
        hours = self.config.config['hours']
        schedule = hours['schedule']

        day_type_mapping = {
            s['day']: s.get('appointment_type')
            for s in schedule
        }

        # 👇 get appointment durations from config
        appt_cfg = self.config.config.get("appointments", {})

        def get_duration(appt_type):
            if appt_type == "followup":
                return appt_cfg.get("followup_duration_min_minutes", 15)
            if appt_type == "extended":
                return appt_cfg.get("extended_duration_minutes", 15)
            return appt_cfg.get("initial_duration_min_minutes", 20)

        slots_by_date = {}
        today = datetime.now().date()

        for offset in range(days_ahead):
            check_date = today + timedelta(days=offset + 1)
            date_str = check_date.strftime('%Y-%m-%d')
            day_name = check_date.strftime('%A')

            # ❌ Clinic closed
            if day_name not in day_type_mapping:
                continue

            # ❌ Appointment type mismatch
            if appointment_type and day_type_mapping[day_name] != appointment_type:
                continue

            working_hours = self._get_working_hours(day_name)
            if not working_hours:
                continue

            duration_minutes = get_duration(appointment_type)

            slots = self._generate_slots(
                date_str,
                working_hours['open'],
                working_hours['close'],
                duration_minutes
            )

            if slots:
                slots_by_date[date_str] = True

            # UI needs max 5 dates
            if len(slots_by_date) >= 5:
                break

        return slots_by_date

    def get_available_slots_for_date(self, date: str):
        """
        REAL availability check
        - Google Calendar authoritative
        - Used ONLY before booking
        """
        if not self.config.google_calendar_enabled:
            return self._get_mock_slots(date)

        try:
            target_date = datetime.strptime(date, '%Y-%m-%d')
            day_name = target_date.strftime('%A')

            working_hours = self._get_working_hours(day_name)
            if not working_hours:
                return []

            slots = self._generate_slots(
                date,
                working_hours['open'],
                working_hours['close'],
                self.config.initial_duration
            )

            # ✅ Google API ONLY HERE
            return [
                slot for slot in slots
                if self._is_slot_available(
                    slot['start_datetime'],
                    slot['end_datetime']
                )
            ]

        except Exception as e:
            print(f"Error getting available slots for {date}: {e}")
            return []

class AppointmentAgent(BaseAgent):
    """Handles all appointment and booking related queries"""

    def __init__(self, context_manager=None):
        super().__init__("Appointment Agent", context_manager)

    def _get_working_hours(self, day_name: str):
        """
        Returns working hours for a given day from config
        """
        try:
            hours = self.config.config['hours']

            for schedule in hours['schedule']:
                if schedule['day'] == day_name:
                    return {
                        'open': schedule['open'],
                        'close': schedule['close'],
                        'appointment_type': schedule.get('appointment_type')
                    }

            return None

        except Exception as e:
            print(f"Error reading working hours: {e}")
            return None

    def _is_slot_available(self, start_dt, end_dt):
        """
        Check if a slot is available (not booked in Google Calendar)
        """

        # If Google Calendar is disabled, all slots are available
        if not self.config.google_calendar_enabled:
            return True

        try:
            calendar_service = get_calendar_service()

            # Check for overlapping events
            events = calendar_service.get_events_between(start_dt, end_dt)

            # Slot is available if no overlapping events
            return len(events) == 0

        except Exception as e:
            print(f"Error checking slot availability: {e}")
            # Fail-safe: treat slot as unavailable on error
            return False
    
    def _generate_slots(
        self,
        date: str,
        open_time: str,
        close_time: str,
        duration_minutes: int
    ):
        """
        Generate time slots between open and close time for a given date
        """

        slots = []

        try:
            # Timezone from config
            tz_name = self.config.config['hours'].get('timezone', 'UTC')
            tz = pytz.timezone(tz_name)

            date_obj = datetime.strptime(date, "%Y-%m-%d").date()

            start_dt = tz.localize(
                datetime.combine(
                    date_obj,
                    datetime.strptime(open_time, "%H:%M").time()
                )
            )

            end_dt = tz.localize(
                datetime.combine(
                    date_obj,
                    datetime.strptime(close_time, "%H:%M").time()
                )
            )

            current = start_dt
            while current + timedelta(minutes=duration_minutes) <= end_dt:
                slots.append({
                    "start_time": current.strftime("%H:%M"),
                    "end_time": (current + timedelta(minutes=duration_minutes)).strftime("%H:%M"),
                    "start_datetime": current,
                    "end_datetime": current + timedelta(minutes=duration_minutes)
                })
                current += timedelta(minutes=duration_minutes)

            return slots

        except Exception as e:
            print(f"Error generating slots for {date}: {e}")
            return []        

    def handle(self, intent: str, message: str, context: Dict) -> Dict:
        """Handle appointment-related intents with context awareness

        Returns: Dict with 'message' and optional 'buttons' for frontend interaction
        """

        last_intent = context.get('last_intent')
        user_name = self.personalize_greeting(context)
        flow_data = context.get('flow_data', {})
        current_step = flow_data.get('booking_step')

        # Check if user is responding to a booking flow step
        if current_step:
            return self._handle_booking_step(message, context, current_step)

        if intent == 'ask_hours':
            # Check if user has a recent booking
            last_booking = context.get('last_booking')

            if last_booking:
                # Personalized response confirming their booking
                date = last_booking.get('date')
                time = last_booking.get('time')

                return {'message': f"{self.emoji('⏰')} Perfect timing to ask!\n\n**Your appointment is confirmed for:**\n📅 {date} at {time}\n\n**Our clinic hours:**\n{self.config.hours_display}\n\nYour appointment fits perfectly within our schedule! See you then! {self.emoji('🌟')}", 'buttons': []}
            else:
                # Generic response
                responses = [
                    f"{self.emoji('⏰')} {user_name}our clinic hours are:\n\n{self.config.hours_display}\n\nWould you like to book an appointment for one of these days?",
                    f"Great question{', ' + user_name.rstrip(', ') if user_name else ''}! We're open:\n{self.config.hours_display}\n\nShall I help you schedule a visit?",
                    f"Here's when we're available:\n\n{self.config.hours_display}\n\n{self.emoji('📅')} Ready to book your appointment?",
                ]
                return {'message': random.choice(responses), 'buttons': []}

        elif intent == 'book_appointment':
            # Check if user already has a recent booking
            last_booking = context.get('last_booking')

            if last_booking:
                # User already has a booking - confirm before rebooking
                date = last_booking.get('date')
                time = last_booking.get('time')
                apt_type = last_booking.get('appointment_type_display')

                message = self.get_response('existing_booking', context, type=apt_type, date=date, time=time)
                return {'message': message, 'buttons': []}
            else:
                # No existing booking - proceed with new booking
                # SET BOOKING FLOW - User is now in booking process
                self.set_booking_flow(context)

                # Start with appointment type selection (online/offline)
                return self._show_appointment_type_options(context)

        elif intent == 'ask_online_consultation':
            responses = [
                f"Yes! {user_name}we offer virtual consultations! {self.emoji('💻')}\n\n**What you get:**\n{self.emoji('✅')} Full video consultation with doctor\n{self.emoji('✅')} Same thorough assessment\n{self.emoji('✅')} Lab result review\n{self.emoji('✅')} Personalized treatment plan\n\n**Available:** Thursday & Saturday, 9 AM - 5 PM\n\nPerfect if you can't visit in person. **Ready to book a virtual visit?**",
                f"Absolutely! Virtual consultations are available! {self.emoji('🎥')}\n\n**Schedule:** Thursday & Saturday, 9 AM - 5 PM\n\nYou'll get the same quality care from home:\n• Video call with doctor\n• Complete health assessment\n• Treatment plan discussion\n\n**Would you like to schedule a virtual consultation?**",
            ]
            return {'message': random.choice(responses), 'buttons': []}

        elif intent == 'ask_virtual_consult':
            return {'message': f"Absolutely! {user_name}Dr. Rania Said sees 25-30 patients daily, both online and offline, serving families all over the world! {self.emoji('🌍')}\n\n**International Patients Welcome:**\n{self.emoji('✅')} Video consultations available globally\n{self.emoji('✅')} Patients from India, Saudi Arabia, UK, USA, Canada & more\n{self.emoji('✅')} Same quality care, from anywhere\n{self.emoji('✅')} Online lab result review\n{self.emoji('✅')} Time-zone friendly scheduling\n\n**Online Consultation Days:** Thursday & Saturday, 9 AM - 5 PM\n\n**Perfect for:**\n• Families living abroad\n• Follow-up consultations\n• Lab result reviews\n• Pediatric nutrition guidance\n\n**Where are you located?** I can help you book a virtual consultation that works for your time zone!", 'buttons': []}

        elif intent == 'ask_waiting_time':
            wait_times = self.config.config['appointments']['average_wait_days']
            responses = [
                f"Great question! {self.emoji('⏰')} {user_name}here's our typical availability:\n\n• **Urgent cases:** {wait_times['urgent']}\n• **Regular appointments:** {wait_times['regular']}\n• **Follow-ups:** {wait_times['followup']}\n\n**Is this urgent for you?** I can help prioritize your booking!",
                f"{user_name.capitalize() if user_name else 'W'}e try to see patients quickly! {self.emoji('🏃')}\n\n⏱️ **Current wait times:**\n• Urgent: {wait_times['urgent']}\n• Regular: {wait_times['regular']}\n• Follow-up: {wait_times['followup']}\n\n**Do you need to be seen urgently?**",
            ]
            return {'message': random.choice(responses), 'buttons': []}

        elif intent == 'ask_walk_in':
            responses = [
                f"While we accept walk-ins when possible, {user_name}I highly recommend booking to guarantee your spot! {self.emoji('📅')}\n\n**Why book?**\n{self.emoji('✅')} Guaranteed time slot (no waiting)\n{self.emoji('✅')} Doctor has time to review your case\n{self.emoji('✅')} You get the attention you deserve\n\n**Can I help you book an appointment now?**",
                f"Here's the deal with walk-ins:\n\n• **Walk-ins:** May wait 1-2 hours (if slots available)\n• **Bookings:** Your dedicated time guaranteed\n\nBooking ensures you're not stuck waiting! {self.emoji('⏰')}\n\n**Shall I help you schedule a time that works for you?**",
            ]
            return {'message': random.choice(responses), 'buttons': []}

        elif intent == 'ask_consultation_duration':
            # Check if user has a recent booking
            last_booking = context.get('last_booking')

            if last_booking:
                # Personalized response referencing their booking
                date = last_booking.get('date')
                time = last_booking.get('time')
                apt_type = last_booking.get('appointment_type_display')

                return {'message': f"Great question! {self.emoji('⏰')}\n\nYour **{apt_type}** consultation on **{date} at {time}** will be approximately **{self.config.initial_duration} minutes**.\n\nThis gives us enough time to:\n{self.emoji('✅')} Review your health history\n{self.emoji('✅')} Discuss your concerns thoroughly\n{self.emoji('✅')} Create a personalized treatment plan\n\n{self.emoji('💡')} **Note:** Complex cases may require up to 60 minutes - we never rush your health!\n\nLooking forward to seeing you! {self.emoji('🌟')}", 'buttons': []}
            else:
                # Generic response
                followup_max = self.config.config['appointments'].get('followup_duration_max_minutes', 30)
                complex_duration = self.config.config['appointments'].get('complex_case_duration_minutes', 60)

                return {'message': f"We give you proper time! {self.emoji('⏰')} {user_name}no rushing here.\n\n**Consultation Duration:**\n\n{self.emoji('📋')} **Initial Consultation:** {self.config.initial_duration} minutes\n• Comprehensive health assessment\n• Review of medical history\n• Personalized treatment plan\n\n{self.emoji('🔄')} **Follow-up Visit:** {self.config.followup_duration}-{followup_max} minutes\n• Progress review\n• Treatment adjustments\n• Questions & guidance\n\n{self.emoji('🔬')} **Complex Cases:** Up to {complex_duration} minutes\n• In-depth analysis required\n• Multiple health concerns\n• Comprehensive lab review\n\n{self.emoji('💡')} We tailor each session to your needs - quality over speed!\n\n**Ready to book your consultation?**", 'buttons': []}

        elif intent == 'ask_cancellation_policy':
            hours = self.config.cancellation_hours
            fee = self.config.config['appointments']['cancellation_fee_percent']
            last_booking = context.get('last_booking')

            base_message = f"We understand plans change! {self.emoji('🔄')}\n\n{self.emoji('✅')} **Free cancellation:** {hours} hours before appointment\n{self.emoji('⚠️')} **Late cancellation (<{hours}hrs):** {fee}% fee\n{self.emoji('❌')} **No-show:** Full fee charged"

            if last_booking:
                date = last_booking.get('date')
                time = last_booking.get('time')
                return {'message': f"{base_message}\n\n**Your upcoming appointment:**\n📅 {date} at {time}\n\nNeed to cancel or reschedule? Contact us at {self.config.whatsapp} at least {hours} hours before to avoid any fees!", 'buttons': []}
            else:
                return {'message': f"{base_message}\n\n**Just give us a heads-up and we'll work with you!**\n\nNeed to cancel or reschedule an existing appointment?", 'buttons': []}

        elif intent == 'ask_reschedule':
            last_booking = context.get('last_booking')

            if last_booking:
                date = last_booking.get('date')
                time = last_booking.get('time')
                return {'message': f"Of course! Let's reschedule your appointment. {self.emoji('📅')}\n\n**Your current booking:**\n📅 {date} at {time}\n\n**To reschedule:**\n1️⃣ Call/WhatsApp: {self.config.whatsapp}\n2️⃣ Give us {self.config.cancellation_hours}hrs notice (no fee)\n3️⃣ Pick your new time\n\nWe'll find a time that works better for you!", 'buttons': []}
            else:
                return {'message': f"Of course! {user_name}rescheduling is easy! {self.emoji('📅')}\n\n**3 Simple Steps:**\n1️⃣ Call/WhatsApp: {self.config.whatsapp}\n2️⃣ Give us {self.config.cancellation_hours}hrs notice (no fee)\n3️⃣ Pick your new time\n\nWe'll find a time that works better for you!\n\n**Do you need to reschedule an appointment right now?**", 'buttons': []}

        elif intent == 'inform':
            # User is providing information - check if it's booking-related
            return self._handle_inform_intent(message, context)

        # Default fallback
        return {'message': f"I can help you with appointments! {self.emoji('📅')} {user_name}ask me about:\n• Working hours\n• Booking appointments\n• Online consultations\n• Our policies\n\n**What would you like to know?**", 'buttons': []}

    def _handle_inform_intent(self, message: str, context: Dict) -> Dict:
        """Handle 'inform' intent - user providing information (possibly booking details)"""

        flow_data = context.get('flow_data', {})
        current_step = flow_data.get('booking_step')

        # If already in a booking flow step, use the existing handler
        if current_step:
            return self._handle_booking_step(message, context, current_step)

        # Not in booking flow - check if message contains booking-related info
        # Extract potential booking details from the message
        has_email = bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message))
        has_phone = bool(re.search(r'\+?\d[\d\s\-\(\)]{8,}\d', message))
        has_date = bool(re.search(r'\b\d{1,2}[\s/-]*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december)[\s/-]*\d{0,4}\b', message, re.IGNORECASE)) or \
                   bool(re.search(r'\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', message, re.IGNORECASE))
        has_time = bool(re.search(r'\b\d{1,2}[\s:]\d{0,2}\s*(am|pm|:00)?\b', message, re.IGNORECASE))

        # Check if this looks like booking information
        booking_score = sum([has_email, has_phone, has_date, has_time])

        if booking_score >= 2:  # At least 2 pieces of booking info
            # User is providing booking details - start booking flow
            print(f"   🔍 Detected booking info in message (score: {booking_score}/4)")

            # Extract and store whatever info we can from the message
            if has_email:
                email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message)
                context['user_info']['email'] = email_match.group()

            if has_phone:
                phone_match = re.search(r'\+?\d[\d\s\-\(\)]{8,}\d', message)
                context['user_info']['phone'] = phone_match.group()

            # Try to extract name (words before email/phone)
            name_match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', message)
            if name_match:
                context['user_info']['name'] = name_match.group(1).strip()

            # Set booking flow and proceed
            self.set_booking_flow(context)

            # Show them what we collected and start the booking process
            collected = []
            if 'name' in context['user_info']:
                collected.append(f"Name: {context['user_info']['name']}")
            if 'email' in context['user_info']:
                collected.append(f"Email: {context['user_info']['email']}")
            if 'phone' in context['user_info']:
                collected.append(f"Phone: {context['user_info']['phone']}")

            collected_text = "\n".join([f"✅ {item}" for item in collected])

            return {
                'message': f"{self.emoji('📋')} Great! I've got your information:\n\n{collected_text}\n\nLet me help you book an appointment. Let's choose a date and time!",
                'buttons': []
            }

        # Not booking-related - generic response
        return {
            'message': f"Thanks for the information! How can I help you with your appointment?\n\n{self.emoji('📅')} Book an appointment\n{self.emoji('💬')} Ask about availability\n{self.emoji('❓')} Other questions",
            'buttons': []
        }

    def _handle_booking_step(self, message: str, context: Dict, step: str) -> Dict:
        """Handle user responses during booking flow steps"""

        flow_data = context.get('flow_data', {})

        if step == 'awaiting_appointment_type':
            # User selected online or offline
            return self._handle_appointment_type_selection(message, context)

        elif step == 'awaiting_date':
            # User selected a date
            return self._handle_date_selection(message, context)

        elif step == 'awaiting_time':
            # User selected a time slot
            return self._handle_time_selection(message, context)

        elif step == 'awaiting_confirmation':
            # User confirmed or cancelled
            return self._handle_confirmation(message, context)

        elif step == 'awaiting_name':
            # User provided name
            context['user_info']['name'] = message.strip()

            # Check if we already have email and phone
            has_email = 'email' in context['user_info']
            has_phone = 'phone' in context['user_info']

            if not has_email:
                context['flow_data']['booking_step'] = 'awaiting_email'
                message = self.get_response('ask_email', context)
                return {'message': message, 'buttons': []}
            elif not has_phone:
                context['flow_data']['booking_step'] = 'awaiting_phone'
                message = self.get_response('ask_phone', context)
                return {'message': message, 'buttons': []}
            else:
                # We have everything, show confirmation
                return self._show_confirmation(context)

        elif step == 'awaiting_email':
            # User provided email
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            email_match = re.search(email_pattern, message)

            if email_match:
                context['user_info']['email'] = email_match.group()

                # Check if we already have phone
                has_phone = 'phone' in context['user_info']

                if not has_phone:
                    context['flow_data']['booking_step'] = 'awaiting_phone'
                    message = self.get_response('ask_phone', context)
                    return {'message': message, 'buttons': []}
                else:
                    # We have everything, show confirmation
                    return self._show_confirmation(context)
            else:
                return {'message': "Please provide a valid email address (e.g., yourname@example.com).", 'buttons': []}

        elif step == 'awaiting_phone':
            # User provided phone
            phone = re.sub(r'[\s\-\(\)]', '', message)

            # Validate UAE phone pattern
            uae_pattern = r'^(\+971|00971|0)?[0-9]{9,10}$'
            if re.match(uae_pattern, phone):
                # Normalize to international format
                if phone.startswith('00971'):
                    phone = '+971' + phone[5:]
                elif phone.startswith('0'):
                    phone = '+971' + phone[1:]
                elif not phone.startswith('+'):
                    phone = '+971' + phone

                context['user_info']['phone'] = phone

                # After phone, ask for location confirmation
                return self._ask_location_confirmation(context)
            else:
                return {'message': "Please provide a valid UAE phone number (e.g., +971501234567 or 0501234567).", 'buttons': []}

        elif step == 'awaiting_location_confirmation':
            # User confirmed or denied their location
            return self._handle_location_confirmation(message, context)

        return {'message': "I didn't understand that. Let's start over.", 'buttons': []}

    def _ask_location_confirmation(self, context: Dict) -> Dict:
        """Ask user to confirm their location before showing pricing"""
        user_info = context['user_info']

        # Check if we have a stored location for this user (from GPS share via WhatsApp)
        user_location = user_info.get('location')

        if user_location:
            # We have a detected location - ask for confirmation
            context['flow_data']['booking_step'] = 'awaiting_location_confirmation'
            return {
                'message': f"📍 Is your location **{user_location}**?\n\nThis helps us show you the correct consultation pricing.",
                'buttons': ['Yes, that\'s correct', 'No, use default pricing']
            }
        else:
            # No location detected - use default location and proceed directly
            context['user_info']['location'] = self.config.default_location
            return self._show_confirmation(context)

    def _handle_location_confirmation(self, message: str, context: Dict) -> Dict:
        """Handle user's response to location confirmation"""
        message_lower = message.lower()

        if 'yes' in message_lower or 'correct' in message_lower:
            # Location confirmed - proceed to final confirmation
            return self._show_confirmation(context)
        else:
            # User wants default pricing
            context['user_info']['location'] = self.config.default_location
            return self._show_confirmation(context)

    def _show_appointment_type_options(self, context: Dict) -> Dict:
        """Step 0: Ask for appointment type (online/offline)"""

        # Update booking step
        context['flow_data']['booking_step'] = 'awaiting_appointment_type'

        message = self.get_response('book_appointment', context)
        online_btn = self.get_response('online_button', context)
        offline_btn = self.get_response('offline_button', context)

        return {
            'message': message,
            'buttons': [online_btn, offline_btn]
        }

    def _handle_appointment_type_selection(self, message: str, context: Dict) -> Dict:
        """Handle user's appointment type selection"""

        flow_data = context['flow_data']
        message_lower = message.lower()

        # Determine appointment type from message
        if 'online' in message_lower or 'virtual' in message_lower:
            appointment_type = 'online'
            display_text = 'Online Consultation'
        elif 'offline' in message_lower or 'person' in message_lower or 'clinic' in message_lower or 'visit' in message_lower:
            appointment_type = 'offline'
            display_text = 'Offline (In-person)'
        else:
            return {
                'message': "Please select either 'Online Consultation' or 'Offline (In-person)'.",
                'buttons': ['Online Consultation', 'Offline (In-person)']
            }

        # Store appointment type in flow data
        flow_data['appointment_type'] = appointment_type
        flow_data['appointment_type_display'] = display_text

        # Now show date options
        return self._show_date_options(context)

    def _show_date_options(self, context: Dict) -> Dict:
        """Step 1: Show available dates as buttons (FAST, UI-only)"""

        flow_data = context.get('flow_data', {})
        appointment_type = flow_data.get('appointment_type', 'online')

        # ✅ FAST method — NO Google calls
        slots_by_date = self.get_available_slots(
            days_ahead=14,
            appointment_type=appointment_type
        )

        print(f"\n📅 _show_date_options DEBUG:")
        print(f"   Appointment type: {appointment_type}")
        print(f"   Slots returned: {len(slots_by_date)} dates")
        print(f"   Date keys: {list(slots_by_date.keys())}")

        if not slots_by_date:
            days_info = (
                "Thursday or Saturday"
                if appointment_type == "online"
                else "Monday, Tuesday, Wednesday, or Friday"
            )

            return {
                "message": (
                    f"Sorry, no {appointment_type} appointments available "
                    f"in the next 14 days ({days_info}). "
                    f"Please contact us at {self.config.phone}."
                ),
                "buttons": []
            }

        # Store dates for next step
        flow_data["available_dates"] = slots_by_date
        flow_data["booking_step"] = "awaiting_date"

        # Create max 5 buttons
        date_buttons = []
        for date_str in list(slots_by_date.keys())[:5]:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            label = date_obj.strftime("%A, %b %d")
            date_buttons.append(label)
            print(f"   Added button: {label}")

        appointment_type_display = flow_data.get(
            "appointment_type_display",
            "Consultation"
        )

        message = self.get_response(
            "select_date",
            context,
            type=appointment_type_display
        )

        return {
            "message": message,
            "buttons": date_buttons
        }

    def _handle_date_selection(self, message: str, context: Dict) -> Dict:
        flow_data = context['flow_data']
        available_dates = flow_data.get('available_dates', {})

        selected_date = None
        for date_str in available_dates.keys():
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            label = date_obj.strftime('%A, %b %d')

            if label.lower() in message.lower():
                selected_date = date_str
                flow_data['selected_date'] = date_str
                flow_data['selected_date_display'] = label
                break

        if not selected_date:
            return {
                'message': "Please select a valid date from above.",
                'buttons': []
            }

        # 🔥 REAL availability check (Google Calendar)
        calendar_service = get_calendar_service()
        slots = calendar_service.get_available_slots_for_date(selected_date)

        if not slots:
            return {
                'message': "Sorry, no time slots available for this date. Please choose another date.",
                'buttons': []
            }

        flow_data['available_slots'] = slots
        flow_data['booking_step'] = 'awaiting_time'

        return self._show_time_options(context)

    def _show_time_options(self, context: Dict) -> Dict:
        """Step 3: Show available time slots as buttons"""

        flow_data = context['flow_data']

        selected_date_display = flow_data.get('selected_date_display')

        available_slots = flow_data.get('available_slots', [])

        if not available_slots:
            return {
                'message': "Sorry, no time slots available for this date. Please choose another date.",
                'buttons': []
            }


        flow_data['booking_step'] = 'awaiting_time'

        # ✅ Create time slot buttons (max 8 for clean UI)
        time_buttons = [
            slot['start_time']
            for slot in available_slots[:8]
        ]

        # Get appointment type for message
        appointment_type_display = flow_data.get(
            'appointment_type_display',
            'Consultation'
        )

        # Bilingual / templated message
        message = self.get_response(
            'select_time',
            context,
            type=appointment_type_display,
            date=selected_date_display
        )

        return {
            'message': message,
            'buttons': time_buttons
        }

    def _handle_time_selection(self, message: str, context: Dict) -> Dict:
        """Handle user's time slot selection"""

        flow_data = context['flow_data']
        available_slots = flow_data.get('available_slots', [])

        # Try to match the selected time from message
        selected_slot = None
        for slot in available_slots:
            if slot['start_time'] in message:
                selected_slot = slot
                flow_data['selected_time'] = slot['start_time']
                flow_data['selected_slot'] = slot
                break

        if not selected_slot:
            return {
                'message': "I didn't catch that time. Please select one of the time slots above.",
                'buttons': []
            }

        # Check if we have user info
        has_name = 'name' in context['user_info']
        has_email = 'email' in context['user_info']
        has_phone = 'phone' in context['user_info']

        if not has_name:
            flow_data['booking_step'] = 'awaiting_name'
            message = self.get_response('ask_name', context)
            return {'message': message, 'buttons': []}
        elif not has_email:
            flow_data['booking_step'] = 'awaiting_email'
            message = self.get_response('ask_email', context)
            return {'message': message, 'buttons': []}
        elif not has_phone:
            flow_data['booking_step'] = 'awaiting_phone'
            message = self.get_response('ask_phone', context)
            return {'message': message, 'buttons': []}
        else:
            # We have all info, show confirmation
            return self._show_confirmation(context)

    def _show_confirmation(self, context: Dict) -> Dict:
        """Step 4: Show booking confirmation"""

        flow_data = context['flow_data']
        user_info = context['user_info']

        appointment_type = flow_data.get('appointment_type', 'offline')
        appointment_type_display = flow_data.get('appointment_type_display', 'Consultation')
        selected_date_display = flow_data.get('selected_date_display')
        selected_time = flow_data.get('selected_time')
        patient_name = user_info.get('name', 'Unknown')
        patient_email = user_info.get('email', 'Unknown')
        patient_phone = user_info.get('phone', 'Unknown')

        # Update booking step
        flow_data['booking_step'] = 'awaiting_confirmation'

        # Get doctor name
        doctor_name = self.config.config.get('doctors', [{}])[0].get('name', 'Doctor')

        # Get user's location for pricing (default to config's default_location if not set)
        user_location = user_info.get('location', self.config.config['pricing']['default_location'])

        # Get consultation price for user's location
        location_pricing = self.config.get_location_pricing(user_location)
        consultation_price = location_pricing['consultation']['initial']

        # Build location section (only for offline appointments)
        location_section = ""
        if appointment_type == 'offline':
            location = self.config.config['location']
            location_section = f"""📍 **LOCATION**
{location['address']}
{location['area']}, {location['city']}

━━━━━━━━━━━━━━━━━━━━━━

"""

        confirmation_message = f"""{location_section}📋 **APPOINTMENT SUMMARY**

👤 Name: {patient_name}
📧 Email: {patient_email}
📱 Phone: {patient_phone}
👨‍⚕️ Doctor: {doctor_name}
🏥 Type: {appointment_type_display}
📅 Date: {selected_date_display}
⏰ Time: {selected_time}
💰 **Consultation Fee: {consultation_price} {self.config.currency}**

━━━━━━━━━━━━━━━━━━━━━━

**Step 4/4:** Confirm your booking"""

        return {
            'message': confirmation_message,
            'buttons': ['Yes, confirm booking', 'No, cancel']
        }

    def _handle_confirmation(self, message: str, context: Dict) -> Dict:
        """Handle final booking confirmation"""

        message_lower = message.lower()

        # Check if user confirmed
        if 'yes' in message_lower or 'confirm' in message_lower:
            return self._book_appointment_final(context)
        elif 'no' in message_lower or 'cancel' in message_lower:
            self.clear_booking_flow(context)
            return {
                'message': f"No problem! Booking cancelled. Let me know if you'd like to book for a different time.",
                'buttons': []
            }
        else:
            return {
                'message': "Please select 'Yes, confirm booking' or 'No, cancel'",
                'buttons': []
            }

    def _book_appointment_final(self, context: Dict) -> Dict:
        """Actually book the appointment in Google Calendar"""

        flow_data = context['flow_data']
        user_info = context['user_info']

        selected_slot = flow_data.get('selected_slot')
        appointment_type = flow_data.get('appointment_type', 'offline')
        appointment_type_display = flow_data.get('appointment_type_display', 'Consultation')
        patient_name = user_info.get('name')
        patient_email = user_info.get('email')
        patient_phone = user_info.get('phone')

        if not selected_slot or not patient_name or not patient_email or not patient_phone:
            return {
                'message': "Sorry, something went wrong. Missing booking information. Let's start over.",
                'buttons': []
            }

        # Book the appointment via Google Calendar
        calendar_service = get_calendar_service()
        result = calendar_service.book_appointment(
            patient_name=patient_name,
            patient_phone=patient_phone,
            patient_email=patient_email,
            start_datetime=selected_slot['start_datetime'],
            end_datetime=selected_slot['end_datetime'],
            appointment_type='initial',
            notes=f"Booked via chatbot on {datetime.now().strftime('%Y-%m-%d %H:%M')} | Type: {appointment_type_display}"
        )

        # Store booking details in context BEFORE clearing flow
        if result['success']:
            context['last_booking'] = {
                'patient_name': patient_name,
                'appointment_type': appointment_type,
                'appointment_type_display': appointment_type_display,
                'date': flow_data.get('selected_date_display'),
                'time': flow_data.get('selected_time'),
                'email': patient_email,
                'phone': patient_phone,
                'booked_at': datetime.now().isoformat(),
                'zoom_link': result.get('zoom_join_url')
            }

        # Clear booking flow
        self.clear_booking_flow(context)

        if result['success']:
            # Get location from config
            location = self.config.config['location']

            # Build location/video info section
            if appointment_type == 'online':
                # Online consultation - show Zoom link
                location_section = ""
                if result.get('zoom_join_url'):
                    location_section = f"""🎥 **ZOOM MEETING**
━━━━━━━━━━━━━━━━━━━━━━

Join URL: {result['zoom_join_url']}
Meeting ID: {result.get('zoom_meeting_id', 'N/A')}
Password: {result.get('zoom_password', 'No password')}

⚠️ Join link also sent to your email!"""
                else:
                    location_section = f"""🎥 **ONLINE CONSULTATION**
━━━━━━━━━━━━━━━━━━━━━━

Video call link will be sent to your email shortly."""

                reminders = """💡 **Reminders:**
• Check your email for Zoom link
• Test your camera/microphone beforehand
• Have previous lab results ready (digital)
• Ensure stable internet connection
• Join 5 minutes early"""
            else:
                # In-person consultation - show location
                location_section = f"""📍 **LOCATION**
{location['address']}
{location['area']}, {location['city']}"""

                reminders = """💡 **Reminders:**
• Bring previous lab results (if any)
• Arrive 10 minutes early
• Bring your insurance card"""

            success_message = f"""{location_section}

━━━━━━━━━━━━━━━━━━━━━━

✅ **APPOINTMENT BOOKED SUCCESSFULLY!**

👤 Patient: {patient_name}
🏥 Type: {appointment_type_display}
📅 Date: {flow_data.get('selected_date_display')}
⏰ Time: {flow_data.get('selected_time')}

You'll receive a confirmation email shortly.

{reminders}

Looking forward to seeing you! 🌟"""

            return {'message': success_message, 'buttons': []}
        else:
            return {
                'message': f"❌ Booking failed: {result.get('message', 'Unknown error')}\n\nPlease try again or contact us at {self.config.phone}",
                'buttons': []
            }


class PricingAgent(BaseAgent):
    """Handles all pricing and payment queries"""

    def __init__(self, context_manager=None):
        super().__init__("Pricing Agent", context_manager)

    def handle(self, intent: str, message: str, context: Dict) -> str:
        """Handle pricing-related intents with smooth handovers"""

        user_name = self.personalize_greeting(context)

        if intent == 'ask_pricing':
            pricing_text = self.config.get_pricing_text()

            responses = [
                f"{pricing_text}\n\n**Does this work for your budget?** If so, {self.suggest_next_agent('appointment')}",
                f"Here's our transparent pricing! {self.emoji('💰')} {user_name}\n\n{pricing_text}\n\n**Questions about packages to save money?** Or ready to book?",
            ]
            return random.choice(responses)

        elif intent == 'ask_followup_pricing':
            followup_max = self.config.config['appointments'].get('followup_duration_max_minutes', 30)
            return f"Follow-ups are more affordable! {self.emoji('💚')} {user_name}\n\n**Follow-up Visit:**\n• **Price:** {self.config.followup_consultation_price} {self.config.currency}\n• **Duration:** {self.config.followup_duration}-{followup_max} minutes\n• **Includes:** Progress review & plan adjustments\n\n**Why cheaper?** We already know your case!\n\nTypically need 2-4 follow-ups in first 3 months.\n\n**Want to book your initial consultation first?**"

        elif intent == 'ask_packages':
            return f"{self.config.get_packages_text()}\n\n{self.emoji('💡')} **Pro tip:** Packages can save you up to 30%!\n\n**Which package interests you, or shall we start with a single consultation?**"

        elif intent == 'ask_insurance':
            insurance_info = self.config.config['payment']['insurance']
            return f"Good news on insurance! {self.emoji('🏥')} {user_name}\n\n**Insurance:**\n{self.emoji('✅')} Accepted: {'Yes' if insurance_info['accepted'] else 'No'}\n{self.emoji('✅')} Direct billing: {'Available' if insurance_info['direct_billing'] else 'Not available'}\n\n{insurance_info['note']}\n\n{self.emoji('📞')} **Next step:** Call us at {self.config.phone} with your insurance card details, we'll verify coverage before your visit!\n\n**Who's your insurance provider?**"

        elif intent == 'ask_payment_methods':
            methods = self.config.config['payment']['methods']
            methods_text = '\n'.join([f"{self.emoji('✅')} {method}" for method in methods])

            return f"We make payment easy! {self.emoji('💳')} {user_name}\n\n**Accepted Methods:**\n{methods_text}\n\n**Payment timing:** After consultation\n\nNo hidden fees - what you see is what you pay!\n\n**Any other pricing questions, or ready to book?**"

        elif intent == 'ask_lab_cost':
            return f"Let me explain lab test pricing: {self.emoji('🔬')} {user_name}\n\n**Consultation fee ({self.config.initial_consultation_price} {self.config.currency}) includes:**\n{self.emoji('✅')} Doctor's time & assessment\n{self.emoji('✅')} Treatment plan creation\n{self.emoji('✅')} Follow-up support\n\n**Lab tests (separate):** 500-2000 {self.config.currency} depending on what's needed\n\n**Why separate?** Everyone needs different tests! We only order what YOU need - no unnecessary testing.\n\n**Want to know more about specific lab tests?**"

        elif intent == 'ask_treatment_cost':
            return f"Supplements are customized to your needs! {self.emoji('💊')} {user_name}\n\n**Why priced separately:**\n• Everyone's needs differ\n• Quality matters (premium brands only)\n• Sometimes lifestyle changes alone are enough!\n\n**Typical range:** 300-800 {self.config.currency}/month\n\nDoctor recommends only what you truly need - no unnecessary sales!\n\n**Questions about our treatment approach?** {self.suggest_next_agent('treatment')}"

        return f"I can help with pricing! {self.emoji('💰')} {user_name}ask me about:\n• Consultation fees\n• Packages & savings\n• Insurance coverage\n• Payment methods\n\n**What pricing info do you need?**"


class LabTestAgent(BaseAgent):
    """Handles lab test and medical requirement queries"""

    def __init__(self, context_manager=None):
        super().__init__("Lab Test Agent", context_manager)

    def handle(self, intent: str, message: str, context: Dict) -> str:
        """Handle lab test related intents"""

        user_name = self.personalize_greeting(context)

        if intent == 'ask_bring_tests':
            return f"Yes please, {user_name}bring them! {self.emoji('📋')}\n\n**Previous lab tests help us:**\n{self.emoji('✅')} See your health trends over time\n{self.emoji('✅')} Avoid repeating recent tests\n{self.emoji('✅')} Save you money!\n\n**Bring anything from past 6-12 months:**\n• Blood work\n• Imaging reports\n• Specialist reports\n\n{self.emoji('📧')} **Pro tip:** Email them before your visit to {self.config.config['contact']['health_records_email']} - the doctor can review in advance!\n\n**Ready to book your consultation?**"

        elif intent == 'ask_lab_at_clinic':
            onsite = self.config.config['lab_testing']['onsite_blood_draw']
            return f"{'We partner with top labs for your convenience!' if not onsite else 'Yes! We offer on-site testing!'} {self.emoji('🏥')} {user_name}\n\n**Lab Testing Process:**\n{self.emoji('✅')} {'Blood draw at our clinic' if onsite else 'Partner labs nearby'}\n{self.emoji('✅')} Samples sent to certified labs\n{self.emoji('✅')} Results in a few days\n{self.emoji('✅')} Doctor reviews WITH you\n\nEasy, professional, and reliable!\n\n**Any specific tests you're wondering about?**"

        elif intent == 'ask_lab_results_time':
            timing = self.config.lab_results_timing
            return f"Results come pretty quick! {self.emoji('⚡')} {user_name}\n\n**Turnaround Times:**\n• **Standard blood work:** {timing['standard_blood']}\n• **Comprehensive panels:** {timing['comprehensive_panels']}\n• **Functional tests:** {timing['functional_tests']}\n• **Stool/hormone tests:** {timing['stool_hormone']}\n\n{self.emoji('📱')} You'll get notified the moment they're ready!\n\n**The doctor explains everything in your follow-up.** Want to schedule that now?"

        elif intent == 'ask_functional_tests':
            tests = self.config.available_tests
            tests_text = '\n'.join([f"{self.emoji('✅')} {test}" for test in tests[:6]])

            return f"Yes! This is our strength! {self.emoji('🎯')} {user_name}\n\n**Advanced Functional Tests:**\n{tests_text}\n\n**Why these are special:** They dig MUCH deeper than standard tests - finding root causes, not just symptoms!\n\n**Curious about which tests might help YOU?** Book a consultation and the doctor will recommend the perfect panel for your case.\n\n{self.suggest_next_agent('appointment')}"

        return f"I can help with lab testing! {self.emoji('🔬')} {user_name}\n\n**Ask me about:**\n• Required tests\n• On-site testing\n• Results timing\n• Functional/advanced tests\n\n**What would you like to know?**"


class TreatmentAgent(BaseAgent):
    """Handles treatment approach and medical philosophy queries"""

    def __init__(self, context_manager=None):
        super().__init__("Treatment Agent", context_manager)

    def handle(self, intent: str, message: str, context: Dict) -> str:
        """Handle treatment approach intents"""

        user_name = self.personalize_greeting(context)

        if intent == 'ask_functional_medicine':
            clinic_type = self.config.clinic_type.replace('_', ' ').title()
            return f"Great question! {user_name}let me explain {clinic_type}: {self.emoji('🌱')}\n\n**Our Approach:**\n{self.emoji('🔍')} Finds ROOT CAUSE (not just treating symptoms)\n{self.emoji('🧩')} Treats body as connected system\n{self.emoji('⏰')} Takes time to understand YOUR story\n{self.emoji('🎯')} Personalized treatment (not cookie-cutter)\n\n**Example:** If you're tired, we don't just say \"rest more\" - we find WHY you're tired (hormones? gut? stress?) and fix THAT.\n\n**Make sense?** Want to know what conditions we treat?"

        elif intent == 'ask_conditions_treated':
            specialties_text = self.config.get_specialties_text()
            return f"{specialties_text}\n\n{self.emoji('💡')} **Remember:** If it's chronic and you're not getting answers elsewhere, we can probably help!\n\n**See your condition on the list?** {self.suggest_next_agent('appointment')}"

        elif intent == 'ask_treatment_methods':
            return f"Dr. Rania Said's approach is highly focused on nutrition, gut health, and lifestyle changes - the root causes! {self.emoji('🍎')} {user_name}\n\n**Our Food-First Philosophy:**\n{self.emoji('✅')} Personalized dietary plans tailored to your child's needs\n{self.emoji('✅')} Targeted nutritional supplements (safe for children)\n{self.emoji('✅')} Gut healing protocols\n{self.emoji('✅')} Food sensitivity identification\n{self.emoji('✅')} Lifestyle modifications (sleep, stress, exercise)\n{self.emoji('✅')} Medication when necessary (avoiding when possible)\n\n**Why nutrition first?**\nFood is medicine! Many chronic conditions in children stem from nutritional imbalances, gut issues, or food sensitivities. Dr. Rania Said helps heal from the inside out.\n\n**What specific health concern are you addressing?**"

        elif intent == 'ask_specialist_coordination':
            return f"Absolutely! {user_name}we love working as a team! {self.emoji('🤝')}\n\n**How We Coordinate:**\n{self.emoji('✅')} Communicate with your specialists\n{self.emoji('✅')} Share relevant findings\n{self.emoji('✅')} Ensure treatments don't conflict\n{self.emoji('✅')} Refer when needed\n\n**YOU'RE the center** - we're all supporting you together.\n\nBest outcomes happen through collaboration!\n\n**Already seeing specialists?** Bring their reports to your first visit!"

        return f"I can explain our treatment approach! {self.emoji('🩺')} {user_name}\n\n**Ask me about:**\n• Our medical philosophy\n• Conditions we treat\n• Treatment methods\n• Working with specialists\n\n**What interests you most?**"


class SupportAgent(BaseAgent):
    """Handles communication and support queries"""

    def __init__(self, context_manager=None):
        super().__init__("Support Agent", context_manager)

    def handle(self, intent: str, message: str, context: Dict) -> str:
        """Handle support and communication intents"""

        user_name = self.personalize_greeting(context)

        if intent == 'ask_contact':
            contact_text = self.config.get_contact_text()
            return f"{contact_text}\n\n**Prefer WhatsApp?** {self.emoji('💬')} Most patients find it the easiest way to reach us!\n\n**How would you like to get in touch?**"

        elif intent == 'ask_whatsapp':
            response_time = self.config.config['communication']['response_time_hours']
            return f"Yes! {user_name}WhatsApp is our favorite way to help you! {self.emoji('💬')}\n\n**WhatsApp:** {self.config.whatsapp}\n\n**You can:**\n{self.emoji('✅')} Book appointments\n{self.emoji('✅')} Send lab results\n{self.emoji('✅')} Ask quick questions\n{self.emoji('✅')} Get appointment reminders\n\n**Response time:** Usually within {response_time}\n\n{self.emoji('⚠️')} **Not for emergencies** - call {self.config.phone} instead!\n\n{self.emoji('📲')} **Save our number now!** Have a question to test it out?"

        elif intent == 'ask_location':
            location = self.config.config['location']

            # Log location access
            print(f"\n{'='*60}")
            print(f"LOCATION ACCESSED - INFO REQUEST")
            print(f"User: {context['user_info'].get('name', 'Unknown')}")
            print(f"Location: {location['address']}")
            print(f"City: {location['city']}, Area: {location['area']}")
            print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")

            return f"""📍 **LOCATION**
{location['address']}
{location['area']}, {location['city']}

━━━━━━━━━━━━━━━━━━━━━━

{self.emoji('🏥')} **{self.config.clinic_name}**

{self.emoji('⏰')} **Hours:**
{self.config.hours_display}

{self.emoji('🚗')} {'Parking available on-site' if location.get('parking') else 'Street parking available'}
{self.emoji('🚇')} Metro: {location.get('metro_station', 'N/A')}

**Need directions?** Call {self.config.phone} and we'll guide you!

**Ready to visit us?** {self.suggest_next_agent('appointment')}"""

        elif intent == 'ask_doctors':
            # Get doctor info from config
            doctor = self.config.config['doctors'][0]
            specialties_text = '\n'.join([f"• {specialty}" for specialty in doctor['specialties'][:4]])
            locations = ' – '.join(doctor.get('locations', ['Dubai']))

            return f"""{self.emoji('👩‍⚕️')} **{doctor['full_name']}**
{doctor['title']}

**Locations:** {locations}

**Specializes in:**
{specialties_text}

**Fees:** Initial {self.config.initial_consultation_price} {self.config.currency} | Follow-up {self.config.followup_consultation_price} {self.config.currency}

**Available:** {self.config.hours_display}

{self.emoji('📞')} Ready to book?"""

        return f"I'm here to help! {self.emoji('💬')} {user_name}\n\n**Ask me about:**\n• Contact information\n• WhatsApp support\n• Our location\n• How to reach us\n\n**What do you need?**"


class GeneralAgent(BaseAgent):
    """Handles general queries with smart fallback and keyword detection"""

    def __init__(self, context_manager=None):
        super().__init__("General Agent", context_manager)

    def handle(self, intent: str, message: str, context: Dict):
        """Handle general intents with smart routing

        Returns: str or Dict with 'message' and 'buttons' for interactive responses
        """

        user_name = context['user_info'].get('name', 'there')
        user_greeting = self.personalize_greeting(context)

        if intent == 'greet':
            # Extract name from greeting if present
            excluded_greetings = ['hello', 'hi', 'hey', 'greetings', 'good', 'morning', 'afternoon', 'evening']

            name_patterns = [
                r"(?:my name is|i'm|i am|this is)\s+([A-Z][a-z]+)",
                r"^([A-Z][a-z]+)\s+here",
            ]

            for pattern in name_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    extracted_name = match.group(1)

                    # Skip if it's a common greeting
                    if extracted_name.lower() not in excluded_greetings:
                        context['user_info']['name'] = extracted_name
                        user_name = extracted_name
                        user_greeting = f"{user_name}, "

            # Use bilingual greeting
            return self.get_response('greeting', context, clinic_name=self.config.clinic_name)

        elif intent == 'goodbye':
            responses = [
                f"Thank you! {self.emoji('👋')} Call us anytime: {self.config.phone}",
                f"Take care! {self.emoji('😊')} We're here when you need us.",
                f"Goodbye! {self.emoji('🙏')} Stay healthy!",
            ]
            return random.choice(responses)

        elif intent == 'bot_challenge':
            return f"I'm an AI assistant for {self.config.clinic_name}! {self.emoji('🤖')} {user_greeting}\n\nI can answer questions about appointments, pricing, treatments, and more.\n\n**For personalized medical advice**, our doctors are here during consultations!\n\n**What would you like to know?**"

        elif intent == 'affirm':
            # Context-aware affirmation handling
            last_intent = context.get('last_intent')
            last_agent = context.get('last_agent')
            last_response = context.get('last_response', '')

            # Check if last response was about booking (keyword-based fallback)
            booking_keywords = ['book', 'appointment', 'schedule', 'available', 'working hours', 'availability']
            is_booking_context = any(keyword in last_response.lower() for keyword in booking_keywords)

            # If user was just asked about online consultation or booking
            if last_intent in ['ask_online_consultation', 'ask_hours', 'book_appointment'] or is_booking_context:
                # Set booking flow
                self.set_booking_flow(context)

                # Update booking step to await appointment type
                context['flow_data']['booking_step'] = 'awaiting_appointment_type'

                # Show appointment type options (online/offline) - bilingual
                message = self.get_response('book_appointment', context)
                online_btn = self.get_response('online_button', context)
                offline_btn = self.get_response('offline_button', context)

                return {
                    'message': message,
                    'buttons': [online_btn, offline_btn]
                }

            # If user was asked about pricing/packages
            elif last_intent in ['ask_pricing', 'ask_packages']:
                return f"Wonderful! {self.emoji('✨')} Ready to move forward?\n\nWould you like to:\n{self.emoji('📅')} **Book an appointment now**\n{self.emoji('❓')} **Ask more questions**\n{self.emoji('📞')} **Speak with our team**: {self.config.phone}\n\n**What works best for you?**"

            # Generic affirmation
            else:
                return f"Great! {self.emoji('😊')} {user_greeting}\n\nHow can I help you further?\n\n{self.emoji('📅')} Book an appointment\n{self.emoji('💰')} Learn about pricing\n{self.emoji('🔬')} Ask about lab tests\n{self.emoji('💬')} Contact information\n\n**What would you like to know?**"

        elif intent == 'deny':
            # Context-aware denial handling
            last_intent = context.get('last_intent')

            return f"No problem! {self.emoji('😊')} {user_greeting}\n\n**Is there something else I can help you with?**\n\n{self.emoji('❓')} Have questions about our services?\n{self.emoji('📞')} Need contact information?\n{self.emoji('💬')} Want to discuss something specific?\n\n**What would you like to know?**"

        elif intent == 'ask_age_groups':
            return f"Yes! {user_greeting}Dr. Rania Said is a board-certified Pediatrician, Functional Medicine Specialist, and Clinical Nutritionist! {self.emoji('👧')}\n\n**She sees children from:**\n{self.emoji('✅')} Newborns all the way up to adolescents\n{self.emoji('✅')} Adults with metabolic and nutritional concerns\n\n**Dr. Rania Said specializes in:**\n• Pediatric functional medicine\n• Clinical nutrition & pediatric nutrition\n• Diabetes & hypertension in children\n• Weight management for kids\n• Food sensitivities & allergies\n\n**How old is your child?**"

        elif intent == 'unknown':
            # Smart fallback with keyword detection
            return self._handle_unknown_intent(message, user_greeting)

        return f"I'm here to help! {self.emoji('😊')}\n\nAsk me about:\n• Appointments\n• Pricing\n• Lab tests\n• Treatments\n\nWhat do you need?"

    def _handle_unknown_intent(self, message: str, user_greeting: str) -> str:
        """Smart fallback with keyword detection and routing suggestions"""

        message_lower = message.lower()

        # Detect common off-topic patterns and refuse immediately
        off_topic_patterns = [
            # General knowledge
            ['weather', 'forecast', 'temperature', 'rain', 'sunny'],
            ['news', 'current events', 'politics', 'president', 'election'],
            ['sports', 'game', 'score', 'team', 'player'],
            ['movie', 'film', 'actor', 'actress', 'cinema'],
            ['music', 'song', 'singer', 'album', 'concert'],
            # Random requests
            ['joke', 'funny', 'laugh', 'humor'],
            ['recipe', 'cooking', 'food', 'restaurant'],
            ['travel', 'flight', 'hotel', 'vacation', 'trip'],
            ['shopping', 'buy', 'product', 'store'] if not any(w in message_lower for w in ['appointment', 'package', 'consultation']) else [],
            # Math/calculations (unless it's about pricing)
            ['calculate', 'math', 'equation'] if not any(w in message_lower for w in ['cost', 'price', 'fee']) else [],
        ]

        for pattern_words in off_topic_patterns:
            if pattern_words and any(word in message_lower for word in pattern_words):
                message_preview = message[:50] + "..." if len(message) > 50 else message
                return f"""{self.emoji('🚫')} I apologize, {user_greeting}but I cannot help with that.

I'm an AI assistant specifically for **{self.config.clinic_name}** and can **only** answer questions about our healthcare services.

Your question "{message_preview}" appears to be outside my scope.

**I can help you with:**
{self.emoji('📅')} Booking appointments
{self.emoji('💰')} Pricing and insurance
{self.emoji('🔬')} Lab tests and results
{self.emoji('🩺')} Treatment options
{self.emoji('💬')} Contacting the clinic

**What healthcare topic can I assist you with?**"""

        # Healthcare-related keyword detection (original routing logic)
        if any(word in message_lower for word in ['cost', 'price', 'fee', 'pay', 'money', 'expensive', 'cheap', 'afford']):
            return f"I see you're asking about **pricing**! {self.emoji('💰')} {user_greeting}\n\nAre you wondering about:\n• **Initial consultation fees**?\n• **Follow-up visit costs**?\n• **Lab test pricing**?\n• **Package deals**?\n\n**Which one interests you?**"

        if any(word in message_lower for word in ['book', 'appointment', 'schedule', 'visit', 'time', 'date', 'available', 'slot', 'consult', 'consultation', 'see doctor', 'meet']):
            return f"Looking to **book an appointment**? {self.emoji('📅')} {user_greeting}\n\nI can help with that! Would you like to know:\n• **Our working hours**?\n• **How to book**?\n• **Current availability**?\n\n**Or shall I start the booking process right away?**"

        if any(word in message_lower for word in ['test', 'lab', 'blood', 'result', 'screening', 'analysis']):
            return f"You're asking about **lab tests**! {self.emoji('🔬')} {user_greeting}\n\nI can explain:\n• **What tests we offer**\n• **How to get tested**\n• **When you get results**\n• **Pricing for tests**\n\n**What would you like to know?**"

        if any(word in message_lower for word in ['treat', 'help', 'cure', 'fix', 'condition', 'disease', 'illness', 'problem']):
            return f"Asking about **treatment**? {self.emoji('🩺')} {user_greeting}\n\nI can tell you about:\n• **What conditions we treat**\n• **Our treatment approach**\n• **How we can help**\n\n**What brings you in? What are you dealing with?**"

        if any(word in message_lower for word in ['where', 'location', 'address', 'directions', 'find']):
            return f"Looking for our **location**? {self.emoji('📍')} {user_greeting}\n\n{self.config.config['location']['address']}\n\n**Need directions or parking info?**"

        if any(word in message_lower for word in ['call', 'phone', 'contact', 'reach', 'whatsapp', 'email']):
            return f"Want to **contact us**? {self.emoji('📞')} {user_greeting}\n\n• Phone: {self.config.phone}\n• WhatsApp: {self.config.whatsapp}\n• Email: {self.config.email}\n\n**Which method works best for you?**"

        if any(word in message_lower for word in ['clinic name', 'name of clinic', 'what is the name', 'your name', 'called']):
            return f"We are **{self.config.clinic_name}**! {self.emoji('🏥')}\n\nHow can I help you today?"

        # True fallback - off-topic query detected
        return f"""I can help with clinic questions only:

{self.emoji('📅')} Appointments & hours
{self.emoji('💰')} Pricing & insurance
{self.emoji('🔬')} Lab tests
{self.emoji('🩺')} Treatments
{self.emoji('💬')} Contact info

What would you like to know?"""


class AgentRouter:
    """Routes intents to appropriate specialized agents with context awareness"""

    def __init__(self):
        # Initialize context manager first
        self.context_manager = ConversationContext()

        # Initialize agents and pass context_manager to each
        self.agents = {
            'appointment': AppointmentAgent(self.context_manager),
            'pricing': PricingAgent(self.context_manager),
            'lab_test': LabTestAgent(self.context_manager),
            'treatment': TreatmentAgent(self.context_manager),
            'support': SupportAgent(self.context_manager),
            'general': GeneralAgent(self.context_manager),
        }

        # Map intents to agents
        self.intent_routing = {
            # Appointment intents
            'ask_hours': 'appointment',
            'book_appointment': 'appointment',
            'inform': 'appointment',  # User providing booking details
            'ask_online_consultation': 'appointment',
            'ask_virtual_consult': 'appointment',
            'ask_waiting_time': 'appointment',
            'ask_walk_in': 'appointment',
            'ask_consultation_duration': 'appointment',
            'ask_cancellation_policy': 'appointment',
            'ask_reschedule': 'appointment',

            # Pricing intents
            'ask_pricing': 'pricing',
            'ask_followup_pricing': 'pricing',
            'ask_packages': 'pricing',
            'ask_insurance': 'pricing',
            'ask_payment_methods': 'pricing',
            'ask_lab_cost': 'pricing',
            'ask_treatment_cost': 'pricing',

            # Lab test intents
            'ask_bring_tests': 'lab_test',
            'ask_tests_needed': 'lab_test',
            'ask_lab_at_clinic': 'lab_test',
            'ask_lab_results_time': 'lab_test',
            'ask_test_guidance': 'lab_test',
            'ask_repeat_tests': 'lab_test',
            'ask_functional_tests': 'lab_test',

            # Treatment intents
            'ask_functional_medicine': 'treatment',
            'ask_conditions_treated': 'treatment',
            'ask_treatment_methods': 'treatment',
            'ask_improvement_time': 'treatment',
            'ask_followup_frequency': 'treatment',
            'ask_specialist_coordination': 'treatment',

            # Support intents
            'ask_contact': 'support',
            'ask_whatsapp': 'support',
            'ask_send_results': 'support',
            'ask_doctor_followup': 'support',
            'ask_followup_cost': 'support',
            'ask_urgent_questions': 'support',
            'ask_location': 'support',
            'ask_doctors': 'support',

            # General intents
            'greet': 'general',
            'goodbye': 'general',
            'bot_challenge': 'general',
            'affirm': 'general',  # Context-aware yes/confirmation
            'deny': 'general',    # Context-aware no/rejection
            'ask_age_groups': 'general',
            'ask_chronic_conditions': 'general',
            'ask_health_plans': 'general',
            'ask_specific_conditions': 'general',
        }

    def route(self, intent: str, message: str, sender_id: str) -> Dict:
        """Route intent to appropriate agent and get response"""
        context = self.context_manager.get_context(sender_id)
        agent_name = self.intent_routing.get(intent, 'general')
        agent = self.agents[agent_name]

        response = agent.handle(intent, message, context)

        # Handle Dict response from AppointmentAgent or string response from other agents
        if isinstance(response, dict):
            response_text = response.get('message', '')
            buttons = response.get('buttons', [])
        else:
            response_text = response
            buttons = []

        self.context_manager.update_context(sender_id, agent_name, intent, message, response_text)

        return {
            'response': response_text,
            'buttons': buttons,
            'agent': agent_name,
            'intent': intent,
            'confidence': 'high'
        }

    def get_fallback_response(self, message: str, sender_id: str) -> str:
        """Handle messages that don't match any intent using smart fallback"""
        context = self.context_manager.get_context(sender_id)
        return self.agents['general'].handle('unknown', message, context)
