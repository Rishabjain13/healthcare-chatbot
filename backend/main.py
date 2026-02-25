"""
FastAPI Backend for Healthcare Chatbot
Multi-Agent System with Google Calendar Integration
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import requests
from openai import OpenAI
from twilio.rest import Client

from config_loader import get_config
from google_calendar_service import get_calendar_service
from agents import AgentRouter
from location_service import get_location_service

# Load environment variables
load_dotenv()

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    import time

    print('\n' + '=' * 70)
    print(f'🚀 Healthcare Chatbot API v2.0')
    print('=' * 70)
    print(f'📡 Server: http://localhost:{int(os.getenv("PORT", "3000"))}')
    print(f'📊 RASA: {os.getenv("RASA_URL", "http://localhost:5005")}')
    print('=' * 70 + '\n')

    yield

    # Shutdown
    print("Shutting down...")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Healthcare Chatbot API",
    description="General-purpose healthcare chatbot with appointment booking",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
config = get_config()
calendar_service = get_calendar_service()
location_service = get_location_service()

# Environment variables
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER')
RASA_URL = os.getenv('RASA_URL', 'http://localhost:5005')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
# Set to 90% - only route to agents if Rasa is very confident
# Lower confidence uses OpenAI with conversation history for better context
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.90'))
PORT = int(os.getenv('PORT', '3000'))

# Initialize clients
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None
agent_router = AgentRouter()

# Initialize OpenAI
openai_client = None
if OPENAI_API_KEY and OPENAI_API_KEY != 'your_openai_key_here':
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI configured")
    except Exception as e:
        print(f"⚠️  OpenAI not configured: {e}")
        openai_client = None

# In-memory conversation storage
conversations = {}


# Pydantic models
class ChatMessage(BaseModel):
    message: str
    sender: str = "test_user"
    name: str = "Test User"


class AppointmentBooking(BaseModel):
    patient_name: str
    patient_phone: str
    patient_email: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    appointment_type: str = "initial"
    notes: str = ""


class AvailabilityQuery(BaseModel):
    date: str  # YYYY-MM-DD
    appointment_type: str = "initial"


# Helper functions
def get_rasa_response(message: str, sender: str) -> Dict:
    """Get ONLY intent classification from RASA (no state management)

    IMPORTANT: We only use /model/parse endpoint (stateless intent classification).
    We do NOT use /webhooks/rest/webhook to avoid Rasa state conflicts with backend agents.
    """
    try:
        print(f"   → Asking RASA for intent classification...")

        # ONLY use /model/parse for stateless intent classification
        parse_response = requests.post(
            f"{RASA_URL}/model/parse",
            json={"text": message},
            timeout=5
        )
        parse_data = parse_response.json()

        intent_data = parse_data.get('intent', {})
        intent_name = intent_data.get('name', 'unknown')
        confidence = intent_data.get('confidence', 0)
        entities = parse_data.get('entities', [])

        print(f"   ✅ Intent: {intent_name} (confidence: {confidence:.2f})")

        # NOTE: We deliberately DO NOT call /webhooks/rest/webhook here
        # Reason: Webhook activates Rasa's state management (forms, rules, tracker)
        # which conflicts with our backend agent system. Backend agents now manage
        # all conversation state and context.

        return {
            'intent': intent_name,
            'confidence': confidence,
            'entities': entities,
        }

    except Exception as e:
        print(f"   ❌ RASA error: {str(e)}")
        return {
            'intent': 'unknown',
            'confidence': 0,
            'entities': [],
        }


def get_intent_from_rasa(message: str, sender: str) -> Dict:
    """Get intent classification from RASA (backward compatibility)"""
    result = get_rasa_response(message, sender)
    return {
        'intent': result['intent'],
        'confidence': result['confidence'],
        'entities': result['entities']
    }


def extract_buttons_from_rasa(rasa_responses: List[Dict]) -> List[str]:
    """Extract button titles from Rasa responses"""
    buttons = []
    for response in rasa_responses:
        if 'buttons' in response and isinstance(response['buttons'], list):
            for button in response['buttons']:
                if 'title' in button:
                    buttons.append(button['title'])
    return buttons


def ask_openai(message: str, sender: str, context: Dict) -> str:
    """Send message to OpenAI with full conversation history for context-aware responses"""
    try:
        if not openai_client:
            print(f"   ⚠️  OpenAI not configured")
            return None

        print(f"   → Asking OpenAI with conversation history...")

        # Build conversation history for OpenAI
        messages = []

        # System prompt with clinic info and safety guidelines
        current_flow = context.get('current_flow', 'general conversation')
        user_info = context.get('user_info', {})
        collected_info = ', '.join([f"{k}: {v}" for k, v in user_info.items()]) if user_info else 'none yet'

        system_prompt = f"""You are a helpful medical assistant for {config.clinic_name}.

DOCTOR INFORMATION:
- Our doctor is Dr. Rania Said, MD - Pediatrician, Functional Medicine Specialist, and Clinical Nutritionist
- Certified in Functional Medicine – IFM (Institute for Functional Medicine)
- She specializes in: pediatric nutrition, clinical nutrition, digestive health, hormonal imbalances, chronic fatigue, autoimmune conditions, metabolic health
- She speaks English and Arabic
- Locations: Cairo – Dubai
- Her approach: root cause analysis and personalized treatment plans

CONSULTATION OPTIONS:
- IN-PERSON: At our clinic in {config.area}, {config.city}
- ONLINE: Via Zoom video call (same pricing, convenient for anyone worldwide)
- We offer both in-person and online consultations at your preferred time

IMPORTANT SAFETY GUIDELINES:
- Help with appointments, pricing, lab tests, and clinic information
- Answer health questions (never diagnose, always recommend seeing Dr. Rania Said)
- Respond in the SAME language as the patient
- Be empathetic, professional, and concise
- NEVER hallucinate or confirm appointment bookings
- If asked to book, collect: name, email, phone, preferred date/time, consultation type (in-person or online)
- DO NOT say "appointment confirmed" unless you actually booked it via API

CLINIC INFO:
- Hours: {config.hours_display}
- Location: {config.area}, {config.city}
- Initial Consultation: {config.initial_consultation_price} {config.currency}
- Follow-up: {config.followup_consultation_price} {config.currency}
- Phone: {config.phone}
- WhatsApp: {config.whatsapp}

CURRENT CONVERSATION STATE:
- Flow: {current_flow}
- User info collected: {collected_info}

If in booking flow, help collect missing information naturally in conversation, one piece at a time."""

        messages.append({"role": "system", "content": system_prompt})

        # Add conversation history (last 15 messages for context)
        history = context.get('history', [])[-15:]
        for turn in history:
            messages.append({
                "role": "user",
                "content": turn['user_message']
            })
            if turn.get('bot_response'):
                messages.append({
                    "role": "assistant",
                    "content": turn['bot_response']
                })

        # Add current message
        messages.append({"role": "user", "content": message})

        # 🔍 LOG OPENAI REQUEST
        print(f"\n📤 SENDING TO OPENAI:")
        print(f"   └─ System Prompt: {len(system_prompt)} chars")
        print(f"   └─ Conversation History: {len(history)} messages")
        print(f"   └─ Total Context: {len(messages)} messages")
        print(f"   └─ Current Flow: {current_flow}")
        print(f"   └─ User Info: {collected_info}")

        # Call OpenAI with GPT-4
        completion = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )

        reply = completion.choices[0].message.content

        print(f"\n📥 OPENAI RESPONSE:")
        print(f"   └─ Generated: {len(reply)} chars")
        print(f"   └─ Model: gpt-4")
        print(f"   ✅ OpenAI response generated ({len(history)} messages in context)")

        return reply

    except Exception as e:
        print(f"   ❌ OpenAI error: {str(e)}")
        return None

    # Original implementation removed - replaced with history-aware version above
    # try:
    #     if not openai_client:
    #         return "I can help with specific questions about the clinic. Try asking about hours, pricing, or services!"
    #
    #     print(f"   → Asking OpenAI...")
    #
    #     if sender not in conversations:
    #         conversations[sender] = []
    #
    #     # Build system prompt from config
    #     system_prompt = f"""You are a helpful medical assistant for {config.clinic_name}.
    # - Help with appointments ({config.hours_display})
    # - Answer health questions (never diagnose, always recommend seeing a doctor)
    # - Respond in the SAME language as the patient (English or Arabic)
    # - Be empathetic, professional, and concise
    # - Consultation fees: Initial {config.initial_consultation_price} {config.currency}, Follow-up {config.followup_consultation_price} {config.currency}, Emergency {config.emergency_consultation_price} {config.currency}
    # - Location: {config.area}, {config.city}"""
    #
    #     messages = [
    #         {"role": "system", "content": system_prompt},
    #         *conversations[sender],
    #         {"role": "user", "content": message}
    #     ]
    #
    #     completion = openai_client.chat.completions.create(
    #         model="gpt-4",
    #         messages=messages,
    #         max_tokens=200,
    #         temperature=0.7
    #     )
    #
    #     reply = completion.choices[0].message.content
    #
    #     conversations[sender].append({"role": "user", "content": message})
    #     conversations[sender].append({"role": "assistant", "content": reply})
    #
    #     if len(conversations[sender]) > 20:
    #         conversations[sender] = conversations[sender][-20:]
    #
    #     return reply
    #
    # except Exception as e:
    #     print(f"   ❌ OpenAI error: {str(e)}")
    #     return "I'm having trouble processing that. Please try again."


def get_reply(message: str, sender: str, name: str) -> Dict:
    """Main logic: RASA intent classification → Backend Agent (with context)"""
    print(f"\n{'=' * 70}")
    print(f"📨 From: {name} ({sender})")
    print(f"💬 Message: \"{message}\"")

    # Get intent from RASA (stateless classification only)
    rasa_result = get_rasa_response(message, sender)
    intent = rasa_result['intent']
    confidence = rasa_result['confidence']
    entities = rasa_result.get('entities', [])

    # Get conversation context (backend manages all state)
    context = agent_router.context_manager.get_context(sender)

    # 🔍 LOG CONVERSATION HISTORY AND STATE
    print(f"\n📊 CONTEXT DEBUG:")
    print(f"   └─ Session ID: {sender}")
    print(f"   └─ Current Flow: {context.get('current_flow', 'None')}")
    print(f"   └─ Flow Step: {context.get('flow_data', {}).get('booking_step', 'N/A')}")
    print(f"   └─ User Info Collected: {list(context.get('user_info', {}).keys())}")
    print(f"   └─ History Length: {len(context.get('history', []))} messages")

    if context.get('history'):
        print(f"   └─ Last 3 conversation turns:")
        for i, turn in enumerate(context['history'][-3:], 1):
            user_msg = turn['user_message'][:60]
            bot_msg = turn.get('bot_response', '')[:60]
            print(f"      {i}. User: {user_msg}...")
            if bot_msg:
                print(f"         Bot:  {bot_msg}...")

    print(f"\n🎯 RASA CLASSIFICATION:")
    print(f"   └─ Intent: {intent}")
    print(f"   └─ Confidence: {confidence * 100:.1f}%")
    print(f"   └─ Entities: {entities if entities else 'None'}")
    print(f"{'=' * 70}\n")

    # ============================================================================
    # ROUTING DECISION - SMART FLOW MANAGEMENT
    # ============================================================================

    # PRIORITY 1: Active Flow with Smart Side-Question Handling
    # If user is in a conversation flow (booking, etc.), intelligently handle:
    # - High confidence questions (90%+) about different topics → Answer but KEEP flow
    # - Low confidence messages → Continue flow (probably booking info)
    current_flow = context.get('current_flow')

    if current_flow:
        print(f"🔄 ACTIVE FLOW DETECTED: '{current_flow}'")

        # Map flows to their handling agents
        flow_agents = {
            'booking': 'book_appointment',
            # Future flows can be added here:
            # 'lab_inquiry': 'ask_bring_tests',
            # 'pricing_inquiry': 'ask_pricing',
        }

        flow_intent = flow_agents.get(current_flow, 'book_appointment')

        # Smart detection: Is this a side question or flow continuation?
        # Only specific informational intents are "side questions"
        # Generic intents (inform, affirm, deny) should continue the flow
        side_question_intents = {
            'ask_hours', 'ask_pricing', 'ask_doctors', 'ask_location',
            'ask_bring_tests', 'ask_online_consultation', 'ask_services',
            'ask_insurance', 'ask_parking', 'ask_languages'
        }

        if (confidence >= CONFIDENCE_THRESHOLD and
            intent in side_question_intents and
            intent != flow_intent):
            # HIGH confidence for INFORMATIONAL intent = Side question during flow
            print(f"   💡 SIDE QUESTION detected (confidence: {confidence * 100:.1f}%)")
            print(f"   └─ Answering '{intent}' question while MAINTAINING '{current_flow}' flow")

            agent_result = agent_router.route(intent, message, sender)

            # Add context reminder to help user continue flow after answer
            flow_reminder = "\n\n📝 Ready to continue booking when you are!"
            enhanced_response = agent_result['response'] + flow_reminder

            # IMPORTANT: Flow remains active - don't clear it
            print(f"   ✅ Side question answered, flow '{current_flow}' still active")

            return {
                'reply': enhanced_response,
                'handler': f"Agent ({agent_result['agent']}) - side question in {current_flow} flow",
                'intent': intent,
                'confidence': confidence,
                'buttons': agent_result.get('buttons', [])
            }
        else:
            # Low confidence or same intent = Continue flow
            print(f"   └─ Continuing '{current_flow}' flow (confidence: {confidence * 100:.1f}%)")
            agent_result = agent_router.route(flow_intent, message, sender)

            if agent_result.get('buttons'):
                print(f"   🔘 Buttons provided: {len(agent_result['buttons'])} options")

            return {
                'reply': agent_result['response'],
                'handler': f"Agent ({agent_result['agent']}) - {current_flow} flow",
                'intent': flow_intent,
                'confidence': confidence,
                'buttons': agent_result.get('buttons', [])
            }

    # PRIORITY 2: High Confidence Intent Classification
    # If no active flow, use specialized agents for high-confidence intents
    elif confidence >= CONFIDENCE_THRESHOLD and intent != 'unknown':
        print(f"✅ High confidence ({confidence * 100:.1f}%) - Routing to specialized agent")
        agent_result = agent_router.route(intent, message, sender)

        print(f"   🤖 Agent: {agent_result['agent'].upper()}")
        print(f"   ✅ Response generated")
        if agent_result.get('buttons'):
            print(f"   🔘 Buttons: {agent_result['buttons']}")

        return {
            'reply': agent_result['response'],
            'handler': f"Agent ({agent_result['agent']})",
            'intent': intent,
            'confidence': confidence,
            'buttons': agent_result.get('buttons', [])
        }

    # PRIORITY 3: OpenAI with Conversation History
    # For ambiguous messages, use OpenAI with full context
    else:
        print(f"🤖 Low confidence ({confidence * 100:.1f}%) - Using OpenAI with conversation history")
        print(f"   └─ Passing {len(context.get('history', []))} messages for context")

        openai_response = ask_openai(message, sender, context)

        if openai_response:
            # Update context with OpenAI response
            agent_router.context_manager.update_context(
                sender, 'openai', intent, message, openai_response
            )
            print(f"   ✅ OpenAI generated context-aware response")

            return {
                'reply': openai_response,
                'handler': 'OpenAI (History-aware)',
                'intent': intent,
                'confidence': confidence,
                'buttons': []
            }

        # PRIORITY 4: General Agent Fallback
        # Ultimate fallback if OpenAI unavailable
        print(f"⚠️  OpenAI unavailable - using general agent fallback")
        fallback_response = agent_router.get_fallback_response(message, sender)

        return {
            'reply': fallback_response,
            'handler': 'General Agent (Fallback)',
            'intent': intent,
            'confidence': confidence,
            'buttons': []
        }


# API Routes
@app.get("/")
async def home():
    """Home endpoint with API info"""
    return {
        "service": "Healthcare Chatbot API",
        "version": "2.0.0",
        "clinic": config.clinic_name,
        "status": "Running",
        "features": [
            "Multi-channel messaging (SMS, WhatsApp)",
            "Multi-agent NLU system",
            "Google Calendar appointment booking",
            "Configurable for any healthcare business"
        ],
        "endpoints": {
            "health": "/health",
            "chat": "/chat (POST)",
            "appointments": "/appointments",
            "sms_webhook": "/sms/webhook (POST)",
            "whatsapp_webhook": "/whatsapp/webhook (POST)"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "clinic": config.clinic_name,
        "rasa_url": RASA_URL,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "google_calendar_enabled": config.google_calendar_enabled,
        "openai_enabled": openai_client is not None
    }


@app.post("/chat")
async def chat(chat_message: ChatMessage):
    """Chat endpoint for testing"""
    try:
        print(f"\n{'🔵 CHAT REQUEST RECEIVED ' + '=' * 50}")
        print(f"⏰ Timestamp: {datetime.now().isoformat()}")
        print(f"👤 Sender: {chat_message.sender}")
        print(f"📛 Name: {chat_message.name}")
        print(f"💬 Message: \"{chat_message.message}\"")
        print(f"{'=' * 70}")

        result = get_reply(
            chat_message.message,
            chat_message.sender,
            chat_message.name
        )

        print(f"\n{'✅ CHAT RESPONSE SENT ' + '=' * 50}")
        print(f"🤖 Handler: {result['handler']}")
        print(f"🎯 Intent: {result['intent']}")
        print(f"📊 Confidence: {result['confidence']:.2%}")
        print(f"💭 Reply Preview: {result['reply'][:100]}...")
        print(f"{'=' * 70}\n")

        return {
            "success": True,
            "message": chat_message.message,
            "reply": result['reply'],
            "handler": result['handler'],
            "intent": result['intent'],
            "confidence": result['confidence'],
            "buttons": result.get('buttons', [])
        }

    except Exception as e:
        print(f"\n{'❌ CHAT ERROR ' + '=' * 50}")
        print(f"⏰ Timestamp: {datetime.now().isoformat()}")
        print(f"❗ Error: {str(e)}")
        print(f"{'=' * 70}\n")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sms/webhook")
async def sms_webhook(
    From: str = Form(...),
    Body: str = Form(...)
):
    """Handle incoming SMS messages from Twilio"""
    try:
        print(f"\n📱 SMS received from: {From}")
        print(f"📝 Message: {Body}")

        result = get_reply(Body, From, 'SMS User')

        if twilio_client:
            twilio_client.messages.create(
                from_=TWILIO_PHONE_NUMBER,
                to=From,
                body=result['reply']
            )

        return Response(content="", status_code=200)

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/whatsapp/webhook")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(default=''),
    ProfileName: str = Form(default='User'),
    # Location parameters from Twilio
    Latitude: Optional[str] = Form(default=None),
    Longitude: Optional[str] = Form(default=None),
    Address: Optional[str] = Form(default=None)
):
    """Handle incoming WhatsApp messages from Twilio (text and location)"""
    try:
        from_number = From.replace('whatsapp:', '')

        # Check if this is a location message
        if Latitude and Longitude:
            print(f"\n📍 Location received from: {ProfileName} ({from_number})")
            print(f"   Coordinates: {Latitude}, {Longitude}")

            # Convert coordinates to city/area
            location_info = location_service.get_location_from_coordinates(
                float(Latitude),
                float(Longitude)
            )

            print(f"   📍 Detected: {location_info['city']}, {location_info.get('area', '')}")

            # Store location info with coordinates
            location_info['latitude'] = Latitude
            location_info['longitude'] = Longitude
            location_service.store_user_location(from_number, location_info)

            # Also store in agent context for pricing agent to use
            agent_context = agent_router.context_manager.get_context(from_number)
            agent_context['user_info']['location'] = location_info['city']

            # Get pricing for this location
            pricing = config.get_location_pricing(location_info['city'])
            consultation = pricing['consultation']

            # Build location-aware response
            area_text = f", {location_info['area']}" if location_info.get('area') else ""
            reply_message = f"""📍 Thanks for sharing your location!

🏥 You're in {location_info['city']}{area_text}

💰 Our pricing for your area:
• Initial Consultation: {consultation['initial']} {config.currency}
• Follow-up: {consultation['followup']} {config.currency}
• Emergency: {consultation['emergency']} {config.currency}

All future pricing will be customized for your location!

What would you like to know?
• Ask about packages
• Book an appointment
• Learn about our services"""

        else:
            # Normal text message
            print(f"\n💬 WhatsApp from: {ProfileName} ({from_number})")
            print(f"📝 Message: {Body}")

            result = get_reply(Body, from_number, ProfileName)
            reply_message = result['reply']

        # Send response
        if twilio_client:
            twilio_client.messages.create(
                from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
                to=f"whatsapp:{from_number}",
                body=reply_message
            )

        return Response(content="", status_code=200)

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/appointments/availability")
async def check_availability(query: AvailabilityQuery):
    """Get available appointment slots for a date (FAST)"""
    try:
        slots = calendar_service.get_available_slots_for_date(query.date)

        return {
            "success": True,
            "date": query.date,
            "appointment_type": query.appointment_type,
            "available_slots": slots,
            "count": len(slots)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import BackgroundTasks
import pytz

@app.post("/appointments/book")
async def book_appointment(
    booking: AppointmentBooking,
    background_tasks: BackgroundTasks
):
    """
    Book an appointment (FAST response, previous behavior preserved)
    """
    try:
        # 1️⃣ Timezone
        tz_name = config.config["hours"].get("timezone", "UTC")
        tz = pytz.timezone(tz_name)

        # 2️⃣ Build datetime
        try:
            start_dt = tz.localize(
                datetime.strptime(
                    f"{booking.date} {booking.time}",
                    "%Y-%m-%d %H:%M"
                )
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date or time format"
            )

        duration_minutes = config.initial_duration
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        # ✅ FAST single-day availability check (NO AGENTS)
        slots = calendar_service.get_available_slots_for_date(booking.date)

        selected_slot = next(
            (
                s for s in slots
                if s["start_datetime"].startswith(start_dt.isoformat()[:16])
            ),
            None
        )

        if not selected_slot:
            return {
                "success": False,
                "error": "Selected time slot is not available"
            }

        # 3️⃣ FAST calendar booking (no email, no zoom)
        result = calendar_service.book_appointment_fast(
            patient_name=booking.patient_name,
            patient_phone=booking.patient_phone,
            patient_email=booking.patient_email,
            start_datetime=start_dt,
            end_datetime=end_dt,
            appointment_type=booking.appointment_type,
            notes=booking.notes or ""
        )

        # 4️⃣ Background Zoom + email ONLY for online
        if booking.appointment_type == "online":
            background_tasks.add_task(
                calendar_service.finalize_online_booking,
                result["event_id"],
                booking,
                start_dt,
                end_dt
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))    

@app.get("/appointments/list")
async def list_appointments(
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 50
):
    """
    List all appointments from Google Calendar (for doctors)

    Query params:
    - time_min: Start time in ISO format (defaults to now)
    - time_max: End time in ISO format (defaults to 30 days from now)
    - max_results: Maximum number of events to return (default: 50)
    """
    try:
        appointments = calendar_service.list_appointments(
            time_min=time_min,
            time_max=time_max,
            max_results=max_results
        )

        return {
            "success": True,
            "count": len(appointments),
            "appointments": appointments
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/appointments/today")
async def get_today_appointments():
    """Get today's appointments (for doctors)"""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        timezone = ZoneInfo(config.timezone)
        now = datetime.now(timezone)

        # Start of today
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # End of today
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        appointments = calendar_service.list_appointments(
            time_min=start_of_day.isoformat(),
            time_max=end_of_day.isoformat(),
            max_results=100
        )

        return {
            "success": True,
            "date": now.strftime('%Y-%m-%d'),
            "count": len(appointments),
            "appointments": appointments
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/appointments/upcoming")
async def get_upcoming_appointments(days: int = 7):
    """
    Get upcoming appointments for the next N days (for doctors)

    Query params:
    - days: Number of days to look ahead (default: 7)
    """
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        timezone = ZoneInfo(config.timezone)
        now = datetime.now(timezone)
        future = now + timedelta(days=days)

        appointments = calendar_service.list_appointments(
            time_min=now.isoformat(),
            time_max=future.isoformat(),
            max_results=100
        )

        return {
            "success": True,
            "period": f"Next {days} days",
            "count": len(appointments),
            "appointments": appointments
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/config")
async def get_config_info():
    """Get current clinic configuration (public info only)"""
    return {
        "clinic": {
            "name": config.clinic_name,
            "type": config.clinic_type
        },
        "contact": {
            "phone": config.phone,
            "whatsapp": config.whatsapp,
            "email": config.email,
            "website": config.website
        },
        "location": {
            "address": config.location_address,
            "city": config.city,
            "area": config.area
        },
        "hours": config.hours_display,
        "pricing": {
            "currency": config.currency,
            "initial": config.initial_consultation_price,
            "followup": config.followup_consultation_price,
            "emergency": config.emergency_consultation_price
        }
    }




if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
