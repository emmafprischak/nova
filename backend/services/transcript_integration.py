"""
CRM Backend Integration Service
Sends call summaries to the CRM backend for storage and display
"""

import requests
import logging
from typing import Optional
from backend.config import CRM_BACKEND_URL, CRM_TENANT_CODE

logger = logging.getLogger(__name__)


async def send_summary_to_crm(
    call_sid: str,
    summary_data: dict,
    call_data: dict,
) -> bool:
    """
    Send call summary to CRM backend for storage.
    
    Args:
        call_sid: Twilio Call SID
        summary_data: Generated summary with keys:
            - summary: AI-generated summary
            - problem_statement: One-line problem
            - outcome: booked/callback/no_action
            - next_steps: What to do next
        call_data: CallData with caller info (name, phone, email, service, etc.)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        payload = {
            "tenant_code": CRM_TENANT_CODE,
            "summary": summary_data.get("summary"),
            "problem_statement": summary_data.get("problem_statement"),
            "outcome": summary_data.get("outcome"),
            "next_steps": summary_data.get("next_steps"),
            "caller_name": call_data.name,
            "caller_phone": call_data.phone,
        }
        
        response = requests.post(
            f"{CRM_BACKEND_URL}/transcripts/",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            transcript_id = response.json().get("id")
            logger.info(f"✅ Summary sent to CRM: ID {transcript_id}")
            return True
        else:
            logger.error(f"❌ CRM API error: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error("❌ CRM API timeout - summary not sent")
        return False
    except requests.exceptions.ConnectionError:
        logger.error("❌ CRM API connection error - summary not sent")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending summary to CRM: {e}")
        return False