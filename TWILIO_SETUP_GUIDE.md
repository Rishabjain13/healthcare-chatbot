# 🚀 Twilio Setup Guide for Healthcare Chatbot

## Overview
You have two options for testing with Twilio:
1. **SMS with Virtual Phone** - Quick testing with text messages
2. **WhatsApp Sandbox** - Real WhatsApp experience (Recommended!)

---

## Option 1: SMS Testing with Virtual Phone

### Step 1: Get Your Twilio Credentials
1. Go to [Twilio Console](https://console.twilio.com/)
2. Find your **Account SID** and **Auth Token**
3. Get a Twilio phone number (if you don't have one)

### Step 2: Update .env File
```env
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890  # Your Twilio number
```

### Step 3: Test Sending SMS
```bash
cd ~/Desktop/healthcare-chatbot/backend
python3 test_twilio_sms.py
```

### Step 4: Check Virtual Phone Inbox
- Go to: https://console.twilio.com/us1/develop/phone-numbers/virtual-phone
- You'll see your test message!

---

## Option 2: WhatsApp Sandbox (Recommended!) 📱

### Why WhatsApp Sandbox?
- ✅ Test real WhatsApp conversations
- ✅ Free during development
- ✅ No carrier approval needed
- ✅ Perfect for healthcare chatbot testing

### Step 1: Activate WhatsApp Sandbox

1. **Go to WhatsApp Sandbox:**
   - Visit: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
   - Or navigate: Console → Messaging → Try it out → Send a WhatsApp message

2. **Join the Sandbox:**
   - You'll see a code like: `join <your-code>`
   - Example: `join yellow-tiger`
   - Send this to: **+1 415 523 8886** on WhatsApp
   - You'll receive a confirmation message!

### Step 2: Configure Webhook

1. **In Twilio Console:**
   - Go to: Messaging → Settings → WhatsApp Sandbox Settings
   - Find "WHEN A MESSAGE COMES IN"

2. **Set Your Webhook URL:**
   ```
   http://your-server-ip:3000/whatsapp/webhook
   ```

   **For local testing with ngrok:**
   ```
   https://your-ngrok-url.ngrok.io/whatsapp/webhook
   ```

3. **Set Method:** POST

4. **Click Save**

### Step 3: Update Your .env File

```env
# Twilio Credentials
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here

# WhatsApp Sandbox Number (Twilio's)
TWILIO_WHATSAPP_NUMBER=+14155238886

# Your configuration
RASA_URL=http://localhost:5005
OPENAI_API_KEY=your_openai_key_here
CONFIDENCE_THRESHOLD=0.70
PORT=3000
```

### Step 4: Start Everything

**Terminal 1 - Start RASA:**
```bash
cd ~/Desktop/healthcare-chatbot/rasa-bot
rasa run --enable-api --cors "*" --port 5005
```

**Terminal 2 - Start Backend:**
```bash
cd ~/Desktop/healthcare-chatbot/backend
python3 server.py
```

**Terminal 3 (Optional) - Use ngrok for public URL:**
```bash
# Install ngrok first: brew install ngrok
ngrok http 3000
```
Copy the HTTPS URL and update your Twilio webhook!

### Step 5: Test on WhatsApp!

1. Open WhatsApp on your phone
2. Message the sandbox: **+1 415 523 8886**
3. Try these messages:
   - "hello"
   - "what are your hours"
   - "how much does it cost"
   - "مرحبا" (Arabic)

---

## Testing Checklist ✅

### Before Testing:
- [ ] RASA server is running (port 5005)
- [ ] Backend server is running (port 3000)
- [ ] Twilio credentials in .env file
- [ ] WhatsApp Sandbox activated
- [ ] Webhook URL configured
- [ ] Joined sandbox on WhatsApp

### Test These Scenarios:
- [ ] Send greeting → Get welcome message
- [ ] Ask about hours → Get clinic hours
- [ ] Ask about pricing → Get pricing info
- [ ] Ask in Arabic → Get Arabic support
- [ ] Complex medical question → OpenAI fallback

---

## Troubleshooting 🔧

### "Cannot connect to RASA"
```bash
# Check if RASA is running:
curl http://localhost:5005

# If not, start it:
cd ~/Desktop/healthcare-chatbot/rasa-bot
rasa run --enable-api --cors "*" --port 5005
```

### "Twilio webhook not working"
- Make sure your server is publicly accessible (use ngrok)
- Check webhook URL in Twilio console
- Verify POST method is selected
- Check server logs for errors

### "No response from bot"
- Check RASA is running: `curl http://localhost:5005`
- Check backend logs: Look for errors in Terminal 2
- Verify .env credentials are correct
- Test with the interactive script first: `python3 test_bot.py`

---

## Production Deployment 🚀

### When Ready for Production:
1. Get WhatsApp Business API approval
2. Use a real WhatsApp Business number
3. Deploy backend to cloud (AWS, Heroku, etc.)
4. Use proper domain with SSL
5. Update webhook URL in Twilio

### Security Checklist:
- [ ] Never commit .env file
- [ ] Use environment variables in production
- [ ] Enable webhook signature validation
- [ ] Use HTTPS for all endpoints
- [ ] Monitor logs for security issues

---

## Quick Commands Reference 📝

```bash
# Start RASA
cd ~/Desktop/healthcare-chatbot/rasa-bot
rasa run --enable-api --cors "*" --port 5005

# Start Backend
cd ~/Desktop/healthcare-chatbot/backend
python3 server.py

# Test Interactive Bot
cd ~/Desktop/healthcare-chatbot/backend
python3 test_bot.py

# Test SMS to Virtual Phone
cd ~/Desktop/healthcare-chatbot/backend
python3 test_twilio_sms.py

# Start ngrok (for public URL)
ngrok http 3000
```

---

## Support & Resources 📚

- **Twilio Docs:** https://www.twilio.com/docs/whatsapp
- **RASA Docs:** https://rasa.com/docs/
- **OpenAI Docs:** https://platform.openai.com/docs

Need help? Check the logs in your terminal windows!
