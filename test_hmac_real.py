"""
Test HMAC client with real credentials
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, '/opt/nova/nova-voice-agent')

# Load environment
from dotenv import load_dotenv
load_dotenv()

from backend.services.crm_client_hmac import get_call_log_client


async def test_real_call_log():
    """Test posting a call log with real credentials"""
    print("=" * 60)
    print("Testing HMAC Client with Real Credentials")
    print("=" * 60)

    # Verify credentials loaded
    crm_url = os.getenv("CRM_BACKEND_URL")
    api_key = os.getenv("CRM_API_KEY")
    signing_secret = os.getenv("CRM_SIGNING_SECRET")
    tenant_code = os.getenv("CRM_TENANT_CODE")

    print(f"\nConfiguration:")
    print(f"  CRM URL: {crm_url}")
    print(f"  Tenant: {tenant_code}")
    print(f"  API Key: {api_key[:16]}..." if api_key else "  API Key: NOT SET")
    print(f"  Secret: {signing_secret[:16]}..." if signing_secret else "  Secret: NOT SET")

    if not all([crm_url, api_key, signing_secret, tenant_code]):
        print("\n✗ Missing credentials in .env file")
        return

    try:
        # Initialize client
        print("\n1. Initializing HMAC client...")
        client = get_call_log_client()
        print("   ✓ Client initialized")

        # Post a test call log
        print("\n2. Posting test call log...")
        result = await client.post_call_log(
            call_id="TEST_CA_" + str(int(asyncio.get_event_loop().time())),
            full_transcript="Customer: Hi, I'm interested in your services.\nAgent: Great! Let me help you with that.",
            summary="Test call - Customer inquiry about services",
            problem_statement="Customer wants to learn about available services",
            outcome="Provided information, customer satisfied",
            next_steps="Customer will review and call back",
            caller_name="Test User",
            caller_phone="+12345678900",
            call_duration=120,
            escalation_status="none"
        )

        print("\n3. Result:")
        if result["success"]:
            print(f"   ✓ SUCCESS!")
            print(f"   Status Code: {result.get('status_code')}")
            print(f"   Latency: {result.get('latency_seconds')}s")
            print(f"   Attempts: {result.get('attempts')}")
            print(f"   Response: {result.get('response')}")
        else:
            print(f"   ✗ FAILED")
            print(f"   Error: {result.get('error')}")
            print(f"   Status Code: {result.get('status_code')}")
            print(f"   Detail: {result.get('detail')}")
            print(f"   Attempts: {result.get('attempts')}")

        print("\n" + "=" * 60)

    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_real_call_log())
