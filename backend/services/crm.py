"""
CRM Service - Integrates with Notion database and CRM backend
"""
import httpx
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_API_URL, CRM_BACKEND_URL, CRM_TENANT_CODE
from models import CallData
from datetime import datetime

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

async def push_to_crm_backend(call_data: CallData, call_sid: str = None) -> dict:
    """
    Push contact/call data to the public CRM endpoint.

    The new endpoint expects only contact basics plus the tenant code:
    POST {base_url}/public/submit-contact
    Body: {"name", "email", "phone", "tenant_code"}
    """
    if not CRM_BACKEND_URL:
        print("CRM backend URL not configured (CRM_BACKEND_URL missing), skipping push")
        return {"success": False, "error": "CRM backend URL not configured"}
    try:
        url = f"{CRM_BACKEND_URL.rstrip('/')}/public/submit-contact"

        headers = {
            "Content-Type": "application/json"
        }

        # Minimal payload required by the public submit-contact endpoint
        payload = {
            "name": call_data.name or "Unknown",
            "email": call_data.email or "",
            "phone": call_data.phone or "",
            "tenant_code": CRM_TENANT_CODE,
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

        print(f"Pushing to CRM backend: {url}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            print("CRM backend: Contact submitted successfully")
            result = response.json() if response.text else {}
            return {
                "success": True,
                "response": result
            }

    except httpx.TimeoutException as e:
        error_msg = f"CRM backend request timeout: {str(e)}"
        print(error_msg)
        return {"success": False, "error": error_msg}
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        print(f"CRM backend HTTP error: {e}")
        print(f"Response body: {error_detail}")
        return {"success": False, "error": error_detail}
    except Exception as e:
        error_msg = f"CRM backend error: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return {"success": False, "error": error_msg}
