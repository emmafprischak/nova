"""
Webhook Routes - Twilio calls these endpoints
"""
from fastapi import APIRouter, Form, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import sys
import os
import traceback
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.conversation import generate_response, get_conversation, end_conversation, detect_language
from services.calendar import get_available_slots, book_appointment, format_slots_for_speech
from services.sms import send_confirmation_sms
from services.crm import create_lead, push_to_crm_backend

router = APIRouter()

@router.post("/voice/incoming")
async def handle_incoming_call(CallSid: str = Form(...)):
    """Called when someone calls your Twilio number"""
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
        response.say("I didn't hear anything. Please call back when you're ready. Goodbye!", voice='Google.en-US-Neural2-F')

        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        print(f"Error in incoming call: {e}")
        traceback.print_exc()
        response = VoiceResponse()
        response.say("Sorry, there was an error. Please try again later.", voice='Google.en-US-Neural2-F')
        return Response(content=str(response), media_type="application/xml")

@router.post("/voice/process")
async def process_speech(
    CallSid: str = Form(...),
    SpeechResult: str = Form(None),
    From: str = Form(...)
):
    """Called after the user speaks"""
    print(f"User said: {SpeechResult}")

    try:
        if not SpeechResult:
            response = VoiceResponse()
            response.say("Sorry, I didn't catch that. Could you say that again?", voice='Google.en-US-Neural2-F')
            response.redirect('/webhooks/voice/incoming')
            return Response(content=str(response), media_type="application/xml")

        # Detect language from user's speech
        detected_lang = detect_language(SpeechResult)
        print(f"Detected language: {detected_lang}")

        # Generate AI response with detected language
        ai_response, extracted_data = generate_response(CallSid, SpeechResult, detected_lang)

        print(f"Nova says: {ai_response}")
        print(f"Extracted: {extracted_data}")

        conversation = get_conversation(CallSid)

        # Get language settings with more natural neural voices
        lang_code = 'es-MX' if conversation.language == 'es' else 'en-US'
        voice = 'Google.es-US-Neural2-A' if conversation.language == 'es' else 'Google.en-US-Neural2-F'
        fallback_message = "¿Sigues ahí?" if conversation.language == 'es' else "Hello? You still there?"

        # Check if ready to book
        if (conversation.call_data.name and
            conversation.call_data.phone and
            extracted_data.get("ready_to_book")):

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
            gather.say(f"{ai_response} {slots_speech}", voice=voice)
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
        gather.say(ai_response, voice=voice)
        response.append(gather)

        response.say(fallback_message, voice=voice)
        response.redirect('/webhooks/voice/process')

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        print(f"Error in process_speech: {e}")
        traceback.print_exc()
        response = VoiceResponse()
        response.say("Oops, I'm having a little tech issue. Let me have someone call you back. Thanks!", voice='Google.en-US-Neural2-F')
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

                # Push to CRM backend
                print("Pushing to CRM backend...")
                try:
                    await push_to_crm_backend(conversation.call_data, CallSid)
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

                end_conversation(CallSid)
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
        
        # Push to CRM backend
        try:
            await push_to_crm_backend(conversation.call_data, CallSid)
        except Exception as e:
            print(f"Failed to push to CRM backend: {e}")

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        print(f"Error in book_slot: {e}")
        traceback.print_exc()
        response = VoiceResponse()
        response.say("Oops, having a tech issue. Let me have someone call you back. Thanks!", voice='Google.en-US-Neural2-F')
        return Response(content=str(response), media_type="application/xml")

@router.post("/voice/status")
async def call_status(CallSid: str = Form(...), CallStatus: str = Form(...)):
    """Receives call status updates"""
    print(f"Call {CallSid} status: {CallStatus}")

    try:
        if CallStatus == "completed":
            conversation = get_conversation(CallSid)
            if conversation.call_data.status == "new":
                conversation.call_data.status = "no_booking"
                try:
                    await create_lead(conversation.call_data, CallSid)
                except Exception as e:
                    print(f"Failed to save lead on completion: {e}")
                
                # Push to CRM backend
                try:
                    await push_to_crm_backend(conversation.call_data, CallSid)
                except Exception as e:
                    print(f"Failed to push to CRM backend on completion: {e}")

            end_conversation(CallSid)

        return {"status": "received"}
    except Exception as e:
        print(f"Error in call_status: {e}")
        return {"status": "error", "message": str(e)}
