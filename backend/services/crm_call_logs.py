"""
CRM Call Logs Service - Posts call logs to the CRM backend's public endpoint.

Submits data matching the CallLogCreate schema to POST /public/call-logs/.
No authentication required (public endpoint).
"""
import asyncio
import sys
import os
import traceback
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from datetime import datetime, timezone

from config import CRM_CALL_LOGS_ENDPOINT, CRM_TENANT_CODE
from models import CallData


async def push_call_log_to_crm(
    call_data: CallData,
    full_transcript: str,
    summary: str | None = None,
    problem_statement: str | None = None,
    outcome: str | None = None,
    next_steps: str | None = None,
    escalation_status: str | None = None,
    call_duration: int | None = None,
    timestamp: str | None = None,
) -> dict:
    """
    Post a call log to the CRM backend's public /public/call-logs/ endpoint.

    Uses the flat CallLogCreate schema:
        tenant_code (required), full_transcript (required),
        summary, problem_statement, outcome ("booked"/"callback"/"no_action"),
        next_steps, caller_name, caller_phone, call_duration (seconds),
        escalation_status, timestamp (ISO-8601).

    Non-blocking: retries up to 3 times with backoff, but never raises so
    the call flow is unaffected if the CRM backend is unavailable.
    """
    if not CRM_CALL_LOGS_ENDPOINT:
        print("CRM_CALL_LOGS_ENDPOINT not configured, skipping call log push")
        return {"success": False, "error": "CRM_CALL_LOGS_ENDPOINT not configured"}

    try:
        headers = {"Content-Type": "application/json"}

        payload: dict = {
            "tenant_code": CRM_TENANT_CODE,
            "full_transcript": full_transcript or "",
        }

        if summary:
            payload["summary"] = summary
        if problem_statement:
            payload["problem_statement"] = problem_statement
        if outcome:
            payload["outcome"] = outcome
        if next_steps:
            payload["next_steps"] = next_steps
        if call_data.name:
            payload["caller_name"] = call_data.name
        if call_data.phone:
            payload["caller_phone"] = call_data.phone
        if call_duration is not None:
            payload["call_duration"] = call_duration
        if escalation_status:
            payload["escalation_status"] = escalation_status

        payload["timestamp"] = timestamp or datetime.now(timezone.utc).isoformat()

        print(f"Pushing call log to CRM: {CRM_CALL_LOGS_ENDPOINT}")

        max_attempts = 3
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        CRM_CALL_LOGS_ENDPOINT, json=payload, headers=headers
                    )
                    response.raise_for_status()

                print(f"✅ CRM call log submitted successfully (attempt {attempt})")
                result = response.json() if response.text else {}
                return {"success": True, "response": result}

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = str(e)
                print(f"⚠️ CRM call log attempt {attempt}/{max_attempts} failed: {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(attempt)  # simple backoff: 1 s, 2 s

            except httpx.HTTPStatusError as e:
                error_detail = e.response.text
                print(f"❌ CRM call log HTTP error {e.response.status_code}: {error_detail}")
                return {"success": False, "error": error_detail}

        error_msg = f"CRM call log push failed after {max_attempts} attempts: {last_error}"
        print(error_msg)
        return {"success": False, "error": error_msg}

    except Exception as e:
        error_msg = f"CRM call log unexpected error: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return {"success": False, "error": error_msg}
