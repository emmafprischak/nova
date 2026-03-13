"""
Two Factor Authentication Service
FR-18: Generates and validates 6-digit verification codes for appointment booking
"""

import random
import time
from typing import Optional, Dict
from datetime import datetime, timedelta

# Store verification codes in memory (call_sid -> verification data)
verification_store: Dict[str, dict] = {}

# Constants
CODE_LENGTH = 6
MAX_ATTEMPTS = 3
CODE_EXPIRATION_MINUTES = 5


def generate_verification_code() -> str:
    """Generate a random 6-digit verification code."""
    return ''.join([str(random.randint(0, 9)) for _ in range(CODE_LENGTH)])


def create_verification(call_sid: str) -> str:
    """
    Create a new verification code for a call.
    
    Args:
        call_sid: Twilio call SID
        
    Returns:
        The generated 6-digit code
    """
    code = generate_verification_code()
    
    verification_store[call_sid] = {
        "code": code,
        "attempts": 0,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(minutes=CODE_EXPIRATION_MINUTES)
    }
    
    print(f"Generated verification code for {call_sid}: {code}")
    return code


def verify_code(call_sid: str, spoken_code: str) -> dict:
    """
    Verify a spoken verification code.
    
    Args:
        call_sid: Twilio call SID
        spoken_code: The code spoken by the user (may be words like "one two three")
        
    Returns:
        dict with:
            - valid: bool - whether code is valid
            - reason: str - reason if invalid
            - attempts_remaining: int - attempts left before lockout
    """
    if call_sid not in verification_store:
        return {
            "valid": False,
            "reason": "no_code_exists",
            "attempts_remaining": 0
        }
    
    verification = verification_store[call_sid]
    
    # Check if expired
    if datetime.now() > verification["expires_at"]:
        del verification_store[call_sid]
        return {
            "valid": False,
            "reason": "expired",
            "attempts_remaining": 0
        }
    
    # Convert spoken code to digits
    code_digits = convert_spoken_to_digits(spoken_code)
    
    # Increment attempts
    verification["attempts"] += 1
    attempts_remaining = MAX_ATTEMPTS - verification["attempts"]
    
    print(f"Verification attempt {verification['attempts']}/{MAX_ATTEMPTS} for {call_sid}")
    print(f"Expected: {verification['code']}, Got: {code_digits}")
    
    # Check if code matches
    if code_digits == verification["code"]:
        # Success - clean up
        del verification_store[call_sid]
        return {
            "valid": True,
            "reason": "success",
            "attempts_remaining": attempts_remaining
        }
    
    # Check if out of attempts
    if verification["attempts"] >= MAX_ATTEMPTS:
        del verification_store[call_sid]
        return {
            "valid": False,
            "reason": "max_attempts",
            "attempts_remaining": 0
        }
    
    # Invalid but can try again
    return {
        "valid": False,
        "reason": "incorrect",
        "attempts_remaining": attempts_remaining
    }


def convert_spoken_to_digits(spoken: str) -> str:
    """
    Convert spoken numbers to digit string.
    Handles: "one two three" -> "123", "1 2 3" -> "123", etc.
    
    Args:
        spoken: The spoken input from user
        
    Returns:
        String of digits
    """
    # Word to digit mapping
    word_to_digit = {
        "zero": "0", "oh": "0",
        "one": "1",
        "two": "2", "to": "2", "too": "2",
        "three": "3", "tree": "3",
        "four": "4", "for": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8", "ate": "8",
        "nine": "9", "niner": "9"
    }
    
    spoken_lower = spoken.lower().strip()
    digits = []
    
    # First, try to extract any existing digits
    for char in spoken_lower:
        if char.isdigit():
            digits.append(char)
    
    # If we got 6 digits, we're done
    if len(digits) == CODE_LENGTH:
        return ''.join(digits)
    
    # Otherwise, try word conversion
    digits = []
    words = spoken_lower.split()
    
    for word in words:
        # Remove punctuation
        word = word.strip('.,!?')
        
        if word in word_to_digit:
            digits.append(word_to_digit[word])
        elif word.isdigit():
            digits.append(word)
    
    return ''.join(digits)


def cleanup_expired_codes():
    """Remove expired verification codes from storage."""
    now = datetime.now()
    expired_sids = [
        sid for sid, data in verification_store.items()
        if now > data["expires_at"]
    ]
    
    for sid in expired_sids:
        del verification_store[sid]
        print(f"Cleaned up expired verification code for {sid}")
    
    return len(expired_sids)
