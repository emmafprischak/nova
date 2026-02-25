"""
Test script to verify call summary generation
"""
import asyncio
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.conversation import get_conversation, end_conversation
from backend.services.crm import push_to_crm_backend
from backend.models import CallData, Message

def test_summary_generation():
    """Test the generate_call_summary function"""
    print("\n" + "="*60)
    print("Testing Call Summary Generation...")
    print("="*60)
    
    try:
        # Mock OpenAI response
        mock_response = Mock()
        mock_message = Mock()
        mock_message.content = "John Smith called inquiring about AI consulting services. An appointment was successfully booked. Follow-up confirmation SMS was sent to the customer."
        mock_response.choices = [Mock(message=mock_message)]
        
        with patch('backend.services.conversation.client.chat.completions.create', return_value=mock_response):
            # Import after patching
            from backend.services.conversation import generate_call_summary
            
            # Create a test conversation
            test_call_sid = "TEST_CALL_SID_SUMMARY_123"
            conversation = get_conversation(test_call_sid)
            
            # Simulate a conversation
            conversation.messages = [
                Message(role="assistant", content="Hey there! This is Nova from Orbyn AI. How can I help you today?"),
                Message(role="user", content="Hi, my name is John Smith and I need help with AI consulting."),
                Message(role="assistant", content="Great! John, tell me more about your AI consulting needs."),
                Message(role="user", content="I want to learn about implementing AI in my business. Can I book a consultation?"),
                Message(role="assistant", content="Absolutely! I can schedule that for you. What's your phone number?"),
                Message(role="user", content="It's 555-123-4567"),
                Message(role="assistant", content="Perfect! Let me book you for an appointment.")
            ]
            
            # Set call data
            conversation.call_data.name = "John Smith"
            conversation.call_data.phone = "555-123-4567"
            conversation.call_data.service = "AI consulting"
            conversation.call_data.status = "booked"
            conversation.call_data.appointment_time = "2024-03-20T10:00:00"
            
            print("\n1. Generating summary for test conversation...")
            print(f"   Conversation has {len(conversation.messages)} messages")
            
            # Generate summary
            summary = generate_call_summary(test_call_sid)
            
            print(f"\n✅ SUCCESS: Summary generated!")
            print(f"\n📋 Call Summary:\n{summary}\n")
            
            # Verify that the summary is not empty
            if summary and len(summary) > 0:
                print("   ✓ Summary is not empty")
            else:
                print("   ✗ Summary is empty")
                return False
            
            # Test edge case: empty conversation
            print("\n2. Testing edge case: empty conversation...")
            empty_call_sid = "TEST_EMPTY_CALL_123"
            empty_conversation = get_conversation(empty_call_sid)
            empty_conversation.messages = []
            
            empty_summary = generate_call_summary(empty_call_sid)
            if "No conversation data available" in empty_summary:
                print("   ✓ Empty conversation handled gracefully")
            else:
                print("   ✗ Empty conversation not handled properly")
            
            # Clean up
            end_conversation(test_call_sid)
            end_conversation(empty_call_sid)
            
            return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_crm_push_with_summary():
    """Test pushing to CRM backend with summary"""
    print("\n" + "="*60)
    print("Testing CRM Backend Push with Summary...")
    print("="*60)
    
    try:
        print("\n1. Testing CRM payload structure with summary...")
        
        test_call_data = CallData(
            name="Jane Doe",
            phone="+15551234567",
            email="jane.doe@example.com",
            service="AI Integration Test",
            status="booked",
            appointment_time="2024-03-21T14:00:00",
            notes="Test entry for summary feature"
        )
        
        test_summary = "Jane Doe called inquiring about AI integration services. An appointment was successfully booked for March 21st at 2:00 PM. She will receive a confirmation text message."
        
        print(f"   Summary: {test_summary}")
        
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"success": true, "message": "Contact submitted"}'
        mock_response.json = Mock(return_value={"success": True, "message": "Contact submitted"})
        mock_response.raise_for_status = Mock()
        
        # Create an async mock for the client
        async def mock_post(*args, **kwargs):
            # Verify the summary is in the payload
            if 'json' in kwargs:
                payload = kwargs['json']
                if 'summary' in payload:
                    print(f"   ✓ Summary correctly included in payload")
                else:
                    print(f"   ✗ Summary not found in payload")
                if 'escalation_status' in payload:
                    print(f"   ✓ escalation_status correctly included in payload: {payload['escalation_status']}")
                else:
                    print(f"   ✗ escalation_status not found in payload")
                if 'timestamp' in payload:
                    print(f"   ✓ timestamp correctly included in payload: {payload['timestamp']}")
                else:
                    print(f"   ✗ timestamp not found in payload")
            return mock_response
        
        # Mock httpx.AsyncClient
        mock_client = MagicMock()
        mock_client.post = mock_post
        
        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                pass
            
            async def __aenter__(self):
                return mock_client
            
            async def __aexit__(self, *args):
                pass
        
        with patch('httpx.AsyncClient', MockAsyncClient):
            # Push to CRM backend with summary
            result = await push_to_crm_backend(
                call_data=test_call_data,
                call_sid="TEST_CRM_SUMMARY_456",
                summary=test_summary
            )
            
            if result.get("success"):
                print(f"\n✅ SUCCESS: CRM backend integration working")
                return True
            else:
                error = result.get('error', 'Unknown error')
                print(f"\n❌ FAILED: {error}")
                return False
                
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_crm_payload_new_fields():
    """Test that escalation_status and timestamp are included and valid in CRM payload"""
    print("\n" + "="*60)
    print("Testing CRM Payload New Fields (escalation_status, timestamp)...")
    print("="*60)

    import re
    from datetime import datetime, timezone

    ISO8601_Z_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$')
    VALID_ESCALATION_STATUSES = {"none", "pending", "escalated", "resolved"}

    captured = {}

    test_call_data = CallData(
        name="Payload Test",
        phone="+15550000001",
        email="payload@example.com",
        service="Test",
        status="booked",
        appointment_time=None,
        notes=""
    )

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = '{"success": true}'
    mock_response.json = Mock(return_value={"success": True})
    mock_response.raise_for_status = Mock()

    async def mock_post(*args, **kwargs):
        if 'json' in kwargs:
            captured.update(kwargs['json'])
        return mock_response

    mock_client = MagicMock()
    mock_client.post = mock_post

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return mock_client
        async def __aexit__(self, *args):
            pass

    try:
        with patch('httpx.AsyncClient', MockAsyncClient):
            await push_to_crm_backend(
                call_data=test_call_data,
                call_sid="TEST_FIELDS_789",
                escalation_status="pending",
            )

        ok = True

        if 'escalation_status' in captured:
            status = captured['escalation_status']
            if status in VALID_ESCALATION_STATUSES:
                print(f"   ✓ escalation_status='{status}' is valid")
            else:
                print(f"   ✗ escalation_status='{status}' is not a recognised value")
                ok = False
        else:
            print("   ✗ escalation_status missing from payload")
            ok = False

        if 'timestamp' in captured:
            ts = captured['timestamp']
            if ISO8601_Z_RE.match(ts):
                print(f"   ✓ timestamp='{ts}' is valid ISO-8601 UTC")
            else:
                print(f"   ✗ timestamp='{ts}' does not match ISO-8601 Z format")
                ok = False
        else:
            print("   ✗ timestamp missing from payload")
            ok = False

        if ok:
            print("\n✅ SUCCESS: New CRM payload fields are present and valid")
        else:
            print("\n❌ FAILED: One or more new payload fields are missing or invalid")
        return ok

    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("NOVA VOICE AGENT - CALL SUMMARY TESTS")
    print("="*60)
    
    # Test summary generation
    summary_ok = test_summary_generation()
    
    # Test CRM push with summary
    crm_ok = await test_crm_push_with_summary()

    # Test new CRM payload fields
    fields_ok = await test_crm_payload_new_fields()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Summary Generation:       {'✅ WORKING' if summary_ok else '❌ FAILED'}")
    print(f"CRM Push w/ Summary:      {'✅ WORKING' if crm_ok else '❌ FAILED'}")
    print(f"CRM Payload New Fields:   {'✅ WORKING' if fields_ok else '❌ FAILED'}")
    print("="*60 + "\n")
    
    if summary_ok and crm_ok and fields_ok:
        print("🎉 All call summary tests passed!")
        return 0
    else:
        print("⚠️  Some tests need attention")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
