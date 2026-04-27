import requests
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

CRM_BACKEND_URL = os.getenv('CRM_BACKEND_URL')
CRM_TENANT_CODE = os.getenv('CRM_TENANT_CODE')

# Test with just required fields
payload = {
    "tenant_code": CRM_TENANT_CODE,
    "caller_name": "John Doe",
    "caller_phone": "+15551234567",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "full_transcript": "Test transcript"
}

print("Testing with required fields only...")
print(f"Payload: {payload}")

response = requests.post(f"{CRM_BACKEND_URL}/call-logs", json=payload, timeout=30)
print(f"\nStatus: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code in [200, 201]:
    print("\n✅ SUCCESS!")
elif response.status_code == 422:
    print("\n⚠️ More required fields needed")
else:
    print(f"\n❌ Error {response.status_code}")
