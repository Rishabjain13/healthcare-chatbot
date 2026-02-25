# 🎥 Free Zoom Integration Setup Guide

This guide shows you how to add **FREE Zoom meeting links** to your healthcare chatbot for online consultations.

---

## ✅ What's Already Done

I've integrated Zoom into your chatbot:

1. ✅ Created `backend/zoom_service.py` - Handles Zoom meeting creation
2. ✅ Updated `backend/google_calendar_service.py` - Auto-creates Zoom links for online consultations
3. ✅ Updated `backend/agents.py` - Shows Zoom link in booking confirmations
4. ✅ Updated `backend/.env.example` - Added Zoom configuration template

---

## 🚀 Setup Steps (5 minutes)

### Step 1: Create Free Zoom Account

1. Go to https://zoom.us/signup
2. Sign up for a **FREE** account (no credit card needed)
3. Verify your email

**Free Account Benefits:**
- ✅ Unlimited 1-on-1 meetings (perfect for consultations!)
- ✅ No time limit on 1-on-1 calls
- ✅ Full API access
- ⚠️ Group meetings (3+ people) limited to 40 minutes

---

### Step 2: Create Zoom API App

1. **Go to Zoom Marketplace:**
   - Visit https://marketplace.zoom.us/
   - Click **Sign In** (use your Zoom account)

2. **Create Server-to-Server OAuth App:**
   - Click **"Develop"** → **"Build App"**
   - Choose **"Server-to-Server OAuth"** (NOT JWT or OAuth!)
   - Click **"Create"**

3. **Fill App Information:**
   - **App Name:** Healthcare Chatbot
   - **Company Name:** Your clinic name
   - **Developer Email:** Your email
   - Click **"Continue"**

4. **Add Scopes (Permissions):**
   - Click **"Add Scopes"**
   - Search and add these scopes:
     - ✅ `meeting:write:admin` (Create meetings)
     - ✅ `meeting:read:admin` (Read meeting info)
   - Click **"Continue"**

5. **Get Your Credentials:**
   - You'll see three important values:
     - **Account ID**
     - **Client ID**
     - **Client Secret**
   - **KEEP THESE SAFE!** Don't share them publicly.

---

### Step 3: Add Credentials to `.env` File

1. Open `backend/.env` (or create it from `.env.example`)

2. Add your Zoom credentials:

```bash
# ZOOM CONFIGURATION
ZOOM_ACCOUNT_ID=your_actual_account_id_here
ZOOM_CLIENT_ID=your_actual_client_id_here
ZOOM_CLIENT_SECRET=your_actual_client_secret_here
```

3. Replace `your_actual_*_here` with the real values from Step 2

4. Save the file

---

## 🧪 Test It Out

### Method 1: Using the Chat API

1. **Start your backend:**
   ```bash
   cd backend
   python main.py
   ```

2. **Test booking an online consultation:**
   ```bash
   curl -X POST http://localhost:3000/chat \
     -H "Content-Type: application/json" \
     -d '{
       "message": "I want to book an online consultation",
       "sender": "test_user",
       "name": "Test Patient"
     }'
   ```

3. **Follow the booking flow:**
   - Select "Online Consultation"
   - Choose a date and time
   - Enter your details
   - Confirm booking

4. **Check the response:**
   - You should see a Zoom meeting URL in the success message
   - The patient will also receive the Zoom link via email

### Method 2: Using Your Frontend

1. Start your chatbot and book an appointment
2. Select **"Online Consultation"** when prompted
3. Complete the booking
4. You'll see:
   ```
   🎥 ZOOM MEETING
   ━━━━━━━━━━━━━━━━━━━━━━

   Join URL: https://zoom.us/j/1234567890?pwd=...
   Meeting ID: 123 456 7890
   Password: abc123

   ⚠️ Join link also sent to your email!
   ```

---

## 📋 How It Works

### When a Patient Books an **Online Consultation:**

1. **User selects "Online Consultation"** in the chatbot
2. **Zoom API creates a meeting** with:
   - Topic: "Consultation with [Patient Name]"
   - Scheduled time (from booking)
   - Waiting room enabled (doctor must admit patient)
   - No auto-recording (privacy)
3. **Google Calendar event created** with:
   - Zoom link in description
   - Zoom URL as location
   - Email sent to patient with all details
4. **Patient receives:**
   - Email confirmation with Zoom link
   - Calendar invite
   - Chatbot shows Zoom details

### When a Patient Books an **In-Person Consultation:**

- No Zoom meeting created
- Calendar event shows clinic address
- Normal in-person booking flow

---

## 🔍 Verify Setup

**Check if Zoom is working:**

1. Look for this message when backend starts:
   ```
   ✅ Zoom service initialized
   ```

   If you see:
   ```
   ⚠️  Zoom not configured - online consultations will not have video links
   ```
   Then credentials are missing or incorrect.

2. **Test Zoom connection:**
   ```bash
   cd backend
   python -c "from zoom_service import get_zoom_service; z = get_zoom_service(); print('✅ Zoom OK' if z.enabled else '❌ Check credentials')"
   ```

---

## 🐛 Troubleshooting

### Problem: "Zoom not configured" message

**Solution:**
- Check `.env` file has correct `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`
- Make sure there are no extra spaces or quotes
- Restart backend after updating `.env`

### Problem: "Failed to authenticate with Zoom"

**Solution:**
- Verify credentials are copied correctly from Zoom Marketplace
- Check your app has the correct scopes: `meeting:write:admin`, `meeting:read:admin`
- Make sure app is **activated** in Zoom Marketplace

### Problem: Zoom link not showing in booking

**Solution:**
- Make sure user selected "Online Consultation" (not "Offline")
- Check backend logs for errors
- Verify Google Calendar integration is working

### Problem: "Invalid grant_type" error

**Solution:**
- You might have created the wrong app type
- Delete the app and create a new **"Server-to-Server OAuth"** app
- NOT "JWT" or "OAuth 2.0"

---

## 💰 Pricing Comparison

| Feature | Free Zoom | Paid Zoom Pro ($149/year) |
|---------|-----------|---------------------------|
| 1-on-1 consultations | ✅ Unlimited | ✅ Unlimited |
| Time limit (1-on-1) | ✅ No limit | ✅ No limit |
| Waiting room | ✅ Yes | ✅ Yes |
| API access | ✅ Yes | ✅ Yes |
| Group meetings | 40 min limit | 30 hours |
| Cloud recording | ❌ No | ✅ Yes |

**For healthcare consultations (1-on-1), FREE is perfect!** ✅

---

## 🔒 Security & Privacy

Your Zoom integration includes:

- ✅ **Waiting room enabled** - Patients wait for doctor to admit them
- ✅ **No auto-recording** - Privacy protected
- ✅ **Unique meeting per appointment** - No reused meeting IDs
- ✅ **Secure credentials** - Stored in `.env` (not committed to git)

---

## 📞 Alternative: Google Meet (Even Easier!)

If you prefer **Google Meet** instead of Zoom:

1. **No API setup needed!** (Already integrated with Google Calendar)
2. **Edit `google_calendar_service.py` line 299:**

```python
# Add this to the event object:
'conferenceData': {
    'createRequest': {
        'requestId': f'meet-{datetime.now().timestamp()}',
        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
    }
}
```

3. **Update the insert call (line 324):**
```python
created_event = self.service.events().insert(
    calendarId=self.calendar_id,
    body=event,
    sendUpdates='all',
    conferenceDataVersion=1  # Add this parameter
).execute()
```

**Google Meet automatically creates a video link!**

---

## 🎯 Next Steps

1. ✅ Set up Zoom credentials (follow steps above)
2. ✅ Test booking an online consultation
3. ✅ Check email confirmation includes Zoom link
4. ✅ Test joining the Zoom meeting
5. 🎉 Start offering online consultations!

---

## 📝 Notes

- Zoom meetings are created **immediately** when appointment is booked
- Patients receive Zoom link via **email and chatbot**
- Doctor can start meeting from **Google Calendar** or **Zoom dashboard**
- Free Zoom account is **perfect for 1-on-1 consultations** (no upgrade needed!)

---

Need help? Check the logs in `backend/` when you run the server - they'll show if Zoom is configured correctly!
