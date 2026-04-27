"""
Standalone test for HMAC signing (no dependencies)
"""
import hmac
import hashlib
import json
import time


def sign_request(timestamp: str, raw_body_bytes: bytes, signing_secret: str) -> str:
    """Generate HMAC-SHA256 signature"""
    message = f"{timestamp}.".encode('utf-8') + raw_body_bytes
    signature = hmac.new(
        signing_secret.encode('utf-8'),
        message,
        hashlib.sha256
    ).hexdigest()
    return signature


def test_signing():
    """Test HMAC signing with known values"""
    print("=" * 60)
    print("HMAC Signing Test")
    print("=" * 60)

    # Test 1: Basic signing
    timestamp = "1714089600"
    body = {"tenant_code": "walmart", "full_transcript": "Hello world"}
    raw_body_bytes = json.dumps(body, separators=(',', ':')).encode('utf-8')
    signing_secret = "test_secret_key"

    signature = sign_request(timestamp, raw_body_bytes, signing_secret)

    print(f"\nTest 1: Basic Signing")
    print(f"  Timestamp: {timestamp}")
    print(f"  Body: {body}")
    print(f"  Body bytes: {raw_body_bytes}")
    print(f"  Secret: {signing_secret}")
    print(f"  Signature: {signature}")
    print(f"  Length: {len(signature)} chars")

    # Verify deterministic
    signature2 = sign_request(timestamp, raw_body_bytes, signing_secret)
    assert signature == signature2
    print("  ✓ Signature is deterministic")

    # Test 2: Different timestamp = different signature
    timestamp2 = "1714089601"
    signature3 = sign_request(timestamp2, raw_body_bytes, signing_secret)
    assert signature != signature3
    print(f"\nTest 2: Timestamp Sensitivity")
    print(f"  Original timestamp: {timestamp}")
    print(f"  New timestamp: {timestamp2}")
    print(f"  Original signature: {signature[:32]}...")
    print(f"  New signature: {signature3[:32]}...")
    print("  ✓ Different timestamps produce different signatures")

    # Test 3: Different body = different signature
    body2 = {"tenant_code": "walmart", "full_transcript": "Different text"}
    raw_body_bytes2 = json.dumps(body2, separators=(',', ':')).encode('utf-8')
    signature4 = sign_request(timestamp, raw_body_bytes2, signing_secret)
    assert signature != signature4
    print(f"\nTest 3: Body Sensitivity")
    print(f"  Original body: {body}")
    print(f"  New body: {body2}")
    print(f"  Original signature: {signature[:32]}...")
    print(f"  New signature: {signature4[:32]}...")
    print("  ✓ Different bodies produce different signatures")

    # Test 4: Canonical JSON (order doesn't matter)
    body_ordered1 = {"tenant_code": "walmart", "full_transcript": "Test"}
    body_ordered2 = {"full_transcript": "Test", "tenant_code": "walmart"}
    bytes1 = json.dumps(body_ordered1, separators=(',', ':')).encode('utf-8')
    bytes2 = json.dumps(body_ordered2, separators=(',', ':')).encode('utf-8')

    # Note: Python dict maintains insertion order (3.7+), so these will be different
    # In production, always serialize from the same dict to maintain consistency
    print(f"\nTest 4: JSON Serialization")
    print(f"  Body 1 bytes: {bytes1}")
    print(f"  Body 2 bytes: {bytes2}")
    if bytes1 == bytes2:
        print("  ✓ JSON order preserved (Python 3.7+)")
    else:
        print("  ! Different key order produces different bytes")
        print("  → Use same dict for signing and sending!")

    # Test 5: Realistic payload
    current_timestamp = str(int(time.time()))
    realistic_payload = {
        "tenant_code": "walmart",
        "full_transcript": "Customer: Hello, I need help.\nAgent: How can I help you today?",
        "summary": "Customer inquiry about services",
        "problem_statement": "Needs information",
        "outcome": "Scheduled consultation",
        "caller_name": "John Doe",
        "caller_phone": "+12345678900",
        "call_duration": 180,
        "escalation_status": "none",
        "timestamp": "2024-04-25T14:30:00Z"
    }
    realistic_bytes = json.dumps(realistic_payload, separators=(',', ':')).encode('utf-8')
    realistic_signature = sign_request(current_timestamp, realistic_bytes, signing_secret)

    print(f"\nTest 5: Realistic Payload")
    print(f"  Timestamp: {current_timestamp}")
    print(f"  Payload size: {len(realistic_bytes)} bytes")
    print(f"  Signature: {realistic_signature}")
    print("  ✓ Successfully signed realistic payload")

    # Test 6: Create full auth headers
    print(f"\nTest 6: Complete Auth Headers")
    headers = {
        "X-Voice-Agent-Key": "api_key_12345678",
        "X-Voice-Agent-Timestamp": current_timestamp,
        "X-Voice-Agent-Signature": realistic_signature,
        "Content-Type": "application/json"
    }
    for key, value in headers.items():
        if key == "X-Voice-Agent-Signature":
            print(f"  {key}: {value[:32]}...")
        else:
            print(f"  {key}: {value}")
    print("  ✓ Auth headers created")

    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED")
    print("=" * 60)

    # Summary
    print("\nImplementation Summary:")
    print("  1. Signing algorithm: HMAC-SHA256")
    print("  2. Message format: '{timestamp}.{json_body_bytes}'")
    print("  3. Output format: Hex string (64 chars)")
    print("  4. Security: Timestamp prevents replay attacks")
    print("  5. Canonical JSON: Use same bytes for sign + send")
    print()
    print("Server Verification:")
    print("  1. Extract timestamp, signature from headers")
    print("  2. Read raw request body bytes")
    print("  3. Recompute: HMAC(secret, '{timestamp}.{body}')")
    print("  4. Compare computed vs received signature")
    print("  5. Verify timestamp within 5min window")
    print()


if __name__ == "__main__":
    test_signing()
