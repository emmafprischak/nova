"""
Appointment Cancellation via Cal.com API
"""

import httpx
import logging
from typing import Optional
from config import CAL_API_KEY

logger = logging.getLogger(__name__)

CAL_API_URL = "https://api.cal.com/v1"
CAL_API_KEY = settings.CAL_API_KEY


async def cancel_appointment(booking_uid: str, reason: Optional[str] = None) -> dict:
    """
    Cancel a Cal.com booking.
    
    Args:
        booking_uid: The booking UID from Cal.com
        reason: Optional cancellation reason
        
    Returns:
        dict with success: bool and message: str
    """
    if not booking_uid:
        return {"success": False, "message": "No booking UID provided"}

    try:
        url = f"{CAL_API_URL}/bookings/{booking_uid}/cancel"
        
        headers = {
            "Authorization": f"Bearer {CAL_API_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "cancellationReason": reason or "Cancelled by customer via phone"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                logger.info(f"Successfully cancelled booking {booking_uid}")
                return {
                    "success": True,
                    "message": "Appointment cancelled successfully",
                }
            elif response.status_code == 404:
                logger.warning(f"Booking {booking_uid} not found")
                return {
                    "success": False,
                    "message": "Appointment not found - may already be cancelled",
                }
            else:
                logger.error(f"Cal.com cancel failed: {response.status_code}")
                return {
                    "success": False,
                    "message": f"Cancellation failed: {response.text}",
                }
                
    except httpx.TimeoutException:
        logger.error(f"Timeout cancelling booking {booking_uid}")
        return {
            "success": False,
            "message": "Request timed out - please try again",
        }
    except Exception as e:
        logger.error(f"Error cancelling booking: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Unexpected error: {str(e)}",
        }


def is_cancellation_request(user_input: str) -> bool:
    """Detect if user wants to cancel an appointment."""
    lower = user_input.lower()
    keywords = ["cancel", "cancellation", "cancel my appointment", "don't need", "won't make it"]
    return any(kw in lower for kw in keywords)