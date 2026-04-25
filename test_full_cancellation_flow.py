"""
Full end-to-end test: Book an appointment and then cancel it
"""
import asyncio
import sys
from datetime import datetime, timedelta
sys.path.append("/opt/nova/nova-voice-agent/backend")

from services.calendar import book_appointment, find_booking_by_phone, get_available_slots
from services.calendar_cancellation import cancel_appointment

async def test_full_flow():
    print("="*60)
    print("Full Cancellation Flow Test")
    print("="*60)
    
    # Step 1: Get available slots
    print("\n[STEP 1] Getting available slots...")
    slots = await get_available_slots()
    
    if not slots:
        print("No available slots found. Cannot proceed with test.")
        return
    
    print(f"Found {len(slots)} available slots")
    first_slot = slots[0]
    print(f"Will book: {first_slot['date']} at {first_slot['time']}")
    
    # Step 2: Book an appointment
    print("\n[STEP 2] Booking test appointment...")
    test_phone = "+15551234567"
    booking_result = await book_appointment(
        name="Test User",
        email="test@example.com",
        phone=test_phone,
        datetime_slot=first_slot['datetime']
    )
    
    if not booking_result['success']:
        print(f"Booking failed: {booking_result.get('error')}")
        return
    
    booking_uid = booking_result.get("uid")
    print(f"Booking successful!")
    print(f"  Booking ID: {booking_result.get('booking_id')}")
    print(f"  Booking UID: {booking_uid}")
    
    # Step 3: Find the booking by phone
    print(f"\n[STEP 3] Finding booking by phone {test_phone}...")
    find_result = await find_booking_by_phone(test_phone)
    
    if find_result['success'] and find_result['bookings']:
        print(f"Found {len(find_result['bookings'])} booking(s)")
        found_booking = find_result['bookings'][0]
        print(f"  UID: {found_booking.get('uid')}")
        print(f"  Name: {found_booking.get('attendee_name')}")
    else:
        print("Booking not found! This is a problem.")
        return
    
    # Step 4: Cancel the booking
    print(f"\n[STEP 4] Cancelling booking {booking_uid}...")
    cancel_result = await cancel_appointment(
        booking_uid=booking_uid,
        reason="Automated test cancellation"
    )
    
    if cancel_result['success']:
        print(f"Cancellation successful: {cancel_result['message']}")
    else:
        print(f"Cancellation failed: {cancel_result['message']}")
    
    print("\n" + "="*60)
    print("Full flow test completed!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_full_flow())
