import requests
import json
from datetime import datetime, timezone

# Test payload with Home Depot tenant
payload = {
    "tenant_code": "home_depot",
    "call_sid": "CA_test_homedepot_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
    "caller_name": "Yucatan",
    "caller_phone": "+15551234567",
    "email": "yucatan@homedepot.test.com",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "escalation_status": "none",

    # Transcript fields
    "full_transcript": "Agent: Thank you for calling Nova. How can I help you today?\nCaller: Hi, this is Yucatan calling for Home Depot.\nAgent: Great! What company are you calling for?\nCaller: Home Depot.\nAgent: Perfect! When are you looking to get started?\nCaller: This week if possible.\nAgent: Sounds good! Do you have a budget in mind?\nCaller: Around $5000.\nAgent: Got it. Are you the main decision-maker?\nCaller: Yes, just me.\nAgent: Excellent! Let me help you book an appointment.",

    "summary": "Yucatan from Home Depot called to schedule service. Timeline: this week. Budget: ~$5000. Sole decision-maker. Ready to book appointment.",

    "problem_statement": "Need to schedule service for Home Depot location",
    "outcome": "booked",
    "next_steps": "Book appointment and send confirmation"
}

print("Sending test call data to CRM...")
print(f"Tenant: {payload['tenant_code']}")
print(f"Caller: {payload['caller_name']}")
print(f"Call SID: {payload['call_sid']}")

try:
    response = requests.post(
        "https://crm-backend-8b97.onrender.com/call-logs",
        json=payload,
        timeout=60
    )

    print(f"\nStatus: {response.status_code}")

    if response.status_code in [200, 201]:
        result = response.json()
        print("\n✅ SUCCESS - Call log created!")
        print(f"Call Log ID: {result.get('id')}")
        print(f"Contact ID: {result.get('contact_id')}")
        print(f"Tenant ID: {result.get('tenant_id')}")
        print(f"Tenant Code: {result.get('tenant_code')}")
        print(f"\nFull Response:")
        print(json.dumps(result, indent=2))
    else:
        print(f"\n❌ ERROR - Status {response.status_code}")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"\n❌ Exception: {e}")
