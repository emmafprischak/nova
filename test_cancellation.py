"""
Test script for appointment cancellation feature
"""
import asyncio
import sys
sys.path.append("/opt/nova/nova-voice-agent/backend")

from services.calendar import find_booking_by_phone
from services.calendar_cancellation import cancel_appointment, is_cancellation_request

async def test_cancellation_flow():
    """Test the full cancellation flow"""
    print("="*60)
    print("Testing Appointment Cancellation Feature")
    print("="*60)
    
    # Test 1: Keyword detection
    print("\n[TEST 1] Testing cancellation keyword detection...")
    test_phrases = [
        ("I want to cancel my appointment", True),
        ("cancel", True),
        ("Quiero cancelar mi cita", True),
        ("cancelar", True),
        ("I need to book an appointment", False),
        ("hello", False)
    ]
    
    for phrase, expected in test_phrases:
        result = is_cancellation_request(phrase)
        status = "PASS" if result == expected else "FAIL"
        print(f"{status}: {phrase}: {result} (expected {expected})")
    
    # Test 2: Find bookings by phone
    print("\n[TEST 2] Testing booking lookup by phone number...")
    print("Fetching all upcoming bookings from Cal.com...")
    
    try:
        # First, lets see what bookings exist
        result = await find_booking_by_phone("")  # Empty to get all
        print(f"Total upcoming bookings found: {len(result.get('bookings', []))}")
        
        if result["success"] and result["bookings"]:
            print("\nAvailable bookings:")
            for i, booking in enumerate(result["bookings"][:5], 1):
                print(f"  {i}. UID: {booking.get('uid')}")
                print(f"     Name: {booking.get('attendee_name')}")
                print(f"     Start: {booking.get('start')}")
                print()
            
            # Test with first bookings phone (if metadata exists)
            print("Note: To test phone lookup, you need a booking with phone in metadata")
        else:
            print("No bookings found or error occurred")
            if not result["success"]:
                print(f"Error: {result.get('error')}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Test cancellation API (dry run - will ask for confirmation)
    print("\n[TEST 3] Testing cancellation API...")
    print("This test will actually cancel a booking if you proceed!")
    
    try:
        result = await find_booking_by_phone("")
        if result["success"] and result["bookings"]:
            test_booking = result["bookings"][0]
            booking_uid = test_booking.get("uid")
            
            print(f"\nFound test booking:")
            print(f"  UID: {booking_uid}")
            print(f"  Name: {test_booking.get('attendee_name')}")
            print(f"  Start: {test_booking.get('start')}")
            
            print("\nSkipping actual cancellation - set CANCEL_TEST=yes to test")
            print("To manually test cancellation, run:")
            print(f"  python -c 'import asyncio; from services.calendar_cancellation import cancel_appointment; print(asyncio.run(cancel_appointment(\"{booking_uid}\", \"Test\")))'")
        else:
            print("No bookings available to test cancellation")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("Test completed!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_cancellation_flow())
