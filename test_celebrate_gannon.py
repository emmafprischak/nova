"""
Test HMAC client with celebrate_gannon tenant
"""
import asyncio
import sys
sys.path.insert(0, '/opt/nova/nova-voice-agent')

from backend.services.crm_client_hmac import CallLogClient
from datetime import datetime, timezone


async def test_celebrate_gannon():
    """Test posting a call log for celebrate_gannon tenant"""
    print("=" * 70)
    print("Testing HMAC Client - Celebrate Gannon Tenant")
    print("=" * 70)

    # Hardcoded credentials for testing
    crm_url = "https://crm-backend-8b97.onrender.com"
    api_key = "vai_DaLfrOsAeRU2LCPAxUIhzcC0FqkQ_FyP"
    signing_secret = "meXMVcjn-UkJEjkcRQ3UgSHBpBTfHeBs5QYFApg_peUoEmGXTPwlw6tkKanA6ydx"
    tenant_code = "celebrate_gannon"

    print(f"\nConfiguration:")
    print(f"  CRM URL: {crm_url}")
    print(f"  Tenant: {tenant_code}")
    print(f"  API Key: {api_key[:20]}...")
    print(f"  Secret: {signing_secret[:20]}...")

    try:
        # Initialize client
        print("\n" + "=" * 70)
        print("Step 1: Initializing HMAC client")
        print("=" * 70)
        client = CallLogClient(
            base_url=crm_url,
            api_key=api_key,
            signing_secret=signing_secret,
            tenant_code=tenant_code
        )
        print("✓ Client initialized successfully")

        # Create test call log
        test_call_id = f"TEST_CELEBRATE_{int(datetime.now(timezone.utc).timestamp())}"

        print("\n" + "=" * 70)
        print("Step 2: Posting test call log")
        print("=" * 70)
        print(f"  Call ID: {test_call_id}")

        result = await client.post_call_log(
            call_id=test_call_id,
            full_transcript=(
                "Customer: Hi, I'm calling about Celebrate Gannon services.\n"
                "Agent: Great! I'd be happy to help. What specifically are you interested in?\n"
                "Customer: I need information about your AI voice services.\n"
                "Agent: Perfect! Let me get some details and we can schedule a consultation."
            ),
            summary="Celebrate Gannon customer inquiry about AI voice services",
            problem_statement="Customer wants to learn about AI voice agent capabilities",
            outcome="Customer interested in consultation",
            next_steps="Customer will schedule follow-up call",
            caller_name="Test User - Celebrate Gannon",
            caller_phone="+12345678900",
            call_duration=145,
            escalation_status="none"
        )

        print("\n" + "=" * 70)
        print("Step 3: Result")
        print("=" * 70)

        if result["success"]:
            print("✓ SUCCESS! Call log posted successfully")
            print(f"\n  Response Details:")
            print(f"    Status Code: {result.get('status_code')}")
            print(f"    Latency: {result.get('latency_seconds'):.3f}s")
            print(f"    Attempts: {result.get('attempts')}")
            if result.get('response'):
                print(f"    Server Response: {result.get('response')}")

            print("\n" + "=" * 70)
            print("✅ TEST PASSED")
            print("=" * 70)
            print("\nThe celebrate_gannon tenant is configured correctly!")
            print("HMAC authentication is working properly.")

        else:
            print("✗ FAILED to post call log")
            print(f"\n  Error Details:")
            print(f"    Error: {result.get('error')}")
            print(f"    Status Code: {result.get('status_code')}")
            print(f"    Attempts: {result.get('attempts')}")
            if result.get('detail'):
                print(f"    Detail: {result.get('detail')}")

            print("\n" + "=" * 70)
            print("❌ TEST FAILED")
            print("=" * 70)

            # Provide troubleshooting hints
            status_code = result.get('status_code')
            if status_code == 401:
                print("\nTroubleshooting: Authentication failed")
                print("  - Check API key is correct")
                print("  - Check signing secret is correct")
                print("  - Verify HMAC signature algorithm matches server")
            elif status_code == 403:
                print("\nTroubleshooting: Tenant mismatch")
                print("  - Verify tenant_code 'celebrate_gannon' is configured on server")
                print("  - Check integration tenant mapping")
            elif status_code == 422:
                print("\nTroubleshooting: Validation error")
                print("  - Check required fields: tenant_code, full_transcript")
                print("  - Verify payload schema matches server expectations")

    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_celebrate_gannon())
