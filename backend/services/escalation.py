"""
Human Escalation Service
Detects when calls should be transferred to a human agent
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Keywords that indicate frustration or need for human
ESCALATION_KEYWORDS = [
    # Direct requests
    "speak to a person", "talk to someone", "human", "real person",
    "representative", "agent", "manager", "supervisor",
    
    # Frustration indicators
    "frustrated", "angry", "upset", "not helping", "doesn't work",
    "not understanding", "don't understand", "confused",
    
    # Complex issues
    "emergency", "urgent", "right now", "immediately", "crisis",
    "complicated", "complex", "long story",
    
    # Dissatisfaction
    "this isn't working", "can't help", "not working", "useless",
    "terrible", "awful", "horrible", "waste of time",
]

# Spanish escalation keywords
ESCALATION_KEYWORDS_ES = [
    "persona real", "hablar con alguien", "humano", "representante",
    "agente", "gerente", "supervisor",
    "frustrado", "enojado", "molesto", "no ayuda",
    "no entiendo", "confundido",
    "emergencia", "urgente", "inmediatamente", "crisis",
    "complicado", "complejo",
    "no funciona", "terrible", "horrible",
]


def should_escalate_to_human(
    user_input: str,
    conversation_messages: list,
    language: str = "en",
    failed_attempts: int = 0
) -> tuple[bool, str]:
    """
    Determine if the call should be escalated to a human.
    
    Args:
        user_input: Latest message from caller
        conversation_messages: Full conversation history
        language: 'en' or 'es'
        failed_attempts: Number of times AI failed to extract needed info
        
    Returns:
        (should_escalate: bool, reason: str)
    """
    reasons = []
    
    # Check for direct escalation keywords
    keywords = ESCALATION_KEYWORDS_ES if language == 'es' else ESCALATION_KEYWORDS
    user_lower = user_input.lower()
    
    for keyword in keywords:
        if keyword in user_lower:
            return True, f"User requested human: '{keyword}'"
    
    # Check for too many failed attempts
    if failed_attempts >= 3:
        return True, f"Failed to extract information after {failed_attempts} attempts"
    
    # Check for very short frustrated responses
    short_frustrated = ["no", "nope", "whatever", "forget it", "nevermind", "bye"]
    if user_lower.strip() in short_frustrated and len(conversation_messages) > 4:
        return True, "User appears frustrated (short negative responses)"
    
    # Check for conversation going in circles
    if len(conversation_messages) > 20:
        # Count repeated questions from AI
        ai_messages = [msg.content for msg in conversation_messages if msg.role == "assistant"]
        if len(ai_messages) > 10:
            # Simple check: are we asking similar questions?
            question_count = sum(1 for msg in ai_messages if "?" in msg)
            if question_count > 8:
                return True, "Conversation going in circles (too many questions)"
    
    return False, ""


def generate_escalation_message(reason: str, language: str = "en") -> str:
    """
    Generate appropriate message when escalating to human.
    
    Args:
        reason: Why we're escalating
        language: 'en' or 'es'
        
    Returns:
        Message to say to caller before transfer
    """
    if language == "es":
        return (
            "Entiendo. Déjame conectarte con uno de nuestros representantes "
            "que puede ayudarte mejor. Por favor, espera un momento."
        )
    else:
        return (
            "I understand. Let me connect you with one of our team members "
            "who can help you better. Please hold for just a moment."
        )


def get_escalation_phone_number() -> Optional[str]:
    """
    Get the phone number to transfer to.
    In a real system, this might route to different numbers based on:
    - Time of day
    - Caller's issue
    - Agent availability
    
    For now, returns a single fallback number.
    """
    # TODO: Replace with actual team phone number
    return "+18145550100"  # Example fallback number


def log_escalation(call_sid: str, reason: str, call_data: dict):
    """
    Log that this call was escalated for review.
    
    Args:
        call_sid: Twilio call SID
        reason: Why it was escalated
        call_data: Information collected so far
    """
    logger.warning(
        f"ESCALATION: Call {call_sid} escalated to human. "
        f"Reason: {reason}. "
        f"Caller: {call_data.get('name', 'Unknown')} - {call_data.get('phone', 'Unknown')}"
    )
    
    # You could also:
    # - Send Slack notification
    # - Create urgent task in CRM
    # - Send SMS to on-call agent
    # - Log to escalation tracking system


class EscalationTracker:
    """
    Track escalation patterns to improve AI over time.
    """
    def __init__(self):
        self.escalations = {}  # call_sid -> reason
    
    def record_escalation(self, call_sid: str, reason: str):
        """Record that a call was escalated."""
        self.escalations[call_sid] = reason
        logger.info(f"Recorded escalation for {call_sid}: {reason}")
    
    def get_escalation_rate(self) -> float:
        """Calculate percentage of calls that get escalated."""
        # In real system, would query from database
        # For now, just return from in-memory tracking
        if not hasattr(self, '_total_calls'):
            return 0.0
        return (len(self.escalations) / self._total_calls) * 100
    
    def get_common_reasons(self) -> dict:
        """Get most common escalation reasons."""
        from collections import Counter
        return dict(Counter(self.escalations.values()).most_common(5))


# Global escalation tracker
escalation_tracker = EscalationTracker()