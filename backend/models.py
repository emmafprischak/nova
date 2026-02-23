"""
Data models - defines the structure of data we work with
"""
from pydantic import BaseModel
from typing import Optional

class CallData(BaseModel):
    """Stores information collected during a call"""
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    service: Optional[str] = None
    appointment_time: Optional[str] = None
    status: str = "new"
    notes: str = ""
   
    
class Message(BaseModel):
    """Represents a single message in the conversation"""
    role: str  # 'user' or 'assistant'
    content: str
    
class ConversationState(BaseModel):
    """Tracks the state of an ongoing conversation"""
    call_sid: str
    messages: list[Message] = []
    call_data: CallData = CallData()
    stage: str = "greeting"
    language: str = "en"  # 'en' or 'es'
    discovery_complete: bool = False
