import requests
import json
from datetime import datetime, timezone

# Full realistic payload with long transcript
payload = {
    tenant_code: walmart,
    call_sid: CA1234567890abcdef1234567890abcdef,
    caller_name: John Doe,
    caller_phone: +15551234567,
    email: johndoe@example.com,
    timestamp: datetime.now(timezone.utc).isoformat().replace(+00:00, Z),
    escalation_status: none,
    
    # Long transcript field
    full_transcript: Agent: Thank you for calling Nova. How can I help you today?
