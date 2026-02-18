"""
Conversation Service - Handles AI conversation using OpenAI
"""
from openai import OpenAI
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OPENAI_API_KEY, NOVA_SYSTEM_PROMPT_EN, NOVA_SYSTEM_PROMPT_ES
from models import ConversationState, Message
import json

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
    return 'es' if spanish_word_count >= 2 else 'en'

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

    # Select the appropriate system prompt
    system_prompt = NOVA_SYSTEM_PROMPT_ES if conversation.language == 'es' else NOVA_SYSTEM_PROMPT_EN

    # Build messages for OpenAI
    messages = [{"role": "system", "content": system_prompt}]

    for msg in conversation.messages:
        messages.append({"role": msg.role, "content": msg.content})
    
    # Add extraction instructions - make it clearer this is AFTER the spoken response
    messages.append({
        "role": "system", 
        "content": """IMPORTANT: First, provide your conversational response to the user. Then, on a new line, output ONLY a JSON object (no additional text) with any extracted information:
{"name": "value or null", "phone": "value or null", "email": "value or null", "service": "value or null", "ready_to_book": true/false}

The JSON must come AFTER your spoken response and must not be part of what you say to the user."""
    })
    
    # Call OpenAI with settings optimized for natural conversation
    response = client.chat.completions.create(
        model="gpt-4",
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
            if extracted_data.get("phone"):
                conversation.call_data.phone = extracted_data["phone"]
            if extracted_data.get("email"):
                conversation.call_data.email = extracted_data["email"]
            if extracted_data.get("service"):
                conversation.call_data.service = extracted_data["service"]
            
            # Remove JSON from response
            assistant_message = assistant_message[:json_start].strip()
    except:
        pass
    
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
        model="gpt-4",
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
