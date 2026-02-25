"""
Call Transcript & Summary Generation
Generates call summaries without database storage (for now)
"""

import logging
from openai import OpenAI
from typing import Optional
from backend.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

# System prompt for generating summaries
SUMMARY_PROMPT = """You are analyzing a customer service call for Orbyn.AI.

Generate a brief, professional call summary that includes:

1. **Problem Statement** (1 sentence): What did the caller need?
2. **Call Summary** (2-3 sentences): What happened during the call? What info was collected?
3. **Outcome**: Was an appointment booked? Do they need a callback?
4. **Next Steps**: What should the team do next?

Keep it concise and factual. Write in third person (e.g., "Caller requested...").

CONVERSATION:
{conversation}
"""


def format_conversation_transcript(messages: list) -> str:
    """
    Convert message list to a readable transcript.
    
    Args:
        messages: List of Message objects with role and content
        
    Returns:
        Formatted transcript string
    """
    lines = []
    for msg in messages:
        role = msg.role.upper()
        content = msg.content.strip()
        
        # Skip system messages
        if role == "SYSTEM":
            continue
            
        # Label speakers
        if role == "USER":
            label = "CALLER"
        elif role == "ASSISTANT":
            label = "NOVA"
        else:
            label = role
            
        lines.append(f"{label}: {content}")
    
    return "\n".join(lines)


async def generate_call_summary(messages: list, call_data: dict) -> dict:
    """
    Generate a call summary using GPT-4.
    
    Args:
        messages: List of conversation messages
        call_data: Dict with name, phone, service, appointment_time, etc.
        
    Returns:
        dict with:
            - transcript: Full formatted conversation
            - summary: AI-generated summary
            - problem_statement: One-line problem description
            - outcome: What happened (booked/callback/no_action)
            - next_steps: What the team should do
    """
    try:
        # Format the conversation
        transcript = format_conversation_transcript(messages)
        
        # Generate summary with OpenAI
        prompt = SUMMARY_PROMPT.format(conversation=transcript)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap for summaries
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Low temp for consistent formatting
            max_tokens=300,
        )
        
        summary_text = response.choices[0].message.content
        
        # Parse the summary into sections
        lines = summary_text.split("\n")
        parsed = {
            "problem_statement": "",
            "summary": "",
            "outcome": "",
            "next_steps": "",
        }
        
        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect section headers
            if "problem statement" in line.lower():
                current_section = "problem_statement"
                # Extract text after the header
                if ":" in line:
                    parsed[current_section] = line.split(":", 1)[1].strip()
            elif "call summary" in line.lower() or "summary" in line.lower():
                current_section = "summary"
                if ":" in line:
                    parsed[current_section] = line.split(":", 1)[1].strip()
            elif "outcome" in line.lower():
                current_section = "outcome"
                if ":" in line:
                    parsed[current_section] = line.split(":", 1)[1].strip()
            elif "next step" in line.lower():
                current_section = "next_steps"
                if ":" in line:
                    parsed[current_section] = line.split(":", 1)[1].strip()
            elif current_section:
                # Continue current section
                parsed[current_section] += " " + line
        
        # Determine outcome if not parsed
        if not parsed["outcome"]:
            if call_data.get("appointment_time"):
                parsed["outcome"] = "Appointment booked"
            elif call_data.get("status") == "needs_callback":
                parsed["outcome"] = "Needs callback"
            else:
                parsed["outcome"] = "No booking made"
        
        return {
            "transcript": transcript,
            "summary": parsed["summary"] or summary_text,  # Fallback to full text
            "problem_statement": parsed["problem_statement"],
            "outcome": parsed["outcome"],
            "next_steps": parsed["next_steps"],
            "call_data": call_data,  # Include for reference
        }
        
    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        
        # Return basic transcript if summary generation fails
        return {
            "transcript": format_conversation_transcript(messages),
            "summary": "Summary generation failed",
            "problem_statement": "Unknown",
            "outcome": call_data.get("status", "Unknown"),
            "next_steps": "Review call manually",
            "call_data": call_data,
        }


def save_summary_to_file(call_sid: str, summary_data: dict, output_dir: str = "/opt/nova/nova-voice-agent/call_summaries") -> str:
    """
    Save call summary to a text file.
    
    Args:
        call_sid: Twilio call SID
        summary_data: Dict from generate_call_summary()
        output_dir: Directory to save files
        
    Returns:
        Path to saved file
    """
    import os
    from datetime import datetime
    
    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/call_{timestamp}_{call_sid[:8]}.txt"
    
    # Format the summary
    content = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                          NOVA CALL SUMMARY                               ║
╚══════════════════════════════════════════════════════════════════════════╝

CALL ID: {call_sid}
DATE: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

┌─ CALLER INFORMATION ─────────────────────────────────────────────────────┐
│ Name:    {summary_data['call_data'].get('name', 'Not provided')}
│ Phone:   {summary_data['call_data'].get('phone', 'Not provided')}
│ Email:   {summary_data['call_data'].get('email', 'Not provided')}
│ Service: {summary_data['call_data'].get('service', 'Not specified')}
└──────────────────────────────────────────────────────────────────────────┘

┌─ PROBLEM STATEMENT ──────────────────────────────────────────────────────┐
│ {summary_data['problem_statement']}
└──────────────────────────────────────────────────────────────────────────┘

┌─ CALL SUMMARY ───────────────────────────────────────────────────────────┐
│ {summary_data['summary']}
└──────────────────────────────────────────────────────────────────────────┘

┌─ OUTCOME ────────────────────────────────────────────────────────────────┐
│ {summary_data['outcome']}
│ Appointment: {summary_data['call_data'].get('appointment_time', 'None')}
└──────────────────────────────────────────────────────────────────────────┘

┌─ NEXT STEPS ─────────────────────────────────────────────────────────────┐
│ {summary_data['next_steps']}
└──────────────────────────────────────────────────────────────────────────┘

╔══════════════════════════════════════════════════════════════════════════╗
║                         FULL TRANSCRIPT                                  ║
╚══════════════════════════════════════════════════════════════════════════╝

{summary_data['transcript']}

═══════════════════════════════════════════════════════════════════════════
End of Summary
═══════════════════════════════════════════════════════════════════════════
"""
    
    # Write to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"Saved call summary to: {filename}")
    return filename