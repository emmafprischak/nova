import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

CRM_BACKEND_URL = os.getenv('CRM_BACKEND_URL')
CRM_TENANT_CODE = os.getenv('CRM_TENANT_CODE')

# Test data from the call summary
payload = {
    "tenant_code": CRM_TENANT_CODE,
    "call_sid": "CA4c9ad85533bf6188642d333c2118471e",
    "full_transcript": """CALLER: you tell me about the last customer that called
NOVA: Ah, sorry about that, but I can't share details about other customers. It's part of keeping everyone's info safe and sound. But enough about that, what brought you to us today?""",
    "summary": "During the call, the representative, Nova, informed the caller that sharing details about other customers is against company policy to ensure privacy. The caller did not provide additional information regarding their specific needs or concerns.",
    "problem_statement": "Caller requested information about a previous customer interaction.",
    "outcome": "No appointment was booked, and the caller did not request a callback.",
    "next_steps": "The team should follow up with the caller to clarify their needs and offer assistance with any specific inquiries they may have.",
    "caller_name": "Unknown",
    "caller_phone": "Unknown"
}

print("="*70)
print("CRM /call-logs ENDPOINT TEST")
print("="*70)
print(f"URL: {CRM_BACKEND_URL}/call-logs")
print(f"Tenant: {CRM_TENANT_CODE}")
print(f"Call SID: {payload['call_sid']}")
print("="*70)

# First, let's check if the server is reachable
print("\n[1/3] Testing if CRM backend is reachable...")
try:
    start = time.time()
    response = requests.get(f"{CRM_BACKEND_URL}/", timeout=30)
    elapsed = time.time() - start
    print(f"    ✅ Server is UP! (responded in {elapsed:.2f}s)")
    print(f"    Status: {response.status_code}")
except requests.exceptions.Timeout:
    print("    ❌ Server timeout (might be sleeping on Render)")
except Exception as e:
    print(f"    ⚠️  Error: {e}")

# Now test the /call-logs endpoint
print("\n[2/3] Sending POST request to /call-logs...")
print(f"    Payload size: {len(str(payload))} bytes")
print(f"    Timeout: 60 seconds")

try:
    start = time.time()
    response = requests.post(
        f"{CRM_BACKEND_URL}/call-logs",
        json=payload,
        timeout=60
    )
    elapsed = time.time() - start
    
    print(f"    Response time: {elapsed:.2f}s")
    print(f"    Status Code: {response.status_code}")
    print(f"    Headers: {dict(response.headers)}")
    
    print("\n[3/3] Response Body:")
    print("-" * 70)
    try:
        print(response.json())
    except:
        print(response.text[:500])
    print("-" * 70)
    
    if response.status_code == 200 or response.status_code == 201:
        print("\n✅ SUCCESS! Call log sent to CRM")
    else:
        print(f"\n⚠️  Non-200 response: {response.status_code}")
        
except requests.exceptions.Timeout:
    print(f"    ❌ Request timeout after 60 seconds")
    print("    This likely means:")
    print("       - The endpoint doesn't exist")
    print("       - The server is processing but taking too long")
    print("       - Render free tier is cold-starting (can take 30-60s)")
except requests.exceptions.ConnectionError as e:
    print(f"    ❌ Connection error: {e}")
except Exception as e:
    print(f"    ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("Test complete. Check your CRM backend to verify the endpoint.")
print("="*70)
