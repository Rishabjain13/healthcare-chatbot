import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests
from openai import OpenAI
from twilio.rest import Client
from agents import AgentRouter

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER')
RASA_URL = os.getenv('RASA_URL', 'http://localhost:5005')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.70'))
PORT = int(os.getenv('PORT', '3000'))

# Initialize clients
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize Multi-Agent System
agent_router = AgentRouter()

# Initialize OpenAI only if key is provided
openai_client = None
if OPENAI_API_KEY and OPENAI_API_KEY != 'your_openai_key_here':
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI configured")
    except Exception as e:
        print(f"⚠️  OpenAI not configured: {e}")
        print("   Bot will use Agent system only")

# In-memory conversation storage
conversations = {}


def get_intent_from_rasa(message, sender):
    """Get intent classification from RASA"""
    try:
        print(f"   → Asking RASA for intent...")

        # First, parse the message to get intent
        parse_response = requests.post(
            f"{RASA_URL}/model/parse",
            json={"text": message},
            timeout=5
        )

        parse_data = parse_response.json()

        if parse_data:
            intent_data = parse_data.get('intent', {})
            intent_name = intent_data.get('name', 'unknown')
            confidence = intent_data.get('confidence', 0)

            print(f"   ✅ Intent: {intent_name} (confidence: {confidence:.2f})")

            return {
                'intent': intent_name,
                'confidence': confidence,
                'entities': parse_data.get('entities', [])
            }

        return {
            'intent': 'unknown',
            'confidence': 0,
            'entities': []
        }

    except Exception as e:
        print(f"   ❌ RASA error: {str(e)}")
        return {
            'intent': 'unknown',
            'confidence': 0,
            'entities': []
        }


def ask_openai(message, sender):
    """Send message to OpenAI and get response"""
    try:
        # Check if OpenAI is configured
        if not openai_client:
            return "I can help with specific questions about the clinic. Try asking about hours, pricing, or services!"

        print(f"   → Asking OpenAI...")

        # Initialize conversation history for this user
        if sender not in conversations:
            conversations[sender] = []

        # System prompt
        system_prompt = """You are a helpful medical assistant for Functional Medicine Clinics in Dubai.
- Help with appointments (Thursday & Saturday, 9 AM - 5 PM)
- Answer health questions (never diagnose, always recommend seeing a doctor)
- Respond in the SAME language as the patient (English or Arabic)
- Be empathetic, professional, and concise
- Consultation fees: Initial 350 AED, Follow-up 200 AED, Emergency 500 AED
- Location: Dubai Healthcare City"""

        # Build messages array
        messages = [
            {"role": "system", "content": system_prompt},
            *conversations[sender],
            {"role": "user", "content": message}
        ]

        # Call OpenAI
        completion = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=200,
            temperature=0.7
        )

        reply = completion.choices[0].message.content

        # Update conversation history
        conversations[sender].append({"role": "user", "content": message})
        conversations[sender].append({"role": "assistant", "content": reply})

        # Keep only last 20 messages
        if len(conversations[sender]) > 20:
            conversations[sender] = conversations[sender][-20:]

        return reply

    except Exception as e:
        print(f"   ❌ OpenAI error: {str(e)}")
        return "I'm having trouble processing that. Please try again."


def get_reply(message, sender, name):
    """Main logic: RASA classifies intent → Agent responds → OpenAI fallback"""
    print(f"\n{'=' * 70}")
    print(f"📨 From: {name} ({sender})")
    print(f"💬 Message: \"{message}\"")

    # Step 1: Get intent from RASA
    rasa_result = get_intent_from_rasa(message, sender)
    intent = rasa_result['intent']
    confidence = rasa_result['confidence']

    # Step 2: If high confidence, route to specialized agent
    if confidence >= CONFIDENCE_THRESHOLD and intent != 'unknown':
        print(f"✅ High confidence ({confidence * 100:.1f}%) - Routing to agent")

        # Route to appropriate agent
        agent_result = agent_router.route(intent, message, sender)

        print(f"   🤖 Agent: {agent_result['agent'].upper()}")
        print(f"   ✅ Response generated")

        return {
            'reply': agent_result['response'],
            'handler': f"Agent ({agent_result['agent']})",
            'intent': intent,
            'confidence': confidence
        }

    # Step 3: Low confidence or unknown - try OpenAI fallback
    print(f"⚠️  Low confidence ({confidence * 100:.1f}%) or unknown intent")

    if openai_client:
        print(f"🤖 Falling back to OpenAI...")
        openai_reply = ask_openai(message, sender)
        print(f"✅ OpenAI handled")

        return {
            'reply': openai_reply,
            'handler': 'OpenAI (Fallback)',
            'intent': intent,
            'confidence': confidence
        }
    else:
        # No OpenAI - use general agent fallback
        print(f"🤖 Using general agent fallback...")
        fallback_response = agent_router.get_fallback_response(message, sender)

        return {
            'reply': fallback_response,
            'handler': 'General Agent',
            'intent': 'unknown',
            'confidence': 0
        }


@app.route('/sms/webhook', methods=['POST'])
def sms_webhook():
    """Handle incoming SMS messages from Twilio"""
    try:
        # Get message details
        from_number = request.form.get('From', '')
        message = request.form.get('Body', '')
        name = 'SMS User'

        print(f"\n📱 SMS received from: {from_number}")
        print(f"📝 Message: {message}")

        # Get reply
        result = get_reply(message, from_number, name)

        # Send reply via Twilio SMS
        response = twilio_client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            to=from_number,
            body=result['reply']
        )

        print(f"✅ SMS reply sent: {response.sid}")

        return '', 200

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return '', 500


@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages from Twilio"""
    try:
        # Get message details
        from_number = request.form.get('From', '').replace('whatsapp:', '')
        message = request.form.get('Body', '')
        name = request.form.get('ProfileName', 'User')

        # Get reply
        result = get_reply(message, from_number, name)

        # Send reply via Twilio
        twilio_client.messages.create(
            from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
            to=f"whatsapp:{from_number}",
            body=result['reply']
        )

        return '', 200

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return '', 500


@app.route('/test', methods=['POST'])
def test():
    """Test endpoint for debugging"""
    try:
        data = request.get_json()
        message = data.get('message', '')

        if not message:
            return jsonify({'error': 'No message provided'}), 400

        result = get_reply(message, 'test_user', 'Test User')

        return jsonify({
            'success': True,
            'message': message,
            'reply': result['reply'],
            'handler': result['handler'],
            'confidence': result['confidence']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'OK',
        'rasa': RASA_URL,
        'threshold': CONFIDENCE_THRESHOLD
    })


@app.route('/', methods=['GET'])
def home():
    """Home endpoint"""
    return '''
    <h1>🤖 Healthcare Chatbot Backend</h1>
    <p>Status: <strong>Running!</strong></p>
    <p>RASA URL: <code>{}</code></p>
    <p>Confidence Threshold: <strong>{}</strong></p>
    '''.format(RASA_URL, CONFIDENCE_THRESHOLD)


if __name__ == '__main__':
    print('\n' + '=' * 70)
    print('🚀 Healthcare Chatbot Backend - MULTI-AGENT SYSTEM')
    print('=' * 70)
    print(f'📡 Server: http://localhost:{PORT}')
    print(f'📊 RASA: {RASA_URL}')
    print(f'⚡ Confidence Threshold: {CONFIDENCE_THRESHOLD}')
    print('\n🤖 Active Agents:')
    print('   📅 Appointment Agent')
    print('   💰 Pricing Agent')
    print('   🔬 Lab Test Agent')
    print('   🩺 Treatment Agent')
    print('   💬 Support Agent')
    print('   🌟 General Agent')
    print('=' * 70 + '\n')

    app.run(host='0.0.0.0', port=PORT, debug=True)
