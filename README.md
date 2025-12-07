# 🤖 Nova Voice Agent for Orbyn.ai

An AI-powered voice agent that handles phone calls, books appointments, sends SMS confirmations, and logs to Notion CRM.

## 📞 Quick Test

Call: **+1 (814) 568-5796** (after setup)

## 🚀 Quick Start (15 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Server
```bash
cd backend
python main.py
```

### 3. Expose with ngrok
```bash
# In a new terminal
ngrok http 8000
# Copy the https URL
```

### 4. Configure Twilio
1. Go to https://console.twilio.com/
2. Phone Numbers → Active Numbers → +1 (814) 568-5796
3. Voice Configuration:
   - Webhook: `https://YOUR-NGROK-URL/webhooks/voice/incoming`
   - Method: POST
4. Save

### 5. Test It!
Call: +1 (814) 568-5796

## 📁 Project Structure

```
nova-voice-agent/
├── .env                    # Your API keys (already configured!)
├── requirements.txt        # Python dependencies
├── README.md              # This file
│
└── backend/
    ├── main.py            # Start server here
    ├── config.py          # Configuration
    ├── models.py          # Data structures
    │
    ├── routes/
    │   ├── health.py      # Health check
    │   └── webhooks.py    # Twilio webhooks (IMPORTANT!)
    │
    └── services/
        ├── conversation.py # OpenAI integration
        ├── calendar.py     # Cal.com integration
        ├── sms.py         # Twilio SMS
        └── crm.py         # Notion integration
```

## 🎯 What Nova Does

1. **Answers calls** via Twilio
2. **Converses naturally** using OpenAI GPT-4
3. **Collects info**: name, phone, email, service
4. **Books appointments** in Cal.com
5. **Sends SMS** confirmations
6. **Logs to Notion** CRM

## 🔑 Your API Keys (Already Configured!)

Check your `.env` file - everything is already set up:
- ✅ Twilio (phone calls)
- ✅ OpenAI (AI conversation)
- ✅ Cal.com (scheduling)
- ✅ Notion (CRM)
- ✅ CRM Backend (optional - for external CRM integration)

## 🧪 Testing

### Test Server Health
```bash
curl http://localhost:8000/health
```

### Test Complete Flow
1. Start server: `python backend/main.py`
2. Start ngrok: `ngrok http 8000`
3. Configure Twilio with ngrok URL
4. Call: +1 (814) 568-5796
5. Have a conversation with Nova
6. Book an appointment
7. Check SMS, Cal.com, and Notion

## 📊 What to Watch

When you call, watch the terminal for:
```
📞 Incoming call: CA...
🗣️  User said: Hi, I need help
🤖 Nova says: Great! Can I get your name?
📊 Extracted: {'name': 'John'}
📅 Booking: Yes
✅ SMS sent!
✅ Notion lead created!
```

## 🔧 Troubleshooting

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### "Address already in use"
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### Nova doesn't respond
- Check OpenAI API key in .env
- Check you have OpenAI credits
- Look at terminal for errors

### No SMS received
- Check phone number format: +1XXXXXXXXXX
- Verify Twilio number is SMS-enabled

## 🔗 CRM Backend Integration

Nova can automatically send call data to your external CRM backend at the end of each call. This is optional and works alongside the existing Notion integration.

### Setup

Add this variable to your `.env` file:

```bash
# CRM Backend Integration (optional)
CRM_BACKEND_URL=https://crm-backend-8b97.onrender.com
CRM_TENANT_CODE=walmart
```

### How it works

At the end of each call, Nova automatically sends contact data to your CRM backend:
- **Endpoint**: `POST {CRM_BACKEND_URL}/public/submit-contact`
- **Authentication**: None (public endpoint)
- **Payload**: Minimal JSON contract required by the public endpoint

Example payload:
```json
{
  "name": "from nova",
  "email": "from nova",
  "phone": "from nova",
  "tenant_code": "walmart"
}
```

### Error Handling

- Failed CRM pushes are logged but do not crash the call flow
- Both successful and failed attempts are logged in console
- If CRM backend is not configured, it's silently skipped

### Testing

Test your CRM backend integration:
```bash
python test_integrations.py
```

