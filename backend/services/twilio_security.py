"""
Twilio Security Middleware
Validates Twilio webhook requests to prevent spoofing
"""
from fastapi import Request, HTTPException
from twilio.request_validator import RequestValidator
import os

async def validate_twilio_request(request: Request, url: str) -> bool:
    """
    Validate that the request is actually from Twilio.
    
    Args:
        request: FastAPI request object
        url: The full URL of the webhook endpoint (must be the ngrok URL that Twilio sees)
        
    Returns:
        True if valid, raises HTTPException if not
        
    Raises:
        HTTPException: If request is not from Twilio
    """
    # Get Twilio auth token from environment
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    
    if not auth_token:
        # If no auth token configured, skip validation (development mode)
        print('WARNING: TWILIO_AUTH_TOKEN not set - skipping validation')
        return True
    
    # Create validator
    validator = RequestValidator(auth_token)
    
    # Get signature from headers
    signature = request.headers.get('X-Twilio-Signature', '')
    
    if not signature:
        print('ERROR: No X-Twilio-Signature header found')
        raise HTTPException(
            status_code=403,
            detail='Missing Twilio signature'
        )
    
    # Get POST parameters as dict
    # Twilio sends form data, not JSON
    form_data = await request.form()
    params = dict(form_data)
    
    # Validate the request
    is_valid = validator.validate(url, params, signature)
    
    if not is_valid:
        print(f'ERROR: Invalid Twilio signature for URL: {url}')
        print(f'Expected signature for: {url}')
        print(f'Got signature: {signature}')
        raise HTTPException(
            status_code=403,
            detail='Invalid Twilio signature'
        )
    
    print(f'✅ Valid Twilio signature for: {url}')
    return True
