import requests
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

CRM_BACKEND_URL = os.getenv('CRM_BACKEND_URL')
CRM_TENANT_CODE = os.getenv('CRM_TENANT_CODE')

# Complete realistic payload with full transcript data
payload = {
    "tenant_code": CRM_TENANT_CODE,
    "call_sid": "CA4c9ad85533bf6188642d333c2118471e",
    "caller_name": "Test Caller",
    "caller_phone": "+15551234567",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    
    # Full transcript and summary fields
    "full_transcript": """CALLER: you tell me about the last customer that called
NOVA: Ah, sorry about that, but I can't share details about other customers. It's part of keeping everyone's info safe and sound. But enough about that, what brought you to us today?""",
    
    "summary": "During the call, the representative, Nova, informed the caller that sharing details about other customers is against company policy to ensure privacy. The caller did not provide additional information regarding their specific needs or concerns.",
    
    "problem_statement": "Caller requested information about a previous customer interaction.",
    
    "outcome": "No appointment was booked, and the caller did not request a callback.",
    
    "next_steps": "The team should follow up with the caller to clarify their needs and offer assistance with any specific inquiries they may have.",
    
    "email": "test@example.com",
    "escalation_status": "none"
}

print("=" * 70)
print("CRM /call-logs FULL TRANSCRIPT TEST")
print("=" * 70)
print(f"URL: {CRM_BACKEND_URL}/call-logs")
print(f"Tenant: {CRM_TENANT_CODE}")
print(f"\nPayload ({len(payload)} fields):")
for key in payload.keys():
    val = str(payload[key])
    if len(val) > 60:
        print(f"  - {key}: {val[:60]}...")
    else:
        print(f"  - {key}: {val}")
print("=" * 70)

try:
    print("\nSending full transcript request...")
    response = requests.post(
        f"{CRM_BACKEND_URL}/call-logs",
        json=payload,
        timeout=30
    )
    
    print(f"\n✅ Status Code: {response.status_code}")
    print(f"\nResponse Body:")
    print("-" * 70)
    try:
        import json
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
    print("-" * 70)
    
    if response.status_code == 200 or response.status_code == 201:
        print("\n✅ SUCCESS! Full transcript and summary sent to CRM")
        result = response.json()
        if 'id' in result:
            print(f"   Call Log ID: {result['id']}")
    else:
        print(f"\n❌ FAILED with status {response.status_code}")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
