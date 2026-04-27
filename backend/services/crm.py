"""
CRM Service - Integrates with Notion database and CRM backend
"""
import hashlib
import hmac
import httpx
import json
import logging
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_API_URL, CRM_BACKEND_URL, CRM_TENANT_CODE
from models import CallData
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.tenant_registry import TenantRegistryManager

logger = logging.getLogger(__name__)

# Module-level reference to the TenantRegistryManager, set during app startup.
# When None, CRM requests are sent without per-tenant HMAC authentication.
registry_manager: Optional["TenantRegistryManager"] = None


def _build_voice_agent_headers(tenant_code: str, body_bytes: bytes) -> dict:
    """
    Build authenticated request headers for the CRM voice-agent endpoints.

    Uses the per-tenant credentials from the registry manager to construct an
    HMAC-SHA256 signature that the CRM backend can verify.

    Args:
        tenant_code: Identifies the tenant whose credentials to use.
        body_bytes:  The serialised JSON request body (used in the signature).

    Returns:
        A dict with ``Content-Type`` and, when credentials are available,
        ``X-Voice-Agent-Key``, ``X-Voice-Agent-Timestamp``, and
        ``X-Voice-Agent-Signature`` headers.
    """
    headers = {"Content-Type": "application/json"}

    if registry_manager is None:
        return headers

    creds = registry_manager.get_tenant_credentials(tenant_code)
    if not creds:
        logger.warning(
            "No registry credentials found for tenant '%s'; sending unauthenticated request",
            tenant_code,
        )
        return headers

    timestamp = str(int(time.time()))
    payload = f"{timestamp}.".encode("utf-8") + body_bytes
    signature = hmac.new(
        creds["signing_secret"].encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    headers["X-Voice-Agent-Key"] = creds["api_key"]
    headers["X-Voice-Agent-Timestamp"] = timestamp
    headers["X-Voice-Agent-Signature"] = signature
    return headers

async def create_lead(call_data: CallData, call_sid: str) -> dict:
    """Create a new lead entry in Notion"""
    try:
        url = f"{NOTION_API_URL}/pages"

        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

        properties = {
            "Name": {
                "title": [{"text": {"content": call_data.name or "Unknown"}}]
            },
            "Phone_Number": {
                "phone_number": call_data.phone or ""
            },
            "Email": {
                "email": call_data.email or ""
            },
            "service": {
                "rich_text": [{"text": {"content": call_data.service or ""}}]
            },
            "status": {
                "select": {"name": call_data.status}
            },
            "Date": {
                "date": {"start": datetime.now().isoformat()}
            },
            "notes": {
                "rich_text": [{
                    "text": {
                        "content": f"Call SID: {call_sid}\n{call_data.notes}"
                    }
                }]
            }
        }

        if call_data.appointment_time:
            properties["notes"]["rich_text"][0]["text"]["content"] += f"\nAppointment: {call_data.appointment_time}"

        data = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": properties
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)

            if response.status_code != 200:
                error_detail = response.text
                print(f"Notion API Error {response.status_code}:")
                print(f"Response: {error_detail}")
                return {"success": False, "error": error_detail}

            result = response.json()

            print(f"Notion lead created!")
            return {
                "success": True,
                "page_id": result.get("id"),
                "url": result.get("url")
            }

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if hasattr(e, 'response') else str(e)
        print(f"Notion HTTP error: {e}")
        print(f"Response body: {error_detail}")
        return {"success": False, "error": error_detail}
    except Exception as e:
        print(f"Notion error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def determine_escalation_status(call_data: CallData, summary: str | None = None) -> str:
    """
    Determine the escalation status for a call based on the call outcome and summary.

    Escalation statuses:
    - "none"      — successful booking or completed call with no issues
    - "pending"   — booking failed or caller requested a callback (needs follow-up)
    - "escalated" — call was transferred to a human agent
    - "resolved"  — issue resolved after escalation

    Args:
        call_data: The call data object with status and other fields.
        summary: Optional AI-generated call summary text for keyword detection.

    Returns:
        A string escalation status: "none", "pending", "escalated", or "resolved".
    """
    status = (call_data.status or "").lower()

    # Directly escalated statuses
    if status in ("needs_human", "escalated"):
        return "escalated"

    # Resolved after escalation
    if status == "resolved":
        return "resolved"

    # Pending/callback statuses — needs follow-up
    if status in ("needs_callback", "pending", "failed", "no_booking", "cancelled"):
        return "pending"

    # Successful booking — no escalation needed
    if status in ("booked", "qualified"):
        return "none"

    # Fall back to keyword detection in the summary if status is ambiguous
    if summary:
        summary_lower = summary.lower()
        pending_keywords = ("callback", "call back", "follow-up", "follow up", "no booking", "unable to book", "failed")
        escalation_keywords = ("escalat", "transfer", "human agent", "supervisor", "needs_human")
        resolved_keywords = ("resolved", "issue resolved")

        if any(kw in summary_lower for kw in resolved_keywords):
            return "resolved"
        # Check pending before escalation so "callback" phrases are not mis-classified
        if any(kw in summary_lower for kw in pending_keywords):
            return "pending"
        if any(kw in summary_lower for kw in escalation_keywords):
            return "escalated"

    # Default: no escalation
    return "none"


async def push_to_crm_backend(
    call_data: CallData,
    call_sid: str = None,
    summary: str = None,
    escalation_status: str | None = None,
    timestamp: str | None = None,
) -> dict:
    """
    Push contact/call data to the public CRM endpoint.

    The new endpoint expects only contact basics plus the tenant code:
    POST {base_url}/public/submit-contact
    Body: {"name", "email", "phone", "tenant_code", "summary",
           "escalation_status", "timestamp"}

    If escalation_status is not provided, it is determined automatically from
    call_data.status and the summary text via determine_escalation_status().
    """
    if not CRM_BACKEND_URL:
        logger.warning("CRM backend URL not configured (CRM_BACKEND_URL missing), skipping push")
        return {"success": False, "error": "CRM backend URL not configured"}
    try:
        url = f"{CRM_BACKEND_URL.rstrip('/')}/public/submit-contact"

        headers = {
            "Content-Type": "application/json"
        }

        # Resolve escalation status automatically when not supplied by caller
        effective_escalation_status = escalation_status if escalation_status is not None else determine_escalation_status(call_data, summary)

        # Resolve tenant code: prefer per-call value, fall back to global config
        tenant_code = call_data.tenant_code or CRM_TENANT_CODE

        # Minimal payload required by the public submit-contact endpoint
        payload = {
            "name": call_data.name or "Unknown",
            "email": call_data.email or "novaisnotworking@orbyn.ai",
            "phone": call_data.phone or "(555)555-5555",
            "tenant_code": tenant_code,
            "summary": summary or "",
            "escalation_status": effective_escalation_status,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        # Include extra context in optional notes field if accepted by backend
        # but keep the primary contract minimal to avoid schema mismatches.
        if call_data.notes:
            payload["notes"] = call_data.notes
        if call_sid:
            payload["call_sid"] = call_sid
        if call_data.service:
            payload["service"] = call_data.service
        if call_data.status:
            payload["status"] = call_data.status
        if call_data.appointment_time:
            payload["appointment_time"] = call_data.appointment_time

        logger.info("Pushing contact to CRM backend: %s (tenant=%s, escalation_status=%s)", url, tenant_code, effective_escalation_status)

        body_bytes = json.dumps(payload).encode("utf-8")
        headers = _build_voice_agent_headers(tenant_code, body_bytes)

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, content=body_bytes, headers=headers)
            response.raise_for_status()

            logger.info("CRM backend: Contact submitted successfully (call_sid=%s)", call_sid)
            result = response.json() if response.text else {}
            return {
                "success": True,
                "response": result
            }

    except httpx.TimeoutException as e:
        error_msg = f"CRM backend request timeout: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        logger.error("CRM backend HTTP error %s: %s", e.response.status_code, error_detail)
        return {"success": False, "error": error_detail}
    except Exception as e:
        error_msg = f"CRM backend error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}

async def push_call_log_to_backend(
    call_sid: str,
    call_data: CallData,
    summary: str | None = None,
    transcript: str | None = None,
    duration_seconds: int | None = None,
    escalation_status: str | None = None,
    language: str = "en",
    discovery_answers: dict | None = None,
    timestamp: str | None = None,
) -> dict:
    """
    Push detailed call log to the CRM backend's /public/call-logs/ endpoint.

    POST {base_url}/public/call-logs/
    Body: {"call_id", "tenant_code", "timestamp", "caller_info", "call_metadata",
           "call_outcome", "escalation", "summary", "transcript", "discovery_answers"}

    Complements push_to_crm_backend() which focuses on lead submission.
    """
    if not CRM_BACKEND_URL:
        print("CRM backend URL not configured, skipping call log push")
        return {"success": False, "error": "CRM backend URL not configured"}
    try:
        url = f"{CRM_BACKEND_URL.rstrip('/')}/public/call-logs/"

        # Resolve tenant code: prefer per-call value, fall back to global config
        tenant_code = call_data.tenant_code or CRM_TENANT_CODE

        payload = {
            "call_id": call_sid,
            "tenant_code": tenant_code,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "caller_info": {
                "name": call_data.name or "Unknown",
                "phone": call_data.phone or "(555)555-5555",
                "email": call_data.email or "novaisnotworking@orbyn.ai",
            },
            "call_metadata": {
                "language": language,
                "duration_seconds": duration_seconds,
                "service_requested": call_data.service,
            },
            "call_outcome": {
                "status": call_data.status,
                "appointment_booked": bool(call_data.appointment_time),
                "appointment_time": call_data.appointment_time,
                "booking_uid": call_data.booking_uid,
            },
            "escalation": {
                "escalation_status": escalation_status or "none",
                "escalated_to_human": escalation_status == "escalated",
                "reason": None,
            },
            "summary": summary or "",
            "transcript": transcript or "",
            "discovery_answers": discovery_answers if discovery_answers is not None else call_data.discovery_answers,
        }

        logger.info("Pushing call log to CRM backend: %s (tenant=%s, call_sid=%s)", url, tenant_code, call_sid)

        body_bytes = json.dumps(payload).encode("utf-8")
        headers = _build_voice_agent_headers(tenant_code, body_bytes)

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, content=body_bytes, headers=headers)
            response.raise_for_status()

            logger.info("Call log pushed successfully (call_sid=%s)", call_sid)
            result = response.json() if response.text else {}
            return {
                "success": True,
                "response": result
            }

    except httpx.TimeoutException as e:
        error_msg = f"Call log push timeout: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        logger.error("Call log push HTTP error %s: %s", e.response.status_code, error_detail)
        return {"success": False, "error": error_detail}
    except Exception as e:
        error_msg = f"Call log push error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}
