"""
Conversation Service - Handles AI conversation using OpenAI
"""
from openai import OpenAI
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OPENAI_API_KEY, NOVA_SYSTEM_PROMPT_EN, NOVA_SYSTEM_PROMPT_ES, NOVA_CANCELLATION_PROMPT_EN, NOVA_CANCELLATION_PROMPT_ES
from models import ConversationState, Message
import json

# FR-08: Discovery questions integration
from services.discovery import (
    extract_discovery_answers,
    has_sufficient_discovery_data,
    DISCOVERY_SYSTEM_PROMPT
)
from services.calendar_cancellation import is_cancellation_request

# FR-13: Name spelling
from services.name_spelling import (
    generate_spelling_confirmation,
    detect_spelling_correction,
    generate_correction_request,
    extract_spelled_name,
    split_full_name
)

# Escalation
from services.escalation import (
    should_escalate_to_human,
    generate_escalation_message,
    log_escalation
)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Store active conversations
active_conversations = {}

def get_conversation(call_sid: str) -> ConversationState:
    """Get or create a conversation state for a call"""
    if call_sid not in active_conversations:
        active_conversations[call_sid] = ConversationState(call_sid=call_sid)
    return active_conversations[call_sid]

def detect_language(text: str) -> str:
    """
    Detect if the text is in Spanish or English
    Returns: 'es' for Spanish, 'en' for English
    """
    # Common Spanish words and patterns
    spanish_indicators = [
        'hola', 'buenos', 'días', 'tardes', 'noches', 'gracias', 'por favor',
        'sí', 'necesito', 'quiero', 'busco', 'ayuda', 'información',
        'habla', 'español', 'puedo', 'estoy', 'tengo'
    ]

    text_lower = text.lower()
    spanish_word_count = sum(1 for word in spanish_indicators if word in text_lower)

    # If we find 2 or more Spanish indicators, it's likely Spanish
    return 'es' if spanish_word_count >= 1 else 'en'

def generate_response(call_sid: str, user_message: str, detected_language: str = None) -> tuple[str, dict]:
    """
    Generate Nova's response to what the user said

    Returns:
        tuple: (Nova's response text, extracted data)
    """
    conversation = get_conversation(call_sid)
    conversation.messages.append(Message(role="user", content=user_message))

    # Detect language if provided
    if detected_language:
        conversation.language = detected_language
    
    # Check for escalation
    failed_attempts = getattr(conversation, 'failed_extraction_count', 0)
    
    should_escalate, reason = should_escalate_to_human(
        user_input=user_message,
        conversation_messages=conversation.messages,
        language=conversation.language,
        failed_attempts=failed_attempts
    )
    
    if should_escalate:
        log_escalation(call_sid, reason, {
            "name": conversation.call_data.name,
            "phone": conversation.call_data.phone,
        })
        
        conversation.call_data.status = "needs_human"
        escalation_msg = generate_escalation_message(reason, conversation.language)
        
        return escalation_msg, {"escalate": True}
    
    # FR-13: Handle spelling confirmation response
    if hasattr(conversation, 'awaiting_name_confirmation') and conversation.awaiting_name_confirmation:
        
        # Check if they said it's wrong
        if detect_spelling_correction(user_message):
            conversation.spelling_attempts += 1
            
            # First wrong attempt: try NATO phonetic for clarity
            if conversation.spelling_attempts == 1:
                conversation.awaiting_name_confirmation = True  # Still confirming
                
                nato_spelling = generate_spelling_confirmation(
                    conversation.call_data.name,
                    conversation.language,
                    use_nato=True  # NOW use NATO alphabet
                )
                
                return nato_spelling, {}
            
            # Second wrong attempt: ask them to spell it
            else:
                conversation.awaiting_spelling_correction = True
                conversation.awaiting_name_confirmation = False
                
                correction_request = generate_correction_request(conversation.language)
                return correction_request, {}
        else:
            # They confirmed it's correct
            conversation.name_confirmed = True
            conversation.awaiting_name_confirmation = False
            
            # NEW: After name is confirmed, move to discovery stage
            if not conversation.discovery_complete:
                conversation.stage = 'discovery'
            
            # Continue normal conversation - let AI respond naturally
    
    # FR-13: Handle letter-by-letter spelling
    if hasattr(conversation, 'awaiting_spelling_correction') and conversation.awaiting_spelling_correction:
        # Extract the spelled name
        corrected_name = extract_spelled_name(user_message)
        
        if corrected_name:
            # Get first name from original
            first, _ = split_full_name(conversation.call_data.name)
            
            # Update with corrected last name
            conversation.call_data.name = f"{first} {corrected_name}".strip()
            conversation.name_confirmed = True
            conversation.awaiting_spelling_correction = False
            
            # NEW: After name is confirmed via manual spelling, move to discovery
            if not conversation.discovery_complete:
                conversation.stage = 'discovery'
            
            # Confirm we got it
            if conversation.language == 'es':
                confirmation = f"Perfecto, {conversation.call_data.name}. Gracias."
            else:
                confirmation = f"Got it, {conversation.call_data.name}. Thank you."
            
            return confirmation, {"name": conversation.call_data.name}
    
    # FR-08.5: Check for cancellation request
    if is_cancellation_request(user_message) and not conversation.is_cancelling:
        conversation.is_cancelling = True
        conversation.stage = 'cancellation'
        logger.info("Cancellation detected", call_sid=call_sid)
    
    # FR-08: Extract discovery answers from user input
    if hasattr(conversation, 'stage') and conversation.stage == 'discovery':
        conversation.call_data.discovery_answers = extract_discovery_answers(
            user_message,
            conversation.call_data.discovery_answers
        )
        
        # Check if we have enough discovery data to move forward
        if has_sufficient_discovery_data(conversation.call_data.discovery_answers):
            conversation.discovery_complete = True
            # Transition back to normal conversation flow for booking
            conversation.stage = 'booking'

    # Select the appropriate system prompt
    # Priority: cancellation > discovery > normal
    if hasattr(conversation, 'is_cancelling') and conversation.is_cancelling:
        # User wants to cancel - use cancellation prompt
        system_prompt = NOVA_CANCELLATION_PROMPT_ES if conversation.language == 'es' else NOVA_CANCELLATION_PROMPT_EN
    elif hasattr(conversation, 'stage') and conversation.stage == 'discovery' and not conversation.discovery_complete:
        # Discovery stage
        system_prompt = DISCOVERY_SYSTEM_PROMPT
    else:
        # Normal conversation
        system_prompt = NOVA_SYSTEM_PROMPT_ES if conversation.language == 'es' else NOVA_SYSTEM_PROMPT_EN
    
    # Build messages for OpenAI
    messages = [{"role": "system", "content": system_prompt}]

    for msg in conversation.messages:
        messages.append({"role": msg.role, "content": msg.content})
    
    # Only add extraction instructions when NOT in discovery mode
    # JSON extraction is always enabled - we just parse it silently
    if True:  # Always add extraction
        # Add extraction instructions - make it clearer this is AFTER the spoken response
        messages.append({
            "role": "system", 
            "content": """IMPORTANT: First, provide your conversational response to the user. Then, on a new line, output ONLY a JSON object (no additional text) with any extracted information:
{"name": "value or null", "phone": "value or null", "email": "value or null", "service": "value or null", "ready_to_book": true/false}

The JSON must come AFTER your spoken response and must not be part of what you say to the user."""
        })
    # Call OpenAI with settings optimized for natural conversation
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.9,  # Higher temperature for more natural, varied responses
        max_tokens=80,    # Shorter max to keep responses brief and punchy
        presence_penalty=0.6,  # Encourage variety in word choice
        frequency_penalty=0.3  # Reduce repetition
    )
    
    assistant_message = response.choices[0].message.content
    conversation.messages.append(Message(role="assistant", content=assistant_message))
    
    # Extract structured data
    extracted_data = {}
    try:
        if "{" in assistant_message and "}" in assistant_message:
            json_start = assistant_message.rfind("{")
            json_end = assistant_message.rfind("}") + 1
            json_str = assistant_message[json_start:json_end]
            extracted_data = json.loads(json_str)
            
            # Update call data
            if extracted_data.get("name"):
                conversation.call_data.name = extracted_data["name"]
                
                # FR-13: Check if we should spell the name
                if not hasattr(conversation, 'name_confirmed'):
                    conversation.name_confirmed = False
                    conversation.spelling_attempts = 0
                
                if not conversation.name_confirmed:
                    first, last = split_full_name(extracted_data["name"])
                    
                    # Only spell if there's a last name
                    if last:
                        # Start with simple spelling (no NATO)
                        spelling = generate_spelling_confirmation(
                            extracted_data["name"], 
                            conversation.language,
                            use_nato=False  # Simple spelling first
                        )
                        
                        if spelling:
                            # Mark that we're now waiting for spelling confirmation
                            conversation.awaiting_name_confirmation = True
                            
                            # Return the spelling instead of the normal response
                            return spelling, extracted_data
            
            if extracted_data.get("phone"):
                # Validate phone number - must be at least 10 digits
                phone = extracted_data["phone"]
                digits_only = re.sub(r'\D', '', phone)  # Remove all non-digits

                if len(digits_only) < 10:
                    # Phone number too short - ask again
                    if not hasattr(conversation, 'phone_attempt_count'):
                        conversation.phone_attempt_count = 0
                    conversation.phone_attempt_count += 1

                    if conversation.phone_attempt_count == 1:
                        # First attempt - ask for 10 digit number
                        response = "I need a valid 10-digit phone number. Can you provide that?"
                        return response, extracted_data
                    else:
                        # Second attempt failed - ask for email instead
                        response = "No problem, let me get your email address instead. What's your email?"
                        # Clear the invalid phone
                        extracted_data["phone"] = None
                        return response, extracted_data
                else:
                    # Valid phone number
                    conversation.call_data.phone = phone
                    if hasattr(conversation, 'phone_attempt_count'):
                        del conversation.phone_attempt_count
            if extracted_data.get("email"):
                conversation.call_data.email = extracted_data["email"]
            if extracted_data.get("service"):
                conversation.call_data.service = extracted_data["service"]
            
            # Check if we got useful data
            if not any([
                extracted_data.get("name"),
                extracted_data.get("phone"),
                extracted_data.get("email")
            ]):
                # Extraction failed - increment counter
                if not hasattr(conversation, 'failed_extraction_count'):
                    conversation.failed_extraction_count = 0
                conversation.failed_extraction_count += 1
            else:
                # Reset counter on success
                conversation.failed_extraction_count = 0
            
            # Remove JSON from response
            assistant_message = assistant_message[:json_start].strip()
    except:
        # JSON parsing failed
        if not hasattr(conversation, 'failed_extraction_count'):
            conversation.failed_extraction_count = 0
        conversation.failed_extraction_count += 1
    
    return assistant_message, extracted_data

def generate_call_summary(call_sid: str) -> str:
    """
    Generate a summary of the call using OpenAI
    
    Args:
        call_sid: The unique identifier for the call
    
    Returns:
        str: A concise 2-3 sentence summary of the call, including customer's name,
             what they needed, whether an appointment was booked, and any follow-up actions
    
    Raises:
        Exception: If the conversation doesn't exist, has no messages, or if OpenAI API fails
    """
    conversation = get_conversation(call_sid)
    
    # Validate that conversation has messages
    if not conversation or not conversation.messages:
        return "No conversation data available for summary."
    
    # Build the conversation transcript
    transcript = []
    for msg in conversation.messages:
        speaker = "Customer" if msg.role == "user" else "Nova"
        transcript.append(f"{speaker}: {msg.content}")
    
    transcript_text = "\n".join(transcript)
    
    # Create a summary prompt
    summary_prompt = f"""Summarize this customer service call in 2-3 sentences. Include:
- Customer's name and what they needed
- Whether an appointment was booked
- Any important follow-up actions

Call Transcript:
{transcript_text}"""
    
    # Call OpenAI to generate summary
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes customer service calls concisely."},
            {"role": "user", "content": summary_prompt}
        ],
        temperature=0.3,
        max_tokens=150
    )
    
    return response.choices[0].message.content

def end_conversation(call_sid: str):
    """Clean up conversation when call ends"""
    if call_sid in active_conversations:
        del active_conversations[call_sid]