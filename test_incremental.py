import requests
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

CRM_BACKEND_URL = os.getenv('CRM_BACKEND_URL')
CRM_TENANT_CODE = os.getenv('CRM_TENANT_CODE')

# Base working payload
base_payload = {
    "tenant_code": CRM_TENANT_CODE,
    "caller_name": "Test Caller",
    "caller_phone": "+15551234567",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "full_transcript": "Test transcript"
}

# Fields to test adding
test_fields = [
    ("call_sid", "CA4c9ad85533bf6188642d333c2118471e"),
    ("summary", "This is a test summary"),
    ("problem_statement", "Test problem"),
    ("outcome", "No action"),
    ("next_steps", "Follow up"),
    ("email", "test@example.com"),
    ("escalation_status", "none")
]

print("Testing fields incrementally to find which causes 500 error...")
print("=" * 70)

payload = base_payload.copy()

for field_name, field_value in test_fields:
    payload[field_name] = field_value
    
    print(f"\nTesting with: {list(payload.keys())}")
    
    try:
        response = requests.post(
            f"{CRM_BACKEND_URL}/call-logs",
            json=payload,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            print(f"  ✅ {response.status_code} - '{field_name}' added successfully")
        else:
            print(f"  ❌ {response.status_code} - '{field_name}' caused error!")
            print(f"  Response: {response.text[:200]}")
            break
            
    except Exception as e:
        print(f"  ❌ Exception with '{field_name}': {e}")
        break

print("\n" + "=" * 70)
