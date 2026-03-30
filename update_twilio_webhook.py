#!/usr/bin/env python3
"""
Update Twilio phone number to add status callback URL
"""
import os
from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# Initialize Twilio client
client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Get the base URL from environment or prompt
print("What is your server's public URL?")
print("Example: https://your-domain.com or https://yourdomain.ngrok.io")
base_url = input("Enter URL (without trailing slash): ").strip()

if not base_url.startswith('http'):
    print("Error: URL must start with http:// or https://")
    exit(1)

# Define the webhook URLs
voice_url = f"{base_url}/webhooks/voice/incoming"
status_callback_url = f"{base_url}/webhooks/voice/status"

print(f"\nUpdating Twilio configuration for {PHONE_NUMBER}...")
print(f"Voice URL: {voice_url}")
print(f"Status Callback URL: {status_callback_url}")

# Get all phone numbers
phone_numbers = client.incoming_phone_numbers.list(phone_number=PHONE_NUMBER)

if not phone_numbers:
    print(f"Error: Could not find phone number {PHONE_NUMBER}")
    exit(1)

# Update the phone number configuration
phone_number_sid = phone_numbers[0].sid
updated = client.incoming_phone_numbers(phone_number_sid).update(
    voice_url=voice_url,
    voice_method='POST',
    status_callback=status_callback_url,
    status_callback_method='POST'
)

print("\n✅ Successfully updated Twilio configuration!")
print(f"\nConfiguration:")
print(f"  Phone Number: {updated.phone_number}")
print(f"  Voice URL: {updated.voice_url}")
print(f"  Status Callback: {updated.status_callback}")
print(f"\n🎉 Call summaries will now be generated when calls complete!")
