"""
Output Sanitization - Cleans AI-generated text before TTS delivery
Prevents JSON leakage, prompt injection, and formatting issues
"""
import re


def sanitize_for_tts(text: str, max_length: int = 500) -> str:
    """Clean AI-generated text before sending to Twilio TTS"""
    if not text:
        return ""
    
    original_text = text
    
    # 1. Remove JSON artifacts
    if "{" in text and "}" in text:
        last_brace_start = text.rfind("{")
        last_brace_end = text.rfind("}")
        if last_brace_end > last_brace_start:
            text = text[:last_brace_start].strip()
    
    # 2. Remove control characters
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    
    # 3. Remove markdown formatting
    text = text.replace("**", "").replace("*", "")
    text = text.replace("```", "").replace("`", "")
    text = text.replace("##", "").replace("#", "")
    
    # 4. Remove brackets
    text = re.sub(r'\[.*?\]', '', text)
    
    # 5. Collapse spaces
    text = " ".join(text.split())
    
    # 6. Block dangerous phrases
    dangerous_phrases = [
        "as an ai", "as a language model", "i am an ai",
        "ignore previous", "disregard", "system:",
        "assistant:", "user:", "[internal", "<system>", "prompt:"
    ]
    
    text_lower = text.lower()
    for phrase in dangerous_phrases:
        if phrase in text_lower:
            return "I apologize, I need to rephrase that. Could you repeat your question?"
    
    # 7. Remove HTML/XML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # 8. Truncate if too long
    if len(text) > max_length:
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        last_question = truncated.rfind('?')
        last_exclaim = truncated.rfind('!')
        last_sentence = max(last_period, last_question, last_exclaim)
        
        if last_sentence > max_length * 0.7:
            text = truncated[:last_sentence + 1]
        else:
            text = truncated.rstrip() + "..."
    
    # 9. Final cleanup
    text = text.strip()
    
    # 10. Validate output
    if not text or len(text) < 2:
        print(f"WARNING: Sanitization removed all content. Original: {original_text[:100]}")
        return "I'm sorry, could you repeat that?"
    
    return text


def sanitize_user_input(text: str, max_length: int = 1000) -> str:
    """Clean user speech input before processing"""
    if not text:
        return ""
    
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = " ".join(text.split())
    
    if len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()
