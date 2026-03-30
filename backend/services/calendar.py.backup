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

# Event Type ID for free-consultation
EVENT_TYPE_ID = 3871645

async def get_available_slots(days_ahead: int = 7) -> list[dict]:
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
        print(f"Error getting slots: {e}")
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

async def book_appointment(name: str, email: str, phone: str, datetime_slot: str) -> dict:
    """Book an appointment in Cal.com"""
    try:
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

            print(f"Booking successful: {result}")
            return {
                "success": True,
                "booking_id": result.get("data", {}).get("id"),
                "booking_url": result.get("data", {}).get("url"),
                "start_time": datetime_slot
            }

    except Exception as e:
        print(f"Error booking: {e}")
        return {"success": False, "error": str(e)}

def format_slots_for_speech(slots: list[dict]) -> str:
    """Format slots for natural speech"""
    if not slots:
        return "I don't have any available slots right now."

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

    return "I have openings " + ", ".join(parts) + ". Which works best for you?"
