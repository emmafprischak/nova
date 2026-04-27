"""
HMAC-Authenticated CRM Client with Retry Logic
Robust service-to-service client for posting call logs
"""
import httpx
import json
import asyncio
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from backend.services.logger import StructuredLogger, set_trace_id
from backend.services.hmac_auth import create_auth_headers
from backend.config import CRM_BACKEND_URL, CRM_TENANT_CODE
import os

logger = StructuredLogger(__name__)

# HMAC credentials from environment
CRM_API_KEY = os.getenv("CRM_API_KEY", "")
CRM_SIGNING_SECRET = os.getenv("CRM_SIGNING_SECRET", "")

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 10.0
TIMEOUT_SECONDS = 30.0


class CallLogClient:
    """
    Resilient HTTP client for posting call logs with HMAC authentication.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        signing_secret: str,
        tenant_code: str
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.signing_secret = signing_secret
        self.tenant_code = tenant_code

        # Validate HTTPS enforcement
        if not self.base_url.startswith("https://"):
            logger.error("CRM endpoint must use HTTPS", url=self.base_url)
            raise ValueError(f"CRM endpoint must use HTTPS: {self.base_url}")

    async def post_call_log(
        self,
        call_id: str,
        full_transcript: str,
        summary: Optional[str] = None,
        problem_statement: Optional[str] = None,
        outcome: Optional[str] = None,
        next_steps: Optional[str] = None,
        caller_name: Optional[str] = None,
        caller_phone: Optional[str] = None,
        call_duration: Optional[int] = None,
        escalation_status: Optional[str] = None,
        timestamp: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Post call log to CRM backend with HMAC authentication and retry logic.

        Args:
            call_id: Unique call identifier (e.g., Twilio CallSid)
            full_transcript: Full conversation transcript (required)
            summary: Call summary
            problem_statement: Identified problem
            outcome: Call outcome
            next_steps: Recommended next steps
            caller_name: Caller's name
            caller_phone: Caller's phone number
            call_duration: Call duration in seconds
            escalation_status: Escalation status
            timestamp: ISO8601 timestamp (defaults to now)
            request_id: Idempotency key (defaults to UUID)

        Returns:
            Dictionary with success status and response/error details
        """
        # Generate request ID for tracing and idempotency
        if not request_id:
            request_id = str(uuid.uuid4())

        # Set trace ID for structured logging
        set_trace_id(request_id)

        # Build payload matching server schema
        payload = {
            "tenant_code": self.tenant_code,
            "full_transcript": full_transcript
        }

        # Add optional fields
        if summary:
            payload["summary"] = summary
        if problem_statement:
            payload["problem_statement"] = problem_statement
        if outcome:
            payload["outcome"] = outcome
        if next_steps:
            payload["next_steps"] = next_steps
        if caller_name:
            payload["caller_name"] = caller_name
        if caller_phone:
            payload["caller_phone"] = caller_phone
        if call_duration is not None:
            payload["call_duration"] = call_duration
        if escalation_status:
            payload["escalation_status"] = escalation_status
        if timestamp:
            payload["timestamp"] = timestamp
        else:
            payload["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        logger.info(
            "Posting call log to CRM",
            call_id=call_id,
            request_id=request_id,
            tenant_code=self.tenant_code,
            has_summary=bool(summary),
            has_transcript=bool(full_transcript)
        )

        # Serialize JSON once to ensure canonical body
        raw_body_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')

        # Create HMAC authentication headers
        headers = create_auth_headers(
            self.api_key,
            self.signing_secret,
            raw_body_bytes
        )

        # Add request ID header for tracing
        headers["X-Request-ID"] = request_id

        # Attempt request with retry logic
        return await self._post_with_retry(
            endpoint="/public/call-logs/",
            raw_body_bytes=raw_body_bytes,
            headers=headers,
            call_id=call_id,
            request_id=request_id
        )

    async def _post_with_retry(
        self,
        endpoint: str,
        raw_body_bytes: bytes,
        headers: dict,
        call_id: str,
        request_id: str
    ) -> Dict[str, Any]:
        """
        Execute POST request with exponential backoff retry for transient failures.

        Retries only on:
        - 5xx server errors
        - Network/timeout errors

        Does NOT retry on:
        - 401 (authentication failure)
        - 403 (forbidden - tenant mismatch)
        - 422 (validation error)
        """
        url = f"{self.base_url}{endpoint}"
        retry_delay = INITIAL_RETRY_DELAY
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                start_time = asyncio.get_event_loop().time()

                async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                    response = await client.post(
                        url,
                        content=raw_body_bytes,  # Use exact bytes for HMAC consistency
                        headers=headers
                    )

                latency = asyncio.get_event_loop().time() - start_time

                # Log request metrics
                logger.info(
                    "CRM request completed",
                    call_id=call_id,
                    request_id=request_id,
                    status_code=response.status_code,
                    latency_seconds=round(latency, 3),
                    attempt=attempt + 1
                )

                # Handle success (200)
                if response.status_code == 200:
                    result = response.json() if response.text else {}
                    logger.info(
                        "Call log posted successfully",
                        call_id=call_id,
                        request_id=request_id,
                        response=result
                    )
                    return {
                        "success": True,
                        "response": result,
                        "status_code": 200,
                        "attempts": attempt + 1,
                        "latency_seconds": latency
                    }

                # Handle client errors (4xx) - DO NOT RETRY
                if 400 <= response.status_code < 500:
                    error_detail = response.text

                    if response.status_code == 401:
                        logger.error(
                            "CRM authentication failed",
                            call_id=call_id,
                            request_id=request_id,
                            status_code=401,
                            error=error_detail
                        )
                        return {
                            "success": False,
                            "error": "Authentication failed - invalid key/signature",
                            "status_code": 401,
                            "detail": error_detail,
                            "attempts": attempt + 1
                        }

                    if response.status_code == 403:
                        logger.error(
                            "CRM tenant mismatch",
                            call_id=call_id,
                            request_id=request_id,
                            status_code=403,
                            tenant_code=self.tenant_code,
                            error=error_detail
                        )
                        return {
                            "success": False,
                            "error": "Tenant code mismatch",
                            "status_code": 403,
                            "detail": error_detail,
                            "attempts": attempt + 1
                        }

                    if response.status_code == 422:
                        logger.error(
                            "CRM validation failed",
                            call_id=call_id,
                            request_id=request_id,
                            status_code=422,
                            error=error_detail
                        )
                        return {
                            "success": False,
                            "error": "Validation error - check required fields",
                            "status_code": 422,
                            "detail": error_detail,
                            "attempts": attempt + 1
                        }

                    # Other 4xx errors
                    logger.error(
                        "CRM client error",
                        call_id=call_id,
                        request_id=request_id,
                        status_code=response.status_code,
                        error=error_detail
                    )
                    return {
                        "success": False,
                        "error": f"Client error {response.status_code}",
                        "status_code": response.status_code,
                        "detail": error_detail,
                        "attempts": attempt + 1
                    }

                # Handle server errors (5xx) - RETRY
                if response.status_code >= 500:
                    last_error = f"Server error {response.status_code}"
                    logger.warning(
                        "CRM server error - will retry",
                        call_id=call_id,
                        request_id=request_id,
                        status_code=response.status_code,
                        attempt=attempt + 1,
                        max_attempts=MAX_RETRIES + 1,
                        retry_in_seconds=retry_delay if attempt < MAX_RETRIES else None
                    )

            except httpx.TimeoutException as e:
                last_error = f"Request timeout after {TIMEOUT_SECONDS}s"
                logger.warning(
                    "CRM request timeout - will retry",
                    call_id=call_id,
                    request_id=request_id,
                    attempt=attempt + 1,
                    max_attempts=MAX_RETRIES + 1,
                    retry_in_seconds=retry_delay if attempt < MAX_RETRIES else None,
                    error=str(e)
                )

            except (httpx.NetworkError, httpx.ConnectError) as e:
                last_error = f"Network error: {str(e)}"
                logger.warning(
                    "CRM network error - will retry",
                    call_id=call_id,
                    request_id=request_id,
                    attempt=attempt + 1,
                    max_attempts=MAX_RETRIES + 1,
                    retry_in_seconds=retry_delay if attempt < MAX_RETRIES else None,
                    error=str(e)
                )

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(
                    "CRM unexpected error",
                    call_id=call_id,
                    request_id=request_id,
                    attempt=attempt + 1,
                    error=str(e)
                )
                return {
                    "success": False,
                    "error": last_error,
                    "attempts": attempt + 1
                }

            # Retry with exponential backoff (if not last attempt)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
            else:
                # All retries exhausted
                logger.error(
                    "CRM request failed after all retries",
                    call_id=call_id,
                    request_id=request_id,
                    attempts=attempt + 1,
                    last_error=last_error
                )
                return {
                    "success": False,
                    "error": f"Failed after {attempt + 1} attempts: {last_error}",
                    "attempts": attempt + 1
                }

        # Should never reach here
        return {
            "success": False,
            "error": "Maximum retries exceeded",
            "attempts": MAX_RETRIES + 1
        }


# Singleton instance
_call_log_client: Optional[CallLogClient] = None


def get_call_log_client() -> CallLogClient:
    """
    Get or create singleton CallLogClient instance.

    Raises:
        ValueError: If required credentials are missing
    """
    global _call_log_client

    if _call_log_client is None:
        if not CRM_BACKEND_URL:
            raise ValueError("CRM_BACKEND_URL not configured")
        if not CRM_API_KEY:
            raise ValueError("CRM_API_KEY not configured")
        if not CRM_SIGNING_SECRET:
            raise ValueError("CRM_SIGNING_SECRET not configured")
        if not CRM_TENANT_CODE:
            raise ValueError("CRM_TENANT_CODE not configured")

        _call_log_client = CallLogClient(
            base_url=CRM_BACKEND_URL,
            api_key=CRM_API_KEY,
            signing_secret=CRM_SIGNING_SECRET,
            tenant_code=CRM_TENANT_CODE
        )

        logger.info(
            "Initialized HMAC-authenticated CRM client",
            base_url=CRM_BACKEND_URL,
            tenant_code=CRM_TENANT_CODE,
            api_key_prefix=CRM_API_KEY[:8] + "..." if len(CRM_API_KEY) > 8 else "***"
        )

    return _call_log_client
