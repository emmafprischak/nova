import requests
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

CRM_BACKEND_URL = os.getenv('CRM_BACKEND_URL')
CRM_TENANT_CODE = os.getenv('CRM_TENANT_CODE')

# Minimal payload - just the essentials
payload = {
    "tenant_code": CRM_TENANT_CODE,
    "caller_name": "John Doe",
    "caller_phone": "+15551234567",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
}

print("=" * 70)
print("CRM /call-logs MINIMAL TEST")
print("=" * 70)
print(f"URL: {CRM_BACKEND_URL}/call-logs")
print(f"Minimal payload (4 fields):")
for key, val in payload.items():
    print(f"  - {key}: {val}")
print("=" * 70)

try:
    print("\nSending minimal request...")
    response = requests.post(
        f"{CRM_BACKEND_URL}/call-logs",
        json=payload,
        timeout=30
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response:")
    print("-" * 70)
    try:
        import json
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
    print("-" * 70)
    
    if response.status_code == 200 or response.status_code == 201:
        print("\n✅ SUCCESS with minimal payload!")
    elif response.status_code == 422:
        print("\n⚠️  422 Validation Error - missing required fields")
    else:
        print(f"\n❌ Error: {response.status_code}")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
