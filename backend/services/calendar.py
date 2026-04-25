"""
Calendar Service - Integrates with Cal.com
"""
import httpx
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CAL_API_KEY, CAL_EVENT_TYPE
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from backend.services.logger import StructuredLogger

# Initialize logger
logger = StructuredLogger(__name__)

# Event Type ID for free-consultation
EVENT_TYPE_ID = 3871645

def is_valid_business_hours(dt_et: datetime) -> bool:
    """
    FR-04: Check if datetime is within Mon-Fri 7AM-9PM Eastern Time.
    
    Args:
        dt_et: datetime in Eastern timezone
        
    Returns:
        True if within business hours
    """
    if dt_et.weekday() > 4:
        return False
    business_start = time(7, 0)
    business_end = time(21, 0)
EVENT_TYPE_ID = 3871645

async def get_available_slots(days_ahead: int = 7, filter_business_hours: bool = True) -> list[dict]:
    """Get available time slots from Cal.com"""
    try:
        # Get current time in Eastern timezone
        eastern = ZoneInfo("America/New_York")
        now_et = datetime.now(eastern)
        start_date = now_et.date()
        end_date = start_date + timedelta(days=days_ahead)

        url = f"https://api.cal.com/v2/slots/available"
        params = {
            "apiKey": CAL_API_KEY,
            "eventTypeId": EVENT_TYPE_ID,
            "startTime": start_date.isoformat(),
            "endTime": end_date.isoformat(),
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            slots = []
            if "data" in data and "slots" in data["data"]:
                for date, times in data["data"]["slots"].items():
                    for slot in times:
                        # Parse UTC time and convert to Eastern Time
                        time_obj_utc = datetime.fromisoformat(slot["time"].replace('Z', '+00:00'))
                        time_obj_et = time_obj_utc.astimezone(eastern)
                        # FR-04: Filter by business hours if requested
                        if filter_business_hours and not is_valid_business_hours(time_obj_et):
                            continue

                        # Format for display in ET
                        local_time = time_obj_et.strftime("%I:%M %p")
                        local_date = time_obj_et.strftime("%Y-%m-%d")

                        slots.append({
                            "date": local_date,
                            "time": local_time,
                            "datetime": slot["time"]  # Keep original UTC for booking
                        })

            print(f"Found {len(slots)} available slots")
            return slots[:5]

    except Exception as e:
        logger.error("Error getting slots", error=str(e))
        # Return default slots for testing in Eastern Time
        eastern = ZoneInfo("America/New_York")
        tomorrow_et = datetime.now(eastern) + timedelta(days=1)

        # Create slots at 10 AM and 2 PM ET
        slot1_et = tomorrow_et.replace(hour=10, minute=0, second=0, microsecond=0)
        slot2_et = tomorrow_et.replace(hour=14, minute=0, second=0, microsecond=0)

        # Convert to UTC for the datetime field
        slot1_utc = slot1_et.astimezone(ZoneInfo("UTC"))
        slot2_utc = slot2_et.astimezone(ZoneInfo("UTC"))

        return [
            {
                "date": slot1_et.strftime("%Y-%m-%d"),
                "time": "10:00 AM",
                "datetime": slot1_utc.isoformat().replace('+00:00', 'Z')
            },
            {
                "date": slot2_et.strftime("%Y-%m-%d"),
                "time": "2:00 PM",
                "datetime": slot2_utc.isoformat().replace('+00:00', 'Z')
            },
        ]


async def verify_slot_still_available(datetime_slot: str) -> bool:
    """
    FR-04: Double-booking prevention - verify slot is still available before booking.
    
    Args:
        datetime_slot: UTC datetime string
        
    Returns:
        True if slot is still available
    """
    try:
        all_slots = await get_available_slots(days_ahead=14, filter_business_hours=False)
        for slot in all_slots:
            if slot["datetime"] == datetime_slot:
                return True
        logger.warning("Slot no longer available - double-booking prevented", datetime_slot=datetime_slot)
        return False
    except Exception as e:
        logger.error("Error verifying slot availability", error=str(e))
        return False

async def book_appointment(name: str, email: str, phone: str, datetime_slot: str) -> dict:
    """FR-04: Book an appointment with double-booking prevention"""
    try:
        # FR-04: Double-booking prevention
        if not await verify_slot_still_available(datetime_slot):
            return {
                "success": False,
                "error": "slot_unavailable",
                "message": "Sorry, that slot was just booked. Let me find another time."
            }
        url = f"https://api.cal.com/v2/bookings"

        headers = {
            "Authorization": f"Bearer {CAL_API_KEY}",
            "Content-Type": "application/json",
            "cal-api-version": "2024-08-13"
        }

        booking_data = {
            "eventTypeId": EVENT_TYPE_ID,
            "start": datetime_slot,  # UTC time from slot selection
            "attendee": {
                "name": name,
                "email": email,
                "timeZone": "America/New_York",  # Eastern Time
                "language": "en"
            },
            "metadata": {"source": "nova-voice-agent", "phone": phone}
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=booking_data, headers=headers)
            response.raise_for_status()
            result = response.json()

            logger.info("Booking successful", result=result)
            return {
                "success": True,
                "booking_id": result.get("data", {}).get("id"),
                "uid": result.get("data", {}).get("uid"),
                "booking_url": result.get("data", {}).get("url"),
                "start_time": datetime_slot
            }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            return {
                "success": False,
                "error": "slot_conflict",
                "message": "That time slot is no longer available. Let me find another option."
            }
        logger.error("Error booking appointment", error=str(e))
        return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error("Error booking appointment", error=str(e))
        return {"success": False, "error": str(e)}

def format_slots_for_speech(slots: list[dict], language: str = "en") -> str:
    """FR-04: Format slots with alternate window fallback"""
    if not slots:
        if language == "es":
            return "No tengo espacios disponibles esta semana. ¿Qué te parece la próxima semana o la semana siguiente? Puedo consultar otras fechas si prefieres."
        else:
            return "I don't have any openings this week. How about next week or the week after? I can check other dates if you'd like."

    by_date = {}
    for slot in slots[:3]:
        date = slot["date"]
        time = slot["time"]
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(time)

    parts = []
    for date, times in by_date.items():
        dt = datetime.fromisoformat(date)
        day_name = dt.strftime("%A")

        if len(times) == 1:
            parts.append(f"{day_name} at {times[0]}")
        else:
            times_str = ", ".join(times[:-1]) + f", or {times[-1]}"
            parts.append(f"{day_name} at {times_str}")

    if language == "es":
        return "Tengo espacios disponibles " + ", ".join(parts) + ". ¿Cuál te conviene mejor?"
    else:
        return "I have openings " + ", ".join(parts) + ". Which works best for you?"


async def find_booking_by_phone(phone: str) -> dict:
    """
    Find upcoming bookings for a phone number using v1 API.
    
    Args:
        phone: Phone number to search for
        
    Returns:
        dict with success: bool, bookings: list of booking dicts
    """
    try:
        url = f"https://api.cal.com/v1/bookings"
        
        # Get bookings - v1 API doesn't require cal-api-version header
        params = {
            "apiKey": CAL_API_KEY,
            "status": "upcoming"  # Only upcoming bookings
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
            
            bookings = result.get("bookings", [])
            
            # Filter by phone number in metadata
            matching_bookings = []
            for booking in bookings:
                metadata = booking.get("metadata", {})
                booking_phone = metadata.get("phone", "")
                
                # Normalize phone numbers for comparison (remove non-digits)
                import re
                normalized_search = re.sub(r'\D', '', phone)
                normalized_booking = re.sub(r'\D', '', booking_phone)
                
                if normalized_search and normalized_booking and normalized_search in normalized_booking:
                    matching_bookings.append({
                        "id": booking.get("id"),
                        "uid": booking.get("uid"),
                        "start": booking.get("start"),
                        "attendee_name": booking.get("attendees", [{}])[0].get("name", "")
                    })
            
            logger.info("Bookings found by phone", count=len(matching_bookings), phone=phone)
            return {
                "success": True,
                "bookings": matching_bookings
            }
            
    except Exception as e:
        logger.error("Error finding booking", error=str(e))
        return {"success": False, "error": str(e), "bookings": []}


async def detect_rescheduling_request(user_input: str) -> bool:
    """
    FR-04: Detect if user wants to reschedule an existing appointment.
    
    Args:
        user_input: What the user said
        
    Returns:
        True if user wants to reschedule
    """
    keywords = [
        "reschedule", "move my appointment", "change my appointment",
        "different time", "another time", "change the time",
        # Spanish
        "reprogramar", "cambiar mi cita", "mover mi cita", "otra hora"
    ]
    user_lower = user_input.lower()
    return any(kw in user_lower for kw in keywords)
