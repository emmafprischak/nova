"""
Webhook Routes - Twilio calls these endpoints
"""
from fastapi import APIRouter, Form, Response, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
from twilio.twiml.voice_response import VoiceResponse, Gather
import sys
import os
import traceback
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faq_data import FAQ_DATA, DEFAULT_RESPONSES
from services.conversation import generate_response, get_conversation, end_conversation, detect_language
from services.calendar import get_available_slots, book_appointment, format_slots_for_speech, find_booking_by_phone
from services.calendar_cancellation import cancel_appointment
from services.two_factor_auth import create_verification, verify_code
from services.sms import send_confirmation_sms
from services.crm import create_lead, push_to_crm_backend, push_call_log_to_backend, determine_escalation_status
from services.transcript import generate_call_summary, save_summary_to_file
from backend.services.transcript_integration import send_summary_to_crm
from backend.services.sanitization import sanitize_for_tts, sanitize_user_input
from backend.services.agent_auth import require_agent_for_tenant
from backend.config import CRM_TENANT_CODE


router = APIRouter()

# Then in call_status, replace the previous CRM send with:

# ========== FAQ HELPER FUNCTIONS ==========

def detect_faq_intent(user_message: str):
    """
    Detects if user message matches any FAQ keywords
    Returns the FAQ key if match found, else None
    """
    if not user_message:
        return None
        
    user_message_lower = user_message.lower()
    
    for faq_key, faq_content in FAQ_DATA.items():
        for keyword in faq_content["keywords"]:
            if keyword.lower() in user_message_lower:
                return faq_key
    
    return None


def get_faq_response(faq_key: str, language: str):
    """
    Get the FAQ response in the appropriate language
    """
    if faq_key and faq_key in FAQ_DATA:
        return FAQ_DATA[faq_key].get(language, FAQ_DATA[faq_key]["english"])
    return None

# ========== END FAQ FUNCTIONS ==========


def log_faq_miss(user_message: str, call_sid: str, language: str):
    """
    Log when FAQ doesn't match user query for knowledge base improvement
    """
    import json
    from datetime import datetime
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "call_sid": call_sid,
        "user_message": user_message,
        "language": language,
        "matched": False
    }
    
    # Log to file (you can change this to database later)
    try:
        with open("/opt/nova/nova-voice-agent/backend/logs/faq_misses.log", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"Failed to log FAQ miss: {e}")

@router.post("/voice/incoming")
@limiter.limit("10/minute")
async def handle_incoming_call(request: Request, CallSid: str = Form(...)):
    """Called when someone calls your Twilio number"""
    require_agent_for_tenant(request, CRM_TENANT_CODE)
    print(f"Incoming call: {CallSid}")

    try:
        response = VoiceResponse()
        # Set language hints to support both English and Spanish
        gather = Gather(
            input='speech',
            action='/webhooks/voice/process',
            speechTimeout='auto',
            language='en-US',
            hints='hola, hello, buenos días, ayuda, help, español, spanish',
            speech_model='experimental_conversations'
        )

        # Use Google's more natural neural voice
        gather.say(
            "Hey there! This is Nova from Orbyn AI. How can I help you today?",
            voice='Google.en-US-Neural2-F'
        )

        response.append(gather)
        response.say(sanitize_for_tts("I didn't hear anything. Please call back when you're ready. Goodbye!"), voice='Google.en-US-Neural2-F')

        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        print(f"Error in incoming call: {e}")
        traceback.print_exc()
        response = VoiceResponse()
        response.say(sanitize_for_tts("Sorry, there was an error. Please try again later."), voice='Google.en-US-Neural2-F')
        return Response(content=str(response), media_type="application/xml")

@router.post("/voice/process")
@limiter.limit("30/minute")
async def process_speech(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: str = Form(None),
    From: str = Form(...)
):
    """Called after the user speaks"""
    require_agent_for_tenant(request, CRM_TENANT_CODE)
    print(f"User said: {SpeechResult}")
    # Sanitize user input before processing
    if SpeechResult:
        SpeechResult = sanitize_user_input(SpeechResult)
        print(f"Sanitized input: {SpeechResult}")


    try:
        if not SpeechResult:
            response = VoiceResponse()
            response.say(sanitize_for_tts("Sorry, I didn't catch that. Could you say that again?"), voice='Google.en-US-Neural2-F')
            response.redirect('/webhooks/voice/incoming')
            return Response(content=str(response), media_type="application/xml")

        # Detect language from user's speech
        detected_lang = detect_language(SpeechResult)
        print(f"Detected language: {detected_lang}")

        # ========== FAQ DETECTION ==========
        # Get conversation state to check if we are in a special mode
        conversation = get_conversation(CallSid)
        
        # Skip FAQ detection if in discovery or cancellation mode
        skip_faq = (
            (hasattr(conversation, "stage") and conversation.stage in ["discovery", "cancellation"]) or
            (hasattr(conversation, "is_cancelling") and conversation.is_cancelling) or
            (hasattr(conversation, "discovery_complete") and not conversation.discovery_complete)
        )
        
        if not skip_faq:
            faq_key = detect_faq_intent(SpeechResult)
        else:
            faq_key = None
            print(f"Skipping FAQ detection - in {getattr(conversation, 'stage', 'unknown')} mode")
        
        if faq_key:
            print(f"FAQ detected: {faq_key}")
            conversation = get_conversation(CallSid)
            lang_code = 'es-MX' if detected_lang == 'es' else 'en-US'
            voice = 'Google.es-US-Neural2-A' if detected_lang == 'es' else 'Google.en-US-Neural2-F'
            
            # Get FAQ answer in appropriate language
            faq_answer = get_faq_response(faq_key, detected_lang)
            
            # Log successful FAQ match
            print(f"FAQ match logged: {faq_key}")
            
            # Special handling for human escalation - transfer immediately
            if faq_key == "escalate_to_human":
                conversation.call_data.status = "needs_callback"
                print("Human escalation requested - transferring to human")
                
                response = VoiceResponse()
                response.say(sanitize_for_tts(faq_answer), voice=voice)
                
                # Transfer to human immediately
                
                # Add a brief goodbye message before transfer
                goodbye_msg = "Un momento, por favor..." if detected_lang == "es" else "Hold on just a sec, transferring you now..."
                response.say(sanitize_for_tts(goodbye_msg), voice=voice)
                response.dial("+18145550100")
                
                return Response(content=str(response), media_type="application/xml")
            
            # Get follow-up question for non-escalation FAQs
            followup = DEFAULT_RESPONSES["followup_spanish"] if detected_lang == 'es' else DEFAULT_RESPONSES["followup_english"]
            
            # Combine FAQ answer with follow-up
            full_response = f"{faq_answer} {followup}"
            
            response = VoiceResponse()
            gather = Gather(
                input='speech',
                action='/webhooks/voice/process',
                speechTimeout='auto',
                language=lang_code,
                speech_model='experimental_conversations'
            )
            gather.say(sanitize_for_tts(full_response), voice=voice)
            response.append(gather)
            
            fallback = "¿Sigues ahí?" if detected_lang == 'es' else "Hello? You still there?"
            response.say(sanitize_for_tts(fallback), voice=voice)
            # Removed redirect to prevent looping - call will end if no response
            
            return Response(content=str(response), media_type="application/xml")
        else:
            # Log FAQ miss - no match found
            log_faq_miss(SpeechResult, CallSid, detected_lang)
            print(f"FAQ miss logged for: {SpeechResult}")
        # ========== END FAQ DETECTION ==========

        # Generate AI response with detected language
        ai_response, extracted_data = generate_response(CallSid, SpeechResult, detected_lang)

        # Check for escalation
        if extracted_data.get("escalate"):
            conversation = get_conversation(CallSid)
            lang_code = 'es-MX' if conversation.language == 'es' else 'en-US'
            voice = 'Google.es-US-Neural2-A' if conversation.language == 'es' else 'Google.en-US-Neural2-F'
            
            response = VoiceResponse()
            # Say the escalation message from AI
            response.say(sanitize_for_tts(ai_response), voice=voice)
            
            # Add a brief goodbye message before transfer
            goodbye_msg = "Un momento, por favor..." if conversation.language == 'es' else "Hold on just a sec, transferring you now..."
            response.say(sanitize_for_tts(goodbye_msg), voice=voice)
            
            # Transfer to human (update phone number)
            response.dial("+18145550100")  # Your team's phone number
            
            return Response(content=str(response), media_type="application/xml")

        print(f"Nova says: {ai_response}")
        print(f"Extracted: {extracted_data}")

        conversation = get_conversation(CallSid)

        # Get language settings with more natural neural voices
        lang_code = 'es-MX' if conversation.language == 'es' else 'en-US'
        voice = 'Google.es-US-Neural2-A' if conversation.language == 'es' else 'Google.en-US-Neural2-F'
        fallback_message = "¿Sigues ahí?" if conversation.language == 'es' else "Hello? You still there?"

        # Check if this is a cancellation request
        print(f"DEBUG: Checking cancellation - is_cancelling={getattr(conversation, 'is_cancelling', 'N/A')}, has name={conversation.call_data.name}, has phone={conversation.call_data.phone}")
        if hasattr(conversation, 'is_cancelling') and conversation.is_cancelling:
            # User wants to cancel - collect name and phone if we don't have them
            if conversation.call_data.name and conversation.call_data.phone:
                # We have the info - look up their booking
                print(f"Looking up bookings for {conversation.call_data.phone}")
                booking_lookup = await find_booking_by_phone(conversation.call_data.phone)
                
                if booking_lookup["success"] and booking_lookup["bookings"]:
                    # Found booking(s) - cancel the first upcoming one
                    booking = booking_lookup["bookings"][0]
                    booking_uid = booking.get("uid")
                    
                    print(f"Cancelling booking {booking_uid}")
                    cancel_result = await cancel_appointment(booking_uid, reason="Cancelled via voice agent")
                    
                    response = VoiceResponse()
                    if cancel_result["success"]:
                        if conversation.language == 'es':
                            response.say(
                                f"Perfecto, {conversation.call_data.name}. He cancelado tu cita. ¿Hay algo más en lo que pueda ayudarte?",
                                voice=voice
                            )
                        else:
                            response.say(
                                f"All set, {conversation.call_data.name}. I've cancelled your appointment. Is there anything else I can help you with?",
                                voice=voice
                            )
                    else:
                        if conversation.language == 'es':
                            response.say(
                                "Lo siento, no pude cancelar la cita. Déjame que alguien del equipo te ayude.",
                                voice=voice
                            )
                        else:
                            response.say(
                                "I'm sorry, I wasn't able to cancel that appointment. Let me have someone from the team help you out.",
                                voice=voice
                            )
                    
                    # Mark cancellation as complete
                    conversation.is_cancelling = False
                    conversation.call_data.status = "cancelled"
                    
                    return Response(content=str(response), media_type="application/xml")
                else:
                    # No booking found
                    response = VoiceResponse()
                    if conversation.language == 'es':
                        response.say(
                            f"Hmm, no encuentro ninguna cita para {conversation.call_data.phone}. ¿Quieres que alguien del equipo te ayude?",
                            voice=voice
                        )
                    else:
                        response.say(
                            f"Hmm, I don't see any upcoming appointments for {conversation.call_data.phone}. Would you like me to have someone from the team help you out?",
                            voice=voice
                        )
                    
                    conversation.call_data.status = "needs_callback"
                    return Response(content=str(response), media_type="application/xml")

        # FR-08: Trigger discovery stage if not already started or complete
        if (extracted_data.get("ready_to_book") and 
            not conversation.discovery_complete and
            conversation.stage != 'discovery'):
            # User wants to book but hasn't done discovery yet
            conversation.stage = 'discovery'
            print(f"Triggering discovery stage for {conversation.call_data.name}")

        # Check if ready to book
        # FR-08: Only proceed to booking if discovery questions are complete
        if (conversation.call_data.name and
            conversation.call_data.phone and
            extracted_data.get("ready_to_book") and
            conversation.discovery_complete):

            print("Ready to book, fetching slots...")
            slots = await get_available_slots()
            print(f"Got {len(slots)} slots")
            slots_speech = format_slots_for_speech(slots)

            response = VoiceResponse()
            gather = Gather(
                input='speech',
                action='/webhooks/voice/book',
                speechTimeout='auto',
                language=lang_code,
                speech_model='experimental_conversations'
            )
            gather.say(sanitize_for_tts(f"{ai_response} {slots_speech}"), voice=voice)
            response.append(gather)

            return Response(content=str(response), media_type="application/xml")

        # Continue conversation
        response = VoiceResponse()
        gather = Gather(
            input='speech',
            action='/webhooks/voice/process',
            speechTimeout='auto',
            language=lang_code,
            speech_model='experimental_conversations'
        )
        gather.say(sanitize_for_tts(ai_response), voice=voice)
        response.append(gather)

        response.say(sanitize_for_tts(fallback_message), voice=voice)
        # Removed redirect to prevent looping - call will end if no response

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        print(f"Error in process_speech: {e}")
        traceback.print_exc()
        response = VoiceResponse()
        response.say(sanitize_for_tts("Oops, I'm having a little tech issue. Let me have someone call you back. Thanks!"), voice='Google.en-US-Neural2-F')
        return Response(content=str(response), media_type="application/xml")

@router.post("/voice/book")
async def book_slot(CallSid: str = Form(...), SpeechResult: str = Form(None)):
    """Handle booking confirmation"""
    print(f"Booking: {SpeechResult}")

    try:
        conversation = get_conversation(CallSid)

        # Get language settings with natural voices
        voice = 'Google.es-US-Neural2-A' if conversation.language == 'es' else 'Google.en-US-Neural2-F'

        slots = await get_available_slots()

        if slots:
            selected_slot = slots[0]

            print(f"Booking appointment for {conversation.call_data.name} at {selected_slot['datetime']}")

            # Book appointment
            booking_result = await book_appointment(
                name=conversation.call_data.name,
                email=conversation.call_data.email or f"{conversation.call_data.phone}@temp.com",
                phone=conversation.call_data.phone,
                datetime_slot=selected_slot["datetime"]
            )

            if booking_result["success"]:
                conversation.call_data.appointment_time = selected_slot["datetime"]
                conversation.call_data.status = "booked"
                
                # FR-08: Save booking UID for cancellation
                conversation.call_data.booking_uid = booking_result.get("booking_id") or booking_result.get("uid")
                
                print("Booking successful, sending SMS...")
                # Send SMS
                try:
                    send_confirmation_sms(
                        to_phone=conversation.call_data.phone,
                        name=conversation.call_data.name,
                        appointment_time=f"{selected_slot['date']} at {selected_slot['time']}"
                    )
                except Exception as sms_error:
                    print(f"SMS error (non-fatal): {sms_error}")

                print("Saving to Notion...")
                # Save to Notion
                try:
                    await create_lead(conversation.call_data, CallSid)
                except Exception as notion_error:
                    print(f"Notion error (non-fatal): {notion_error}")

                # Generate call summary before pushing to CRM
                summary = None
                try:
                    summary_data = await generate_call_summary(
                        messages=conversation.messages,
                        call_data={
                            "name": conversation.call_data.name,
                            "phone": conversation.call_data.phone,
                            "email": conversation.call_data.email,
                            "service": conversation.call_data.service,
                            "appointment_time": conversation.call_data.appointment_time,
                            "status": conversation.call_data.status,
                            "discovery_answers": conversation.call_data.discovery_answers,
                        }
                    )
                    summary = summary_data.get("summary") if summary_data else None
                except Exception as summary_error:
                    print(f"Summary generation error (non-fatal): {summary_error}")

                # Push to CRM backend
                print("Pushing to CRM backend...")
                try:
                    await push_to_crm_backend(conversation.call_data, CallSid, summary=summary, escalation_status="none")
                except Exception as crm_error:
                    print(f"CRM backend error (non-fatal): {crm_error}")

                response = VoiceResponse()
                if conversation.language == 'es':
                    response.say(
                        f"¡Perfecto! Te reservé para el {selected_slot['date']} a las {selected_slot['time']}. "
                        f"Te acabo de enviar un mensaje de confirmación. ¡Nos vemos pronto!",
                        voice=voice
                    )
                else:
                    response.say(
                        f"Perfect! You're all set for {selected_slot['date']} at {selected_slot['time']}. "
                        f"Just sent you a confirmation text. Talk to you soon!",
                        voice=voice
                    )

                # Don't end conversation here - let status callback handle it so transcript is saved
                return Response(content=str(response), media_type="application/xml")
            else:
                print(f"Booking failed: {booking_result.get('error')}")

        # Fallback
        response = VoiceResponse()
        if conversation.language == 'es':
            response.say(
                "Hmm, tengo un problema técnico. Déjame que alguien del equipo te llame de vuelta. ¡Gracias!",
                voice=voice
            )
        else:
            response.say(
                "Hmm, I'm having a little tech issue. Let me have someone from the team call you back. Thanks!",
                voice=voice
            )

        conversation.call_data.status = "needs_callback"
        try:
            await create_lead(conversation.call_data, CallSid)
        except Exception as e:
            print(f"Failed to save lead: {e}")
        
        # Generate call summary before pushing to CRM
        summary = None
        try:
            summary_data = await generate_call_summary(
                messages=conversation.messages,
                call_data={
                    "name": conversation.call_data.name,
                    "phone": conversation.call_data.phone,
                    "email": conversation.call_data.email,
                    "service": conversation.call_data.service,
                    "appointment_time": conversation.call_data.appointment_time,
                    "status": conversation.call_data.status,
                    "discovery_answers": conversation.call_data.discovery_answers,
                }
            )
            summary = summary_data.get("summary") if summary_data else None
        except Exception as summary_error:
            print(f"Summary generation error (non-fatal): {summary_error}")

        # Push to CRM backend
        try:
            await push_to_crm_backend(conversation.call_data, CallSid, summary=summary, escalation_status="pending")
        except Exception as e:
            print(f"Failed to push to CRM backend: {e}")

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        print(f"Error in book_slot: {e}")
        traceback.print_exc()
        response = VoiceResponse()
        response.say(sanitize_for_tts("Oops, having a tech issue. Let me have someone call you back. Thanks!"), voice='Google.en-US-Neural2-F')
        return Response(content=str(response), media_type="application/xml")

@router.post("/voice/status")
async def call_status(request: Request, CallSid: str = Form(...), CallStatus: str = Form(...)):
    """Receives call status updates"""
    require_agent_for_tenant(request, CRM_TENANT_CODE)
    print(f"Call {CallSid} status: {CallStatus}")

    try:
        if CallStatus == "completed":
            conversation = get_conversation(CallSid)
            
            # Generate call summary
            summary = None
            try:
                print(f"DEBUG: Conversation has {len(conversation.messages)} messages")
                print(f"DEBUG: Call data: name={conversation.call_data.name}, phone={conversation.call_data.phone}")
                
                summary = await generate_call_summary(
                    messages=conversation.messages,
                    call_data={
                        "name": conversation.call_data.name,
                        "phone": conversation.call_data.phone,
                        "email": conversation.call_data.email,
                        "service": conversation.call_data.service,
                        "appointment_time": conversation.call_data.appointment_time,
                        "status": conversation.call_data.status,
                        "discovery_answers": conversation.call_data.discovery_answers,
                    }
                )
                
                filepath = save_summary_to_file(CallSid, summary)
                print(f"✅ Saved call summary: {filepath}")
            except Exception as e:
                print(f"❌ Error generating summary: {e}")

            # Push comprehensive call log to /public/call-logs/ for all completed calls
            try:
                summary_text = summary.get("summary", "") if isinstance(summary, dict) else ""
                transcript_text = summary.get("transcript", "") if isinstance(summary, dict) else ""
                call_log_escalation = determine_escalation_status(conversation.call_data, summary_text)
                await push_call_log_to_backend(
                    call_sid=CallSid,
                    call_data=conversation.call_data,
                    summary=summary_text,
                    transcript=transcript_text,
                    escalation_status=call_log_escalation,
                    language=conversation.language,
                    discovery_answers=conversation.call_data.discovery_answers,
                )
                print("✅ Call log pushed to /public/call-logs/")
            except Exception as e:
                print(f"⚠️ Call log push failed (non-fatal): {e}")

            if conversation.call_data.status == "new":
                conversation.call_data.status = "no_booking"
                try:
                    await create_lead(conversation.call_data, CallSid)
                except Exception as e:
                    print(f"Failed to save lead on completion: {e}")

                # Push to CRM backend with summary text (extracted from summary dict)
                try:
                    summary_text = summary.get("summary", "") if isinstance(summary, dict) else ""
                    crm_escalation = determine_escalation_status(conversation.call_data, summary_text)
                    await push_to_crm_backend(
                        call_data=conversation.call_data,
                        call_sid=CallSid,
                        summary=summary_text,
                        escalation_status=crm_escalation,
                    )
                except Exception as e:
                    print(f"Failed to push to CRM backend on completion: {e}")

            end_conversation(CallSid)

        return {"status": "received"}
    except Exception as e:
        print(f"Error in call_status: {e}")
        return {"status": "error", "message": str(e)}