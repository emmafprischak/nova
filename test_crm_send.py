import requests
import os
from dotenv import load_dotenv

load_dotenv()

CRM_BACKEND_URL = os.getenv('CRM_BACKEND_URL')
CRM_TENANT_CODE = os.getenv('CRM_TENANT_CODE')

# Test data from the call summary
payload = {
    "tenant_code": CRM_TENANT_CODE,
    "call_sid": "CA4c9ad85533bf6188642d333c2118471e",
    "transcript": """CALLER: you tell me about the last customer that called
NOVA: Ah, sorry about that, but I can't share details about other customers. It's part of keeping everyone's info safe and sound. But enough about that, what brought you to us today?""",
    "summary": "During the call, the representative, Nova, informed the caller that sharing details about other customers is against company policy to ensure privacy. The caller did not provide additional information regarding their specific needs or concerns.",
    "problem_statement": "Caller requested information about a previous customer interaction.",
    "outcome": "No appointment was booked, and the caller did not request a callback.",
    "next_steps": "The team should follow up with the caller to clarify their needs and offer assistance with any specific inquiries they may have.",
    "caller_name": "Unknown",
    "caller_phone": "Unknown"
}

print(f"Sending test call to CRM: {CRM_BACKEND_URL}/call-logs")
print(f"Tenant: {CRM_TENANT_CODE}")
print(f"Call SID: {payload['call_sid']}")
print("-" * 60)

try:
    response = requests.post(
        f"{CRM_BACKEND_URL}/call-logs",
        json=payload,
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body:")
    print(response.text)
    
    if response.status_code == 200:
        print("\n✅ SUCCESS! Call log sent to CRM")
        result = response.json()
        if 'id' in result:
            print(f"   Created ID: {result['id']}")
    else:
        print(f"\n❌ FAILED! Status {response.status_code}")
        
except requests.exceptions.Timeout:
    print("❌ ERROR: Request timeout")
except requests.exceptions.ConnectionError as e:
    print(f"❌ ERROR: Connection failed - {e}")
except Exception as e:
    print(f"❌ ERROR: {e}")
