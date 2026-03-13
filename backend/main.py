"""
FastAPI Backend for Healthcare Chatbot
Multi-Agent System with Google Calendar Integration
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, field_validator
import pytz
import requests
from openai import OpenAI
from twilio.rest import Client

from config_loader import get_config
from google_calendar_service import get_calendar_service
from agents import AgentRouter
from location_service import get_location_service
from rag_service import get_rag_service

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
rag_service = get_rag_service()

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

# Response cache for high-frequency stateless questions (hours, pricing, location, etc.)
# Only caches when no booking flow is active. Keyed by normalized message text.
_response_cache: Dict[str, Dict] = {}

# Intents whose responses are deterministic and safe to cache
_CACHEABLE_INTENTS = {
    'ask_hours', 'ask_pricing', 'ask_location', 'ask_doctors',
    'ask_services', 'ask_online_consultation', 'ask_parking',
    'ask_insurance', 'ask_languages', 'ask_bring_tests',
}


# Pydantic models
class ChatMessage(BaseModel):
    message: str
    sender: str = "test_user"
    name: str = "Test User"

    @field_validator('message')
    @classmethod
    def message_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Message cannot be empty')
        if len(v) > 2000:
            raise ValueError('Message too long (max 2000 characters)')
        return v


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


def ask_openai(message: str, sender: str, context: Dict, rag_context: str = None) -> str:
    """Send message to OpenAI, optionally grounded with RAG-retrieved knowledge base context."""
    try:
        if not openai_client:
            print(f"   ⚠️  OpenAI not configured")
            return None

        if rag_context:
            print(f"   → Asking OpenAI with RAG context (grounded)...")
        else:
            print(f"   → Asking OpenAI with conversation history...")

        # Build conversation history for OpenAI
        messages = []

        # System prompt with clinic info and safety guidelines
        current_flow = context.get('current_flow', 'general conversation')
        user_info = context.get('user_info', {})
        collected_info = ', '.join([f"{k}: {v}" for k, v in user_info.items()]) if user_info else 'none yet'

        # Build doctor info dynamically from config.yml
        doctors = config.config.get('doctors', [])
        doctor = doctors[0] if doctors else {}
        doctor_name = doctor.get('full_name', 'Our Doctor')
        doctor_title = doctor.get('title', '')
        doctor_qualifications = doctor.get('qualifications', '')
        doctor_specialties = ', '.join(doctor.get('specialties', config.specialties))
        doctor_languages = ', '.join(doctor.get('languages', ['English']))
        doctor_locations = ', '.join(doctor.get('locations', [config.city]))
        doctor_approach = doctor.get('approach', '')

        system_prompt = f"""You are a helpful medical assistant for {config.clinic_name}.

DOCTOR INFORMATION:
- {doctor_name} — {doctor_title}
- {doctor_qualifications}
- Specializes in: {doctor_specialties}
- Languages: {doctor_languages}
- Locations: {doctor_locations}
- Approach: {doctor_approach}

CONSULTATION OPTIONS:
- IN-PERSON: At our clinic in {config.area}, {config.city}
- ONLINE: Via Zoom video call (same pricing, convenient for anyone worldwide)
- We offer both in-person and online consultations at your preferred time

IMPORTANT SAFETY GUIDELINES:
- Help with appointments, pricing, lab tests, and clinic information
- Answer health questions (never diagnose, always recommend seeing {doctor_name})
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

        # Append RAG-retrieved knowledge when available — grounds the answer in
        # actual clinic documents instead of LLM general knowledge.
        if rag_context:
            system_prompt += f"\n\nRELEVANT CLINIC KNOWLEDGE BASE:\n{rag_context}\n\nAnswer using the knowledge above. Do not guess or add information not in the knowledge base."

        messages.append({"role": "system", "content": system_prompt})

        # Fewer history turns needed when RAG context already grounds the answer
        history_limit = 4 if rag_context else 8
        history = context.get('history', [])[-history_limit:]
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
        print(f"   └─ Mode: {'RAG-grounded' if rag_context else 'History-aware'}")
        print(f"   └─ System Prompt: {len(system_prompt)} chars")
        print(f"   └─ Conversation History: {len(history)} messages")
        print(f"   └─ Total Context: {len(messages)} messages")
        print(f"   └─ Current Flow: {current_flow}")
        print(f"   └─ User Info: {collected_info}")

        # Call OpenAI with GPT-4o-mini
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            temperature=0.7
        )

        reply = completion.choices[0].message.content

        print(f"\n📥 OPENAI RESPONSE:")
        print(f"   └─ Generated: {len(reply)} chars")
        print(f"   └─ Model: gpt-4o-mini")
        print(f"   ✅ OpenAI response generated ({len(history)} messages in context)")

        return reply

    except Exception as e:
        print(f"   ❌ OpenAI error: {str(e)}")
        return None


# Keyword pre-filter: maps (lowercase keyword → intent).
# Checked before Rasa to skip the HTTP call entirely for obvious phrases.
# Order matters — more specific phrases first.
_KEYWORD_SHORTCUTS: List[tuple] = [
    # Booking — specific enough to avoid false positives like "book a table"
    ('book appointment', 'book_appointment'),
    ('book an appointment', 'book_appointment'),
    ('book a consultation', 'book_appointment'),
    ('book a visit', 'book_appointment'),
    ('schedule appointment', 'book_appointment'),
    ('make appointment', 'book_appointment'),
    # Hours — avoid "what time is it?" false positive
    ('opening hour', 'ask_hours'),
    ('working hour', 'ask_hours'),
    ('what time do you open', 'ask_hours'),
    ('what time are you open', 'ask_hours'),
    ('what time does the clinic', 'ask_hours'),
    ('when are you open', 'ask_hours'),
    ('are you open', 'ask_hours'),
    ('clinic hour', 'ask_hours'),
    # Pricing
    ('how much', 'ask_pricing'),
    ('what is the price', 'ask_pricing'),
    ('what is the cost', 'ask_pricing'),
    ('consultation fee', 'ask_pricing'),
    ('consultation cost', 'ask_pricing'),
    ('pricing', 'ask_pricing'),
    # Location
    ('where are you', 'ask_location'),
    ('your address', 'ask_location'),
    ('clinic location', 'ask_location'),
    ('how to get', 'ask_location'),
    # Doctor
    ('about the doctor', 'ask_doctors'),
    ('who is the doctor', 'ask_doctors'),
    ('tell me about dr', 'ask_doctors'),
    # Greeting — Arabic + English
    ('مرحب', 'greet'),
    ('السلام', 'greet'),
]


def _keyword_shortcut(message: str) -> Optional[str]:
    """Return an intent if the message matches a keyword shortcut, else None."""
    lower = message.lower()
    for keyword, intent in _KEYWORD_SHORTCUTS:
        if keyword in lower:
            return intent
    return None


def get_reply(message: str, sender: str, name: str) -> Dict:
    """Main logic: RASA intent classification → Backend Agent (with context)"""
    print(f"\n{'=' * 70}")
    print(f"📨 From: {name} ({sender})")
    print(f"💬 Message: \"{message}\"")

    # Get conversation context early — needed for flow check before shortcuts
    context = agent_router.context_manager.get_context(sender)
    current_flow_early = context.get('current_flow')

    # Keyword pre-filter — only when no active flow (flow needs Rasa for step parsing)
    shortcut_intent = None if current_flow_early else _keyword_shortcut(message)
    if shortcut_intent:
        print(f"⚡ KEYWORD SHORTCUT: '{shortcut_intent}' — skipping Rasa")
        intent = shortcut_intent
        confidence = 1.0
        entities = []
    else:
        # Get intent from RASA (stateless classification only)
        rasa_result = get_rasa_response(message, sender)
        intent = rasa_result['intent']
        confidence = rasa_result['confidence']
        entities = rasa_result.get('entities', [])

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
        # Serve from cache for stateless informational intents
        cache_key = f"{intent}:{message.lower().strip()}"
        if intent in _CACHEABLE_INTENTS and cache_key in _response_cache:
            print(f"✅ Cache HIT for '{intent}' — skipping agent call")
            cached = _response_cache[cache_key]
            return {**cached, 'handler': f"Cache ({cached['handler']})"}

        print(f"✅ High confidence ({confidence * 100:.1f}%) - Routing to specialized agent")
        agent_result = agent_router.route(intent, message, sender)

        print(f"   🤖 Agent: {agent_result['agent'].upper()}")
        print(f"   ✅ Response generated")
        if agent_result.get('buttons'):
            print(f"   🔘 Buttons: {agent_result['buttons']}")

        result = {
            'reply': agent_result['response'],
            'handler': f"Agent ({agent_result['agent']})",
            'intent': intent,
            'confidence': confidence,
            'buttons': agent_result.get('buttons', [])
        }

        # Store in cache if this is a stateless informational intent
        if intent in _CACHEABLE_INTENTS:
            _response_cache[cache_key] = result

        return result

    # PRIORITY 3: RAG — retrieve from clinic knowledge base
    # For questions about treatments, conditions, doctor info, protocols.
    # Grounded answers from actual clinic documents — no hallucination.
    # Only skipped if RAG finds nothing relevant (score threshold not met).
    else:
        # Check LLM/RAG response cache first
        llm_cache_key = f"llm:{message.lower().strip()}"
        if llm_cache_key in _response_cache:
            print(f"✅ LLM Cache HIT — skipping RAG + OpenAI call")
            cached = _response_cache[llm_cache_key]
            agent_router.context_manager.update_context(
                sender, 'openai', intent, message, cached['reply']
            )
            return {**cached, 'handler': f"Cache (OpenAI)"}

        # Try RAG retrieval
        RAG_SCORE_THRESHOLD = 0.45  # Minimum similarity score to use RAG context
        rag_context = None
        rag_hits = []

        try:
            rag_hits = rag_service.retrieve(message, top_k=3)
            top_score = rag_hits[0]['score'] if rag_hits else 0
            print(f"🔍 RAG retrieval: {len(rag_hits)} results, top score={top_score:.3f}")

            if top_score >= RAG_SCORE_THRESHOLD:
                # Build context string from top retrieved chunks
                rag_context = "\n\n".join(
                    f"[{doc['title']}]\n{doc['text']}"
                    for doc in rag_hits
                    if doc['score'] >= RAG_SCORE_THRESHOLD
                )
                print(f"   ✅ RAG context found ({len(rag_context)} chars) — grounding LLM answer")
            else:
                print(f"   ⚠️  RAG score too low ({top_score:.3f} < {RAG_SCORE_THRESHOLD}) — falling back to history-aware LLM")
        except Exception as e:
            print(f"   ❌ RAG error: {e} — falling back to LLM")

        # PRIORITY 4: OpenAI — grounded with RAG context if available, else history-aware
        mode = "RAG-grounded" if rag_context else "history-aware"
        print(f"🤖 Low confidence ({confidence * 100:.1f}%) — Using OpenAI ({mode})")

        openai_response = ask_openai(message, sender, context, rag_context=rag_context)

        if openai_response:
            agent_router.context_manager.update_context(
                sender, 'openai', intent, message, openai_response
            )
            handler = f"RAG + OpenAI (grounded)" if rag_context else "OpenAI (history-aware)"
            print(f"   ✅ {handler} response generated")

            result = {
                'reply': openai_response,
                'handler': handler,
                'intent': intent,
                'confidence': confidence,
                'buttons': []
            }
            _response_cache[llm_cache_key] = result
            return result

        # PRIORITY 5: General Agent Fallback
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
    # Probe Rasa liveness
    rasa_status = "unreachable"
    try:
        r = requests.get(f"{RASA_URL}/", timeout=3)
        rasa_status = "ok" if r.status_code == 200 else f"http_{r.status_code}"
    except Exception:
        pass

    return {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "clinic": config.clinic_name,
        "rasa_url": RASA_URL,
        "rasa_status": rasa_status,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "google_calendar_enabled": config.google_calendar_enabled,
        "openai_enabled": openai_client is not None,
        "rag_documents": len(rag_service.metadata) if rag_service.metadata else 0
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
