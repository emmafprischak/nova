"""
HMAC Request Signing Utilities
Provides cryptographic signing for service-to-service authentication
"""
import hmac
import hashlib
import time
from typing import Tuple
from backend.services.logger import StructuredLogger

logger = StructuredLogger(__name__)


def sign_request(timestamp: str, raw_body_bytes: bytes, signing_secret: str) -> str:
    """
    Generate HMAC-SHA256 signature for request authentication.

    Args:
        timestamp: Unix timestamp in seconds (as string)
        raw_body_bytes: Exact JSON body bytes that will be sent over HTTP
        signing_secret: Secret key for HMAC signing

    Returns:
        Hex-encoded HMAC signature

    Algorithm:
        signature = HMAC_SHA256(signing_secret, "{timestamp}.{raw_body_bytes}")
    """
    # Construct canonical string: timestamp + "." + body
    message = f"{timestamp}.".encode('utf-8') + raw_body_bytes

    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        signing_secret.encode('utf-8'),
        message,
        hashlib.sha256
    ).hexdigest()

    return signature


def get_current_timestamp() -> str:
    """
    Get current Unix timestamp in seconds as string.

    Returns:
        Current timestamp (e.g., "1714089600")
    """
    return str(int(time.time()))


def verify_timestamp_window(timestamp: str, max_age_seconds: int = 300) -> Tuple[bool, str]:
    """
    Verify timestamp is within acceptable window (default 5 minutes).
    Helps prevent replay attacks.

    Args:
        timestamp: Unix timestamp to verify
        max_age_seconds: Maximum age in seconds (default 300 = 5 minutes)

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        request_time = int(timestamp)
        current_time = int(time.time())
        age = abs(current_time - request_time)

        if age > max_age_seconds:
            return False, f"Timestamp too old: {age}s (max {max_age_seconds}s)"

        return True, ""
    except (ValueError, TypeError) as e:
        return False, f"Invalid timestamp format: {e}"


def create_auth_headers(
    api_key: str,
    signing_secret: str,
    raw_body_bytes: bytes
) -> dict:
    """
    Create authentication headers for HMAC-authenticated requests.

    Args:
        api_key: Integration API key
        signing_secret: Secret for HMAC signing
        raw_body_bytes: Exact JSON body bytes

    Returns:
        Dictionary of authentication headers
    """
    timestamp = get_current_timestamp()
    signature = sign_request(timestamp, raw_body_bytes, signing_secret)

    headers = {
        "X-Voice-Agent-Key": api_key,
        "X-Voice-Agent-Timestamp": timestamp,
        "X-Voice-Agent-Signature": signature,
        "Content-Type": "application/json"
    }

    # Log header creation (redact secrets)
    logger.debug(
        "Created HMAC auth headers",
        api_key_prefix=api_key[:8] + "..." if len(api_key) > 8 else "***",
        timestamp=timestamp,
        signature_prefix=signature[:16] + "...",
        body_size=len(raw_body_bytes)
    )

    return headers
