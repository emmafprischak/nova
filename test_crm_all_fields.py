import requests
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

CRM_BACKEND_URL = os.getenv('CRM_BACKEND_URL')
CRM_TENANT_CODE = os.getenv('CRM_TENANT_CODE')

# Complete payload with ALL old fields + new transcript fields
payload = {
    # New transcript fields
    "tenant_code": CRM_TENANT_CODE,
    "call_sid": "CA4c9ad85533bf6188642d333c2118471e",
    "full_transcript": """CALLER: you tell me about the last customer that called
NOVA: Ah, sorry about that, but I can't share details about other customers. It's part of keeping everyone's info safe and sound. But enough about that, what brought you to us today?""",
    "summary": "During the call, the representative, Nova, informed the caller that sharing details about other customers is against company policy to ensure privacy. The caller did not provide additional information regarding their specific needs or concerns.",
    "problem_statement": "Caller requested information about a previous customer interaction.",
    "outcome": "No appointment was booked, and the caller did not request a callback.",
    "next_steps": "The team should follow up with the caller to clarify their needs and offer assistance with any specific inquiries they may have.",
    
    # Old fields from submit-contact
    "caller_name": "Unknown",
    "caller_phone": "Unknown",
    "email": "novaisnotworking@orbyn.ai",
    "escalation_status": "none",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    
    # Optional fields (would be added if available)
    "notes": "Test call from Nova Voice Agent",
    "service": None,
    "status": "completed",
    "appointment_time": None
}

print("=" * 70)
print("CRM /call-logs COMPLETE PAYLOAD TEST")
print("=" * 70)
print(f"URL: {CRM_BACKEND_URL}/call-logs")
print(f"Tenant: {CRM_TENANT_CODE}")
print(f"\nPayload fields ({len(payload)} total):")
for key in payload.keys():
    val = payload[key]
    if isinstance(val, str) and len(val) > 50:
        print(f"  - {key}: {val[:50]}...")
    else:
        print(f"  - {key}: {val}")
print("=" * 70)

try:
    print("\nSending request...")
    response = requests.post(
        f"{CRM_BACKEND_URL}/call-logs",
        json=payload,
        timeout=30
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response Body:")
    print("-" * 70)
    try:
        import json
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text[:500])
    print("-" * 70)
    
    if response.status_code == 200 or response.status_code == 201:
        print("\n✅ SUCCESS! Call log sent to CRM with all fields")
    else:
        print(f"\n❌ FAILED with status {response.status_code}")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
