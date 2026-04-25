import requests
import json
from datetime import datetime, timezone

# Full realistic payload with long transcript
payload = {
    "tenant_code": "walmart",
    "call_sid": "CA1234567890abcdef1234567890abcdef",
    "caller_name": "John Doe",
    "caller_phone": "+15551234567",
    "email": "johndoe@example.com",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "escalation_status": "none",

    # Long transcript field
    "full_transcript": """Agent: Thank you for calling Nova. How can I help you today?
Caller: Hi, I'm having issues with my account and need to speak with someone about billing.
Agent: I'd be happy to help you with that. Can you tell me more about the billing issue you're experiencing?
Caller: Yes, I was charged twice for the same service last month and I haven't received a refund yet.
Agent: I understand that's frustrating. Let me look into that for you. Can I get your account number?
Caller: Sure, it's 123456789.
Agent: Thank you. I see the duplicate charge here. I'm going to process a refund for you right away.
Caller: That would be great, thank you.
Agent: The refund has been initiated and should appear in your account within 3-5 business days.
Caller: Perfect, I appreciate your help.
Agent: Is there anything else I can assist you with today?
Caller: No, that's all. Thank you!
Agent: You're welcome! Have a great day.""",

    # Long summary field
    "summary": "Customer called regarding a duplicate billing charge from last month. Issue was verified and a refund was processed. Customer was satisfied with the resolution. Refund will be credited within 3-5 business days.",

    "problem_statement": "Duplicate billing charge not refunded",
    "outcome": "booked",
    "next_steps": "Monitor refund processing over next 5 business days. Follow up if refund not received."
}

print("Sending full payload to CRM /call-logs endpoint...")
print(f"Payload size: {len(json.dumps(payload))} bytes")

try:
    response = requests.post(
        "https://crm-backend-8b97.onrender.com/call-logs",
        json=payload,
        timeout=60
    )

    print(f"\nStatus: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

except Exception as e:
    print(f"Error: {e}")
